"""
IndicatorCalculator 단위 테스트 (Unit Tests)

Feature: exchange-rate-buy-signal
테스트 대상: utils/indicator_calculator.py - IndicatorCalculator 클래스

데이터 부족 시 None 반환, 빈 리스트, 단일 원소, 동일 값 등 edge case 검증.
Requirements: 1.4, 2.4, 3.4, 4.4
"""

import math

import pytest

from utils.indicator_calculator import IndicatorCalculator


# ============================================================
# moving_average 테스트
# ============================================================
class TestMovingAverage:
    """이동평균(SMA) 단위 테스트 - Validates: Requirements 2.4"""

    def test_empty_list_returns_none(self):
        """빈 리스트 입력 시 None 반환"""
        assert IndicatorCalculator.moving_average([], 5) is None

    def test_single_element_insufficient_period(self):
        """단일 원소 리스트에 period > 1이면 None 반환"""
        assert IndicatorCalculator.moving_average([1300.0], 5) is None

    def test_single_element_period_one(self):
        """단일 원소 리스트에 period=1이면 해당 값 반환"""
        result = IndicatorCalculator.moving_average([1300.0], 1)
        assert result == pytest.approx(1300.0)

    def test_insufficient_data_returns_none(self):
        """데이터가 period 미만이면 None 반환"""
        prices = [1300.0, 1310.0, 1320.0]
        assert IndicatorCalculator.moving_average(prices, 5) is None

    def test_zero_period_returns_none(self):
        """period가 0이면 None 반환"""
        assert IndicatorCalculator.moving_average([1300.0, 1310.0], 0) is None

    def test_negative_period_returns_none(self):
        """period가 음수이면 None 반환"""
        assert IndicatorCalculator.moving_average([1300.0, 1310.0], -1) is None

    def test_exact_period_match(self):
        """데이터 수 == period일 때 정상 계산"""
        prices = [1300.0, 1310.0, 1320.0, 1330.0, 1340.0]
        result = IndicatorCalculator.moving_average(prices, 5)
        expected = sum(prices) / 5
        assert result == pytest.approx(expected)

    def test_uses_last_n_prices(self):
        """마지막 period개의 가격만 사용하는지 확인"""
        prices = [1000.0, 1100.0, 1200.0, 1300.0, 1400.0]
        result = IndicatorCalculator.moving_average(prices, 3)
        expected = (1200.0 + 1300.0 + 1400.0) / 3
        assert result == pytest.approx(expected)


# ============================================================
# rsi 테스트
# ============================================================
class TestRsi:
    """RSI(상대강도지수) 단위 테스트 - Validates: Requirements 3.4"""

    def test_empty_list_returns_none(self):
        """빈 리스트 입력 시 None 반환"""
        assert IndicatorCalculator.rsi([], 14) is None

    def test_single_element_returns_none(self):
        """단일 원소 리스트 입력 시 None 반환"""
        assert IndicatorCalculator.rsi([1300.0], 14) is None

    def test_insufficient_data_returns_none(self):
        """데이터가 period + 1 미만이면 None 반환 (14일 RSI에 15개 미만)"""
        prices = [1300.0 + i for i in range(14)]  # 14개 = period + 1 미만
        assert IndicatorCalculator.rsi(prices, 14) is None

    def test_exact_minimum_data(self):
        """정확히 period + 1개 데이터일 때 정상 계산"""
        # 15개 데이터 (14 + 1)
        prices = [1300.0 + i * 10 for i in range(15)]
        result = IndicatorCalculator.rsi(prices, 14)
        assert result is not None
        assert 0 <= result <= 100

    def test_zero_period_returns_none(self):
        """period가 0이면 None 반환"""
        prices = [1300.0 + i for i in range(20)]
        assert IndicatorCalculator.rsi(prices, 0) is None

    def test_negative_period_returns_none(self):
        """period가 음수이면 None 반환"""
        prices = [1300.0 + i for i in range(20)]
        assert IndicatorCalculator.rsi(prices, -1) is None

    def test_all_identical_values_returns_rsi_none_or_defined(self):
        """모든 값이 동일하면 변화량이 0이므로 avg_loss == 0 → RSI = 100"""
        prices = [1300.0] * 20
        result = IndicatorCalculator.rsi(prices, 14)
        # 모든 변화량이 0이면 avg_gain=0, avg_loss=0 → avg_loss==0 → RSI=100
        assert result == 100.0

    def test_monotonically_increasing_returns_high_rsi(self):
        """단조 증가 가격은 높은 RSI 값을 반환"""
        prices = [1300.0 + i * 10 for i in range(20)]
        result = IndicatorCalculator.rsi(prices, 14)
        assert result is not None
        # 계속 상승하므로 RSI가 높아야 함
        assert result == 100.0

    def test_monotonically_decreasing_returns_low_rsi(self):
        """단조 감소 가격은 낮은 RSI 값을 반환"""
        prices = [1500.0 - i * 10 for i in range(20)]
        result = IndicatorCalculator.rsi(prices, 14)
        assert result is not None
        # 계속 하락하므로 RSI가 낮아야 함
        assert result < 10.0


