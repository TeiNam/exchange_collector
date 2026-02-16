"""
IndicatorCalculator 속성 기반 테스트 (Property-Based Tests)

Feature: exchange-rate-buy-signal
테스트 대상: utils/indicator_calculator.py - IndicatorCalculator 클래스
"""

import math

import pytest
from hypothesis import given, settings, assume
from hypothesis import strategies as st

from utils.indicator_calculator import IndicatorCalculator


# === 전략(Strategy) 정의 ===

# 양수 가격 전략 (환율 범위에 맞는 현실적인 양수)
positive_price = st.floats(min_value=0.01, max_value=10000.0, allow_nan=False, allow_infinity=False)

# 10개 이상의 양수 가격 리스트 (N주 최저가용)
prices_for_n_week_low = st.lists(positive_price, min_size=10, max_size=50)

# 20개 이상의 양수 가격 리스트 (볼린저 밴드용)
prices_for_bollinger = st.lists(positive_price, min_size=20, max_size=50)

# 15개 이상의 양수 가격 리스트 (RSI용)
prices_for_rsi = st.lists(positive_price, min_size=15, max_size=50)

# 이동평균 기간 전략
ma_period = st.integers(min_value=1, max_value=20)


class TestNWeekLowAccuracy:
    """
    Property 1: N주 최저가 산출 정확성

    For any 10개 이상의 양수로 구성된 가격 리스트에 대해,
    find_n_week_low가 반환하는 최저가는 해당 리스트의 실제 최솟값(min())과
    동일해야 하며, 반환되는 영업일 수는 리스트의 길이와 동일해야 한다.

    Feature: exchange-rate-buy-signal, Property 1: N주 최저가 산출 정확성
    **Validates: Requirements 1.1**
    """

    @given(prices=prices_for_n_week_low)
    @settings(max_examples=100)
    def test_n_week_low_equals_min(self, prices):
        """find_n_week_low 결과의 최저가가 min(prices)와 동일한지 검증"""
        result = IndicatorCalculator.find_n_week_low(prices)

        # 10개 이상이므로 None이 아니어야 함
        assert result is not None, "10개 이상의 데이터에서 None이 반환되었습니다"

        lowest, num_days = result

        # 최저가 == min(prices)
        assert lowest == min(prices), (
            f"최저가 불일치: find_n_week_low={lowest}, min(prices)={min(prices)}"
        )

        # 영업일 수 == len(prices)
        assert num_days == len(prices), (
            f"영업일 수 불일치: find_n_week_low={num_days}, len(prices)={len(prices)}"
        )


class TestMovingAverageAccuracy:
    """
    Property 2: 이동평균 계산 정확성

    For any N개 이상의 양수로 구성된 가격 리스트와 기간 N에 대해,
    moving_average(prices, N)의 결과는 리스트의 마지막 N개 원소의
    산술 평균(sum(prices[-N:]) / N)과 동일해야 한다.

    Feature: exchange-rate-buy-signal, Property 2: 이동평균 계산 정확성
    **Validates: Requirements 2.1**
    """

    @given(
        prices=st.lists(positive_price, min_size=1, max_size=50),
        period=ma_period,
    )
    @settings(max_examples=100)
    def test_moving_average_equals_arithmetic_mean(self, prices, period):
        """moving_average 결과가 마지막 N개의 산술 평균과 동일한지 검증"""
        # 가격 리스트가 period 이상인 경우만 테스트
        assume(len(prices) >= period)

        result = IndicatorCalculator.moving_average(prices, period)

        assert result is not None, f"충분한 데이터({len(prices)}개)에서 None이 반환되었습니다"

        expected = sum(prices[-period:]) / period

        assert result == pytest.approx(expected, rel=1e-9), (
            f"이동평균 불일치: moving_average={result}, expected={expected}"
        )


class TestMaCrossAccuracy:
    """
    Property 3: MA 크로스 감지 정확성

    For any 충분한 길이의 가격 리스트에 대해,
    detect_ma_cross가 "golden_cross"를 반환하면
    전일 단기 MA < 전일 장기 MA이고 당일 단기 MA >= 당일 장기 MA이어야 하며,
    "dead_cross"를 반환하면
    전일 단기 MA >= 전일 장기 MA이고 당일 단기 MA < 당일 장기 MA이어야 한다.

    Feature: exchange-rate-buy-signal, Property 3: MA 크로스 감지 정확성
    **Validates: Requirements 2.2, 2.3**
    """

    @given(
        prices=st.lists(positive_price, min_size=21, max_size=60),
    )
    @settings(max_examples=200)
    def test_ma_cross_conditions(self, prices):
        """detect_ma_cross 반환값이 MA 교차 조건과 일치하는지 검증"""
        short_period = 5
        long_period = 20

        result = IndicatorCalculator.detect_ma_cross(prices, short_period, long_period)

        # 당일 MA 계산
        today_short_ma = sum(prices[-short_period:]) / short_period
        today_long_ma = sum(prices[-long_period:]) / long_period

        # 전일 MA 계산 (마지막 원소 제외)
        prev_prices = prices[:-1]
        prev_short_ma = sum(prev_prices[-short_period:]) / short_period
        prev_long_ma = sum(prev_prices[-long_period:]) / long_period

        if result == "golden_cross":
            # 골든크로스: 전일 단기 < 장기, 당일 단기 >= 장기
            assert prev_short_ma < prev_long_ma, (
                f"골든크로스인데 전일 단기 MA({prev_short_ma}) >= 전일 장기 MA({prev_long_ma})"
            )
            assert today_short_ma >= today_long_ma, (
                f"골든크로스인데 당일 단기 MA({today_short_ma}) < 당일 장기 MA({today_long_ma})"
            )

        elif result == "dead_cross":
            # 데드크로스: 전일 단기 >= 장기, 당일 단기 < 장기
            assert prev_short_ma >= prev_long_ma, (
                f"데드크로스인데 전일 단기 MA({prev_short_ma}) < 전일 장기 MA({prev_long_ma})"
            )
            assert today_short_ma < today_long_ma, (
                f"데드크로스인데 당일 단기 MA({today_short_ma}) >= 당일 장기 MA({today_long_ma})"
            )


