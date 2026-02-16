"""
기술적 지표 계산 모듈

환율 데이터에 대한 이동평균, RSI, 볼린저 밴드 등
기술적 지표를 계산하는 순수 함수 모음.
모든 메서드는 상태를 갖지 않는 정적 메서드(static method)이다.
"""

import math


class IndicatorCalculator:
    """기술적 지표 계산 모듈 - 모든 메서드는 순수 함수(stateless)"""

    @staticmethod
    def moving_average(prices: list[float], period: int) -> float | None:
        """
        단순 이동평균(SMA) 계산

        마지막 period개의 가격에 대한 산술 평균을 반환한다.
        데이터가 부족하면 None을 반환한다.

        Args:
            prices: 최근 영업일 매매기준율 리스트 (오래된 순)
            period: 이동평균 기간

        Returns:
            이동평균 값 또는 데이터 부족 시 None
        """
        if len(prices) < period or period <= 0:
            return None

        return sum(prices[-period:]) / period

    @staticmethod
    def rsi(prices: list[float], period: int = 14) -> float | None:
        """
        RSI(상대강도지수) 계산 - Wilder 방식

        일정 기간 동안의 상승폭과 하락폭 비율로 과매수/과매도를 판단한다.
        최소 period + 1개의 데이터가 필요하다.

        Args:
            prices: 최근 영업일 매매기준율 리스트 (오래된 순, 최소 period+1개)
            period: RSI 계산 기간 (기본값: 14)

        Returns:
            0~100 사이의 RSI 값 또는 데이터 부족 시 None
        """
        # RSI 계산에는 period + 1개의 데이터가 필요 (변화량 계산을 위해)
        if len(prices) < period + 1 or period <= 0:
            return None

        # 가격 변화량 계산
        changes = [prices[i] - prices[i - 1] for i in range(1, len(prices))]

        # 첫 번째 평균 상승/하락폭 계산 (초기 period개의 변화량)
        initial_gains = [max(c, 0) for c in changes[:period]]
        initial_losses = [abs(min(c, 0)) for c in changes[:period]]

        avg_gain = sum(initial_gains) / period
        avg_loss = sum(initial_losses) / period

        # Wilder 평활법으로 나머지 변화량 반영
        for change in changes[period:]:
            gain = max(change, 0)
            loss = abs(min(change, 0))
            avg_gain = (avg_gain * (period - 1) + gain) / period
            avg_loss = (avg_loss * (period - 1) + loss) / period

        # RSI 계산
        if avg_loss == 0:
            # 하락이 전혀 없으면 RSI = 100
            return 100.0

        rs = avg_gain / avg_loss
        rsi_value = 100.0 - (100.0 / (1.0 + rs))

        return rsi_value

    @staticmethod
    def bollinger_bands(
        prices: list[float], period: int = 20, num_std: float = 2.0
    ) -> tuple[float, float, float] | None:
        """
        볼린저 밴드 계산

        이동평균선을 중심으로 표준편차의 num_std배를 상하로 설정한 밴드를 반환한다.

        Args:
            prices: 최근 영업일 매매기준율 리스트 (오래된 순)
            period: 볼린저 밴드 기간 (기본값: 20)
            num_std: 표준편차 배수 (기본값: 2.0)

        Returns:
            (상단, 중단, 하단) 튜플 또는 데이터 부족 시 None
        """
        if len(prices) < period or period <= 0:
            return None

        # 마지막 period개의 가격으로 계산
        recent_prices = prices[-period:]

        # 중단 = 단순 이동평균
        middle = sum(recent_prices) / period

        # 모표준편차 계산
        variance = sum((p - middle) ** 2 for p in recent_prices) / period
        std_dev = math.sqrt(variance)

        # 상단/하단 밴드
        upper = middle + num_std * std_dev
        lower = middle - num_std * std_dev

        return (upper, middle, lower)

    @staticmethod
    def find_n_week_low(
        prices: list[float], min_days: int = 10
    ) -> tuple[float, int] | None:
        """
        N주 최저가 산출

        주어진 가격 리스트에서 최저가와 영업일 수를 반환한다.
        데이터가 min_days 미만이면 None을 반환한다.

        Args:
            prices: 최근 영업일 매매기준율 리스트 (오래된 순, 10~20개)
            min_days: 최소 필요 영업일 수 (기본값: 10)

        Returns:
            (최저가, 영업일 수) 튜플 또는 데이터 부족 시 None
        """
        if len(prices) < min_days:
            return None

        lowest = min(prices)
        num_days = len(prices)

        return (lowest, num_days)

    @staticmethod
    def detect_ma_cross(
        prices: list[float], short_period: int = 5, long_period: int = 20
    ) -> str | None:
        """
        MA 크로스 감지

        전일과 당일의 단기/장기 이동평균선을 비교하여 교차를 판별한다.
        골든크로스(매수 신호) 또는 데드크로스(매도 신호)를 반환한다.

        Args:
            prices: 최근 영업일 매매기준율 리스트 (오래된 순)
            short_period: 단기 이동평균 기간 (기본값: 5)
            long_period: 장기 이동평균 기간 (기본값: 20)

        Returns:
            "golden_cross", "dead_cross", 또는 None
        """
        # 당일과 전일 모두 장기 MA를 계산하려면 long_period + 1개 이상 필요
        if len(prices) < long_period + 1 or short_period <= 0 or long_period <= 0:
            return None

        if short_period >= long_period:
            return None

        # 당일 MA 계산 (전체 리스트 기준)
        today_short_ma = sum(prices[-short_period:]) / short_period
        today_long_ma = sum(prices[-long_period:]) / long_period

        # 전일 MA 계산 (마지막 원소 제외)
        prev_prices = prices[:-1]
        prev_short_ma = sum(prev_prices[-short_period:]) / short_period
        prev_long_ma = sum(prev_prices[-long_period:]) / long_period

        # 골든크로스: 전일 단기 < 장기, 당일 단기 >= 장기
        if prev_short_ma < prev_long_ma and today_short_ma >= today_long_ma:
            return "golden_cross"

        # 데드크로스: 전일 단기 >= 장기, 당일 단기 < 장기
        if prev_short_ma >= prev_long_ma and today_short_ma < today_long_ma:
            return "dead_cross"

        return None