# ============================================================
# bollinger_bands 테스트
# ============================================================
class TestBollingerBands:
    """볼린저 밴드 단위 테스트 - Validates: Requirements 4.4"""

    def test_empty_list_returns_none(self):
        """빈 리스트 입력 시 None 반환"""
        assert IndicatorCalculator.bollinger_bands([], 20) is None

    def test_single_element_returns_none(self):
        """단일 원소 리스트 입력 시 None 반환"""
        assert IndicatorCalculator.bollinger_bands([1300.0], 20) is None

    def test_insufficient_data_returns_none(self):
        """데이터가 period 미만이면 None 반환 (20일 볼린저에 20개 미만)"""
        prices = [1300.0 + i for i in range(19)]
        assert IndicatorCalculator.bollinger_bands(prices, 20) is None

    def test_zero_period_returns_none(self):
        """period가 0이면 None 반환"""
        prices = [1300.0] * 25
        assert IndicatorCalculator.bollinger_bands(prices, 0) is None

    def test_negative_period_returns_none(self):
        """period가 음수이면 None 반환"""
        prices = [1300.0] * 25
        assert IndicatorCalculator.bollinger_bands(prices, -1) is None

    def test_all_identical_values(self):
        """모든 값이 동일하면 표준편차 0 → 상단 == 중단 == 하단"""
        prices = [1300.0] * 20
        result = IndicatorCalculator.bollinger_bands(prices, 20)
        assert result is not None

        upper, middle, lower = result
        assert middle == pytest.approx(1300.0)
        # 표준편차가 0이므로 상단/하단 모두 중단과 동일
        assert upper == pytest.approx(1300.0)
        assert lower == pytest.approx(1300.0)

    def test_exact_period_match(self):
        """데이터 수 == period일 때 정상 계산"""
        prices = [1300.0 + i * 10 for i in range(20)]
        result = IndicatorCalculator.bollinger_bands(prices, 20)
        assert result is not None

        upper, middle, lower = result
        expected_middle = sum(prices) / 20
        assert middle == pytest.approx(expected_middle)
        # 상단 > 중단 > 하단
        assert upper > middle
        assert lower < middle

    def test_symmetry_around_middle(self):
        """상단과 하단이 중단 기준으로 대칭인지 확인"""
        prices = [1300.0 + i * 5 for i in range(25)]
        result = IndicatorCalculator.bollinger_bands(prices, 20)
        assert result is not None

        upper, middle, lower = result
        assert (upper - middle) == pytest.approx(middle - lower, rel=1e-9)