class TestRsiRangeInvariance:
    """
    Property 4: RSI 범위 불변성

    For any 15개 이상의 양수로 구성된 가격 리스트에 대해,
    rsi(prices, 14)의 결과는 항상 0 이상 100 이하의 값이어야 한다.

    Feature: exchange-rate-buy-signal, Property 4: RSI 범위 불변성
    **Validates: Requirements 3.1**
    """

    @given(prices=prices_for_rsi)
    @settings(max_examples=100)
    def test_rsi_within_range(self, prices):
        """RSI 값이 항상 0~100 범위 내에 있는지 검증"""
        result = IndicatorCalculator.rsi(prices, period=14)

        # 15개 이상이므로 None이 아니어야 함
        assert result is not None, "15개 이상의 데이터에서 None이 반환되었습니다"

        assert 0 <= result <= 100, (
            f"RSI 값이 범위를 벗어났습니다: rsi={result}"
        )


class TestBollingerBandsAccuracy:
    """
    Property 5: 볼린저 밴드 계산 정확성

    For any 20개 이상의 양수로 구성된 가격 리스트에 대해,
    bollinger_bands가 반환하는 (상단, 중단, 하단) 값은
    중단 = 마지막 20개의 산술 평균,
    상단 = 중단 + 2 * 표준편차,
    하단 = 중단 - 2 * 표준편차와 동일해야 한다.

    Feature: exchange-rate-buy-signal, Property 5: 볼린저 밴드 계산 정확성
    **Validates: Requirements 4.1**
    """

    @given(prices=prices_for_bollinger)
    @settings(max_examples=100)
    def test_bollinger_bands_calculation(self, prices):
        """볼린저 밴드 값이 산술 평균 ± 2*표준편차와 동일한지 검증"""
        period = 20
        num_std = 2.0

        result = IndicatorCalculator.bollinger_bands(prices, period, num_std)

        assert result is not None, "20개 이상의 데이터에서 None이 반환되었습니다"

        upper, middle, lower = result

        # 기대값 계산
        recent = prices[-period:]
        expected_middle = sum(recent) / period
        variance = sum((p - expected_middle) ** 2 for p in recent) / period
        expected_std = math.sqrt(variance)
        expected_upper = expected_middle + num_std * expected_std
        expected_lower = expected_middle - num_std * expected_std

        # 중단 == 산술 평균
        assert middle == pytest.approx(expected_middle, rel=1e-9), (
            f"중단 불일치: middle={middle}, expected={expected_middle}"
        )

        # 상단 == 중단 + 2 * std
        assert upper == pytest.approx(expected_upper, rel=1e-9), (
            f"상단 불일치: upper={upper}, expected={expected_upper}"
        )

        # 하단 == 중단 - 2 * std
        assert lower == pytest.approx(expected_lower, rel=1e-9), (
            f"하단 불일치: lower={lower}, expected={expected_lower}"
        )


class TestBollingerBandsSymmetry:
    """
    Property 6: 볼린저 밴드 대칭성

    For any 20개 이상의 양수로 구성된 가격 리스트에 대해,
    bollinger_bands가 반환하는 상단과 하단은 중단을 기준으로 대칭이어야 한다.
    즉, 상단 - 중단 == 중단 - 하단이어야 한다.

    Feature: exchange-rate-buy-signal, Property 6: 볼린저 밴드 대칭성
    **Validates: Requirements 4.1**
    """

    @given(prices=prices_for_bollinger)
    @settings(max_examples=100)
    def test_bollinger_bands_symmetry(self, prices):
        """볼린저 밴드 상단/하단이 중단 기준으로 대칭인지 검증"""
        result = IndicatorCalculator.bollinger_bands(prices)

        assert result is not None, "20개 이상의 데이터에서 None이 반환되었습니다"

        upper, middle, lower = result

        upper_diff = upper - middle
        lower_diff = middle - lower

        assert upper_diff == pytest.approx(lower_diff, rel=1e-9), (
            f"볼린저 밴드 비대칭: 상단-중단={upper_diff}, 중단-하단={lower_diff}"
        )
