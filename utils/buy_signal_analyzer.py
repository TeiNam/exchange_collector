"""
환율 매수 신호 분석 모듈

DB에서 환율 데이터를 조회하고, IndicatorCalculator로 기술적 지표를 계산하며,
매수/주의 신호를 판별하는 분석기.
"""

import logging
from dataclasses import dataclass

from utils.indicator_calculator import IndicatorCalculator

logger = logging.getLogger(__name__)


@dataclass
class Signal:
    """매수/주의 신호 데이터"""

    currency: str  # "USD" 또는 "JPY(100)"
    signal_type: str  # "n_week_low", "golden_cross", "dead_cross", "rsi_oversold", "rsi_overbought", "bollinger_low", "bollinger_high"
    message: str  # 사람이 읽을 수 있는 설명
    current_rate: float  # 현재 매매기준율
    indicator_value: float | None  # 관련 지표 값 (RSI 값, 밴드 값 등)


class BuySignalAnalyzer:
    """환율 매수 신호 분석기"""

    TARGET_CURRENCIES = ["USD", "JPY(100)"]
    N_WEEK_LOW_DAYS = 20  # 최저가 조회 영업일 수
    MA_SHORT = 5  # 단기 이동평균 기간
    MA_LONG = 20  # 장기 이동평균 기간
    RSI_PERIOD = 14  # RSI 기간
    RSI_OVERSOLD = 30  # RSI 과매도 기준
    RSI_OVERBOUGHT = 70  # RSI 과매수 기준
    BOLLINGER_PERIOD = 20  # 볼린저 밴드 기간
    BOLLINGER_STD = 2.0  # 볼린저 밴드 표준편차 배수

    def __init__(self, db_connector):
        """MySQLConnector 인스턴스를 주입받는다"""
        self.db_connector = db_connector

    def get_recent_rates(self, currency: str, days: int) -> list[float]:
        """
        DB에서 최근 N 영업일의 매매기준율을 조회한다.

        SQL 결과는 search_date DESC 순이므로, Python에서 역순 정렬하여
        오래된 순으로 반환한다.

        Args:
            currency: 통화 코드 (예: "USD", "JPY(100)")
            days: 조회할 영업일 수

        Returns:
            오래된 순으로 정렬된 deal_bas_r 리스트
        """
        connection = self.db_connector.get_connection()
        cursor = connection.cursor()
        try:
            query = (
                "SELECT deal_bas_r FROM exchange_rates "
                "WHERE cur_unit = %s "
                "ORDER BY search_date DESC LIMIT %s"
            )
            cursor.execute(query, (currency, days))
            rows = cursor.fetchall()
            # DB 결과는 최신순이므로 역순으로 변환하여 오래된 순으로 반환
            rates = [float(row[0]) for row in reversed(rows)]
            return rates
        finally:
            cursor.close()

    def analyze_currency(self, currency: str, today_rate: float) -> list[Signal]:
        """
        단일 통화에 대해 모든 지표를 분석하고 신호 리스트를 반환한다.

        각 지표 계산 실패 시 해당 지표만 건너뛰고 로그에 기록한다.

        Args:
            currency: 통화 코드 (예: "USD", "JPY(100)")
            today_rate: 오늘의 매매기준율

        Returns:
            감지된 Signal 리스트
        """
        signals: list[Signal] = []

        # MA 크로스 감지에 long_period + 1개 필요하므로 넉넉히 조회
        rates = self.get_recent_rates(currency, self.MA_LONG + 1)
        logger.info(f"{currency}: 최근 {len(rates)}일 데이터 조회 완료")

        # 1. N주 최저가 분석
        try:
            low_result = IndicatorCalculator.find_n_week_low(rates, min_days=10)
            if low_result is None:
                logger.info(f"{currency}: N주 최저가 분석 건너뜀 - 데이터 부족 (최소 10일 필요, 현재 {len(rates)}일)")
            else:
                lowest_price, num_days = low_result
                if today_rate <= lowest_price:
                    # 영업일 수를 주 단위로 변환 (5 영업일 = 1주)
                    weeks = num_days // 5
                    signals.append(Signal(
                        currency=currency,
                        signal_type="n_week_low",
                        message=f"{weeks}주({num_days} 영업일) 만에 최저가입니다. 매수를 고려해보세요",
                        current_rate=today_rate,
                        indicator_value=lowest_price,
                    ))
        except Exception as e:
            logger.error(f"{currency}: N주 최저가 분석 중 오류 발생: {e}", exc_info=True)

        # 2. MA 크로스 분석
        try:
            ma_cross = IndicatorCalculator.detect_ma_cross(
                rates, short_period=self.MA_SHORT, long_period=self.MA_LONG
            )
            if ma_cross == "golden_cross":
                signals.append(Signal(
                    currency=currency,
                    signal_type="golden_cross",
                    message="골든크로스 발생 - 단기 MA가 장기 MA를 상향 돌파",
                    current_rate=today_rate,
                    indicator_value=None,
                ))
            elif ma_cross == "dead_cross":
                signals.append(Signal(
                    currency=currency,
                    signal_type="dead_cross",
                    message="데드크로스 발생 - 단기 MA가 장기 MA를 하향 돌파",
                    current_rate=today_rate,
                    indicator_value=None,
                ))
        except Exception as e:
            logger.error(f"{currency}: MA 크로스 분석 중 오류 발생: {e}", exc_info=True)

        # 3. RSI 분석
        try:
            rsi_value = IndicatorCalculator.rsi(rates, period=self.RSI_PERIOD)
            if rsi_value is None:
                logger.info(f"{currency}: RSI 분석 건너뜀 - 데이터 부족 (최소 {self.RSI_PERIOD + 1}일 필요, 현재 {len(rates)}일)")
            elif rsi_value <= self.RSI_OVERSOLD:
                signals.append(Signal(
                    currency=currency,
                    signal_type="rsi_oversold",
                    message=f"RSI {rsi_value:.1f} - 과매도 구간, 반등 가능성",
                    current_rate=today_rate,
                    indicator_value=rsi_value,
                ))
            elif rsi_value >= self.RSI_OVERBOUGHT:
                signals.append(Signal(
                    currency=currency,
                    signal_type="rsi_overbought",
                    message=f"RSI {rsi_value:.1f} - 과매수 구간, 주의 필요",
                    current_rate=today_rate,
                    indicator_value=rsi_value,
                ))
        except Exception as e:
            logger.error(f"{currency}: RSI 분석 중 오류 발생: {e}", exc_info=True)

        # 4. 볼린저 밴드 분석
        try:
            bb_result = IndicatorCalculator.bollinger_bands(
                rates, period=self.BOLLINGER_PERIOD, num_std=self.BOLLINGER_STD
            )
            if bb_result is None:
                logger.info(f"{currency}: 볼린저 밴드 분석 건너뜀 - 데이터 부족 (최소 {self.BOLLINGER_PERIOD}일 필요, 현재 {len(rates)}일)")
            else:
                upper, middle, lower = bb_result
                if today_rate <= lower:
                    signals.append(Signal(
                        currency=currency,
                        signal_type="bollinger_low",
                        message=f"볼린저 밴드 하단({lower:.2f}) 터치 - 매수 신호",
                        current_rate=today_rate,
                        indicator_value=lower,
                    ))
                elif today_rate >= upper:
                    signals.append(Signal(
                        currency=currency,
                        signal_type="bollinger_high",
                        message=f"볼린저 밴드 상단({upper:.2f}) 터치 - 과매수 주의",
                        current_rate=today_rate,
                        indicator_value=upper,
                    ))
        except Exception as e:
            logger.error(f"{currency}: 볼린저 밴드 분석 중 오류 발생: {e}", exc_info=True)

        return signals

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
