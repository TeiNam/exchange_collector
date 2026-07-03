"""
환율 저가매기 매수 신호 분석 모듈

달러/엔화를 "싸게 사두려는" 실수요 관점의 신호를 판별한다.
주식 모멘텀 지표(골든/데드크로스, 과매수)는 사용하지 않으며,
"지금이 평소보다 싼가"를 여러 각도에서 확인한다.

신호 유형:
    disparity_low   - 이격도가 기준 이하 (장기 평균 대비 저평가)
    percentile_low  - 기간 내 하위 백분위 (최근 최저가권)
    bollinger_low   - 볼린저 밴드 하단 이하
    n_month_low     - 조회 기간 최저가 갱신
    rsi_oversold    - RSI 과매도 (참고 신호)
"""

import logging
from dataclasses import dataclass

from utils.indicator_calculator import IndicatorCalculator
from utils.time_utils import kst_today

logger = logging.getLogger(__name__)


@dataclass
class Signal:
    """매수 신호 데이터"""

    currency: str  # "USD" 또는 "JPY(100)"
    signal_type: str  # "disparity_low", "percentile_low", "bollinger_low", "n_month_low", "rsi_oversold"
    message: str  # 사람이 읽을 수 있는 설명
    current_rate: float  # 현재 매매기준율
    indicator_value: float | None  # 관련 지표 값