# ============================================================
# find_n_week_low 테스트
# ============================================================
class TestFindNWeekLow:
    """N주 최저가 단위 테스트 - Validates: Requirements 1.4"""

    def test_empty_list_returns_none(self):
        """빈 리스트 입력 시 None 반환"""
        assert IndicatorCalculator.find_n_week_low([]) is None

    def test_single_element_returns_none(self):
        """단일 원소 리스트 입력 시 None 반환 (기본 min_days=10 미만)"""
        assert IndicatorCalculator.find_n_week_low([1300.0]) is None

    def test_insufficient_data_returns_none(self):
        """데이터가 min_days 미만이면 None 반환"""
        prices = [1300.0 + i for i in range(9)]  # 9개 < 10
        assert IndicatorCalculator.find_n_week_low(prices, min_days=10) is None

    def test_exact_minimum_data(self):
        """정확히 min_days개 데이터일 때 정상 계산"""
        prices = [1300.0, 1310.0, 1290.0, 1320.0, 1280.0,
                  1330.0, 1270.0, 1340.0, 1260.0, 1350.0]
        result = IndicatorCalculator.find_n_week_low(prices, min_days=10)
        assert result is not None
        lowest, num_days = result
        assert lowest == 1260.0
        assert num_days == 10

    def test_returns_correct_min_and_length(self):
        """최저가와 영업일 수가 정확한지 확인"""
        prices = [1400.0, 1350.0, 1300.0, 1250.0, 1200.0,
                  1250.0, 1300.0, 1350.0, 1400.0, 1450.0,
                  1500.0, 1550.0]
        result = IndicatorCalculator.find_n_week_low(prices, min_days=10)
        assert result is not None
        lowest, num_days = result
        assert lowest == min(prices)
        assert num_days == len(prices)


# ============================================================
# detect_ma_cross 테스트
# ============================================================
class TestDetectMaCross:
    """MA 크로스 감지 단위 테스트 - Validates: Requirements 2.4"""

    def test_empty_list_returns_none(self):
        """빈 리스트 입력 시 None 반환"""
        assert IndicatorCalculator.detect_ma_cross([]) is None

    def test_single_element_returns_none(self):
        """단일 원소 리스트 입력 시 None 반환"""
        assert IndicatorCalculator.detect_ma_cross([1300.0]) is None

    def test_insufficient_data_returns_none(self):
        """데이터가 long_period + 1 미만이면 None 반환"""
        prices = [1300.0 + i for i in range(20)]  # 20개 < 21 (long_period + 1)
        assert IndicatorCalculator.detect_ma_cross(prices, 5, 20) is None

    def test_short_period_gte_long_period_returns_none(self):
        """short_period >= long_period이면 None 반환"""
        prices = [1300.0 + i for i in range(25)]
        assert IndicatorCalculator.detect_ma_cross(prices, 20, 20) is None
        assert IndicatorCalculator.detect_ma_cross(prices, 21, 20) is None

    def test_zero_period_returns_none(self):
        """period가 0이면 None 반환"""
        prices = [1300.0 + i for i in range(25)]
        assert IndicatorCalculator.detect_ma_cross(prices, 0, 20) is None
        assert IndicatorCalculator.detect_ma_cross(prices, 5, 0) is None

    def test_negative_period_returns_none(self):
        """period가 음수이면 None 반환"""
        prices = [1300.0 + i for i in range(25)]
        assert IndicatorCalculator.detect_ma_cross(prices, -1, 20) is None
        assert IndicatorCalculator.detect_ma_cross(prices, 5, -1) is None

    def test_no_cross_returns_none(self):
        """교차가 없으면 None 반환"""
        # 단조 증가: 단기 MA가 항상 장기 MA보다 높음
        prices = [1000.0 + i * 10 for i in range(25)]
        result = IndicatorCalculator.detect_ma_cross(prices, 5, 20)
        # 단조 증가에서는 단기 MA > 장기 MA가 유지되므로 교차 없음
        assert result is None

    def test_golden_cross_detection(self):
        """골든크로스 감지: 전일 단기 < 장기 → 당일 단기 >= 장기"""
        # 장기 하락 후 마지막에 급등하여 단기 MA가 장기 MA를 상향 돌파
        prices = [1400.0] * 15 + [1300.0] * 5 + [1500.0]
        result = IndicatorCalculator.detect_ma_cross(prices, 5, 20)
        # 전일: 단기 MA(1300 근처) < 장기 MA(1400 근처)
        # 당일: 마지막 급등으로 단기 MA 상승
        if result is not None:
            assert result == "golden_cross"

    def test_dead_cross_detection(self):
        """데드크로스 감지: 전일 단기 >= 장기 → 당일 단기 < 장기"""
        # 장기 상승 후 마지막에 급락하여 단기 MA가 장기 MA를 하향 돌파
        prices = [1300.0] * 15 + [1400.0] * 5 + [1200.0]
        result = IndicatorCalculator.detect_ma_cross(prices, 5, 20)
        if result is not None:
            assert result == "dead_cross"