class BuySignalAnalyzer:
    """환율 저가매기 매수 신호 분석기"""

    TARGET_CURRENCIES = ["USD", "JPY(100)"]

    LOOKBACK_DAYS = 90          # 조회할 영업일 수 (약 4~5개월 캘린더)
    DISPARITY_PERIOD = 60       # 이격도 기준 이동평균 기간
    DISPARITY_THRESHOLD = 98.0  # 이격도 이 값 이하이면 저평가 (평균 대비 -2%)
    PERCENTILE_THRESHOLD = 20.0  # 하위 20% 이내이면 최저가권
    PERCENTILE_MIN_DAYS = 20     # 백분위 계산 최소 데이터 수
    BOLLINGER_PERIOD = 20        # 볼린저 밴드 기간
    BOLLINGER_STD = 2.0          # 볼린저 밴드 표준편차 배수
    N_LOW_MIN_DAYS = 20          # N개월 최저가 판별 최소 데이터 수
    RSI_PERIOD = 14              # RSI 기간
    RSI_OVERSOLD = 30            # RSI 과매도 기준

    def __init__(self, db_connector):
        """MySQLConnector 인스턴스를 주입받는다"""
        self.db_connector = db_connector

    def get_past_rates(self, currency: str, days: int) -> list[float]:
        """
        DB에서 오늘 이전(과거)의 최근 N 영업일 매매기준율을 조회한다.

        하루 여러 행이 있을 수 있으므로 날짜별 최신 1건만 사용해 일별 시계열로
        만든다. 오늘 값은 파라미터(today_rate)로 별도 전달되므로 항상 제외하여,
        "오늘 vs 과거" 비교가 데이터 저장 여부와 무관하게 일관되도록 한다.

        Args:
            currency: 통화 코드 (예: "USD", "JPY(100)")
            days: 조회할 과거 영업일 수

        Returns:
            오래된 순으로 정렬된 일별 deal_bas_r 리스트 (오늘 제외)
        """
        today_kst = kst_today()
        connection = self.db_connector.get_connection()
        cursor = connection.cursor()
        try:
            # 날짜별 최신 create_at 행 하나만 뽑아 일별 시계열 구성 (KST 오늘 제외).
            # KST 오늘을 파라미터로 전달하여 DB 타임존과 무관하게 일관된 날짜 기준 적용.
            query = (
                "SELECT deal_bas_r FROM exchange_rates e "
                "WHERE cur_unit = %s AND search_date < %s "
                "AND create_at = ("
                "  SELECT MAX(e2.create_at) FROM exchange_rates e2 "
                "  WHERE e2.cur_unit = e.cur_unit AND e2.search_date = e.search_date"
                ") "
                "ORDER BY search_date DESC LIMIT %s"
            )
            cursor.execute(query, (currency, today_kst, days))
            rows = cursor.fetchall()
            # DB 결과는 최신순이므로 역순으로 변환하여 오래된 순으로 반환
            return [float(row[0]) for row in reversed(rows)]
        finally:
            cursor.close()

    def analyze_currency(self, currency: str, today_rate: float) -> list[Signal]:
        """
        단일 통화에 대해 저가매기 지표를 분석하고 신호 리스트를 반환한다.

        각 지표 계산 실패 시 해당 지표만 건너뛰고 로그에 기록한다.

        Args:
            currency: 통화 코드
            today_rate: 오늘의 매매기준율

        Returns:
            감지된 Signal 리스트
        """
        signals: list[Signal] = []

        # today_rate는 DB에서 Decimal로 넘어올 수 있으므로 float으로 정규화한다.
        # (지표 계산이 float 리스트와 혼합 연산하므로 타입 통일 필수)
        today_rate = float(today_rate)

        # 과거 시계열 (오늘 제외). 오늘 값은 today_rate로만 다룬다.
        history = self.get_past_rates(currency, self.LOOKBACK_DAYS)
        logger.info(f"{currency}: 과거 {len(history)}일 데이터 조회 완료")

        # 이격도/볼린저는 과거 window로 기준(평균·밴드)을 만들고 오늘 값을 비교한다.
        # (기준 계산에 오늘 값을 넣으면 자기참조가 되어 신호가 둔감해진다.)
        # RSI는 변화량 기반이라 오늘 값을 시계열 끝에 붙여야 한다.
        series_with_today = history + [today_rate]

        # 1. 이격도 (장기 평균 대비 저평가) - 과거 평균 기준
        self._check_disparity(currency, today_rate, history, signals)

        # 2. 백분위 (과거 대비 최저가권)
        self._check_percentile(currency, today_rate, history, signals)

        # 3. 볼린저 밴드 하단 - 과거 밴드 기준
        self._check_bollinger(currency, today_rate, history, signals)

        # 4. N개월 최저가 (과거 최저가와 비교)
        self._check_n_low(currency, today_rate, history, signals)

        # 5. RSI 과매도 (참고 신호) - 오늘 값 포함 시계열
        self._check_rsi(currency, today_rate, series_with_today, signals)

        return signals

    def _check_disparity(self, currency, today_rate, rates, signals):
        try:
            disparity = IndicatorCalculator.disparity(rates, today_rate, self.DISPARITY_PERIOD)
            if disparity is None:
                logger.info(f"{currency}: 이격도 분석 건너뜀 - 데이터 부족 (최소 {self.DISPARITY_PERIOD}일 필요, 현재 {len(rates)}일)")
            elif disparity <= self.DISPARITY_THRESHOLD:
                signals.append(Signal(
                    currency=currency,
                    signal_type="disparity_low",
                    message=f"{self.DISPARITY_PERIOD}일 평균 대비 이격도 {disparity:.1f}% - 평소보다 저렴합니다",
                    current_rate=today_rate,
                    indicator_value=disparity,
                ))
        except Exception as e:
            logger.error(f"{currency}: 이격도 분석 중 오류 발생: {e}", exc_info=True)

    def _check_percentile(self, currency, today_rate, history, signals):
        try:
            if len(history) < self.PERCENTILE_MIN_DAYS:
                logger.info(f"{currency}: 백분위 분석 건너뜀 - 데이터 부족 (최소 {self.PERCENTILE_MIN_DAYS}일 필요, 현재 {len(history)}일)")
                return
            pct = IndicatorCalculator.percentile_rank(history, today_rate)
            if pct is not None and pct <= self.PERCENTILE_THRESHOLD:
                signals.append(Signal(
                    currency=currency,
                    signal_type="percentile_low",
                    message=f"최근 {len(history)}일 중 하위 {pct:.0f}% 수준 - 저점 근처입니다",
                    current_rate=today_rate,
                    indicator_value=pct,
                ))
        except Exception as e:
            logger.error(f"{currency}: 백분위 분석 중 오류 발생: {e}", exc_info=True)

    def _check_bollinger(self, currency, today_rate, rates, signals):
        try:
            bb_result = IndicatorCalculator.bollinger_bands(
                rates, period=self.BOLLINGER_PERIOD, num_std=self.BOLLINGER_STD
            )
            if bb_result is None:
                logger.info(f"{currency}: 볼린저 밴드 분석 건너뜀 - 데이터 부족 (최소 {self.BOLLINGER_PERIOD}일 필요, 현재 {len(rates)}일)")
                return
            _upper, _middle, lower = bb_result
            if today_rate <= lower:
                signals.append(Signal(
                    currency=currency,
                    signal_type="bollinger_low",
                    message=f"볼린저 밴드 하단({lower:.2f}) 이하 - 단기 저평가 구간",
                    current_rate=today_rate,
                    indicator_value=lower,
                ))
        except Exception as e:
            logger.error(f"{currency}: 볼린저 밴드 분석 중 오류 발생: {e}", exc_info=True)

    def _check_n_low(self, currency, today_rate, history, signals):
        try:
            low_result = IndicatorCalculator.find_n_week_low(history, min_days=self.N_LOW_MIN_DAYS)
            if low_result is None:
                logger.info(f"{currency}: 최저가 분석 건너뜀 - 데이터 부족 (최소 {self.N_LOW_MIN_DAYS}일 필요, 현재 {len(history)}일)")
                return
            lowest_price, num_days = low_result
            if today_rate <= lowest_price:
                months = max(1, round(num_days / 22))  # 약 22 영업일 = 1개월
                signals.append(Signal(
                    currency=currency,
                    signal_type="n_month_low",
                    message=f"약 {months}개월({num_days} 영업일) 만의 최저가입니다 - 매수 적기",
                    current_rate=today_rate,
                    indicator_value=lowest_price,
                ))
        except Exception as e:
            logger.error(f"{currency}: 최저가 분석 중 오류 발생: {e}", exc_info=True)

    def _check_rsi(self, currency, today_rate, rates, signals):
        try:
            rsi_value = IndicatorCalculator.rsi(rates, period=self.RSI_PERIOD)
            if rsi_value is None:
                logger.info(f"{currency}: RSI 분석 건너뜀 - 데이터 부족 (최소 {self.RSI_PERIOD + 1}일 필요, 현재 {len(rates)}일)")
            elif rsi_value <= self.RSI_OVERSOLD:
                signals.append(Signal(
                    currency=currency,
                    signal_type="rsi_oversold",
                    message=f"RSI {rsi_value:.1f} - 과매도 구간, 반등 전 저점 가능성",
                    current_rate=today_rate,
                    indicator_value=rsi_value,
                ))
        except Exception as e:
            logger.error(f"{currency}: RSI 분석 중 오류 발생: {e}", exc_info=True)

    def analyze(self, today_rates: dict[str, float]) -> list[Signal]:
        """
        모든 대상 통화에 대해 분석을 수행한다.

        각 통화를 독립적으로 분석하며, 한 통화의 분석 실패가
        다른 통화에 영향을 주지 않도록 개별 try-except로 처리한다.

        Args:
            today_rates: 통화별 오늘의 매매기준율
                예: {"USD": 1425.0, "JPY(100)": 945.0}

        Returns:
            감지된 모든 Signal 리스트
        """
        all_signals: list[Signal] = []

        for currency in self.TARGET_CURRENCIES:
            try:
                if currency not in today_rates:
                    logger.warning(f"{currency}: 오늘의 환율 데이터가 없어 분석을 건너뜁니다")
                    continue

                today_rate = today_rates[currency]
                signals = self.analyze_currency(currency, today_rate)
                all_signals.extend(signals)

                if signals:
                    logger.info(f"{currency}: {len(signals)}개 신호 감지")
                else:
                    logger.info(f"{currency}: 감지된 신호 없음")

            except Exception as e:
                logger.error(f"{currency}: 분석 중 오류 발생: {e}", exc_info=True)

        return all_signals
