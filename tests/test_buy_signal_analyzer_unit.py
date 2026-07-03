"""
BuySignalAnalyzer 단위 테스트 (저가매기 전략)

Mock DB connector를 사용하여 이격도/백분위/볼린저하단/N개월최저가/RSI과매도
신호 생성, 오류 격리, 데이터 부족 처리 등을 검증한다.
"""

from decimal import Decimal

import pytest
from unittest.mock import MagicMock

from utils.buy_signal_analyzer import BuySignalAnalyzer, Signal


def _make_mock_db(rates: list[float]):
    """
    Mock DB connector를 생성한다.
    get_recent_rates가 내부적으로 DB 결과를 역순 정렬하므로,
    rates(오래된 순)를 역순으로 cursor.fetchall에 넣어준다.
    """
    mock_db = MagicMock()
    mock_conn = MagicMock()
    mock_cursor = MagicMock()
    mock_db.get_connection.return_value = mock_conn
    mock_conn.cursor.return_value = mock_cursor
    # DB는 최신순(DESC)으로 반환하므로, 오래된 순 rates를 역순으로 설정
    mock_cursor.fetchall.return_value = [(r,) for r in reversed(rates)]
    return mock_db


def _make_mock_db_per_currency(rates_map: dict[str, list[float]]):
    """통화별로 다른 데이터를 반환하는 Mock DB connector를 생성한다."""
    mock_db = MagicMock()
    mock_conn = MagicMock()
    mock_db.get_connection.return_value = mock_conn

    def make_cursor():
        cursor = MagicMock()
        captured = {}

        def execute_side_effect(query, params):
            captured["currency"] = params[0]

        cursor.execute.side_effect = execute_side_effect

        def fetchall_side_effect():
            currency = captured.get("currency", "")
            rates = rates_map.get(currency, [])
            return [(r,) for r in reversed(rates)]

        cursor.fetchall.side_effect = fetchall_side_effect
        return cursor

    mock_conn.cursor.side_effect = lambda: make_cursor()
    return mock_db


class TestNMonthLowSignal:
    """N개월 최저가 신호 생성 테스트"""

    def test_n_month_low_signal_generated(self):
        """오늘 환율이 과거 최저가 이하이면 n_month_low 신호를 생성한다"""
        # 과거 데이터의 최저가 1400.0, 오늘 환율 1395.0 (최저가 이하)
        # history는 rates[:-1]이므로 마지막 원소는 제외됨 → 25개 제공
        rates = [1420.0, 1415.0, 1410.0, 1405.0, 1400.0,
                 1410.0, 1415.0, 1420.0, 1425.0, 1430.0,
                 1425.0, 1420.0, 1415.0, 1410.0, 1405.0,
                 1410.0, 1415.0, 1420.0, 1425.0, 1430.0,
                 1425.0, 1420.0, 1418.0, 1416.0, 1414.0]
        mock_db = _make_mock_db(rates)
        analyzer = BuySignalAnalyzer(mock_db)

        signals = analyzer.analyze_currency("USD", 1395.0)

        low_signals = [s for s in signals if s.signal_type == "n_month_low"]
        assert len(low_signals) == 1
        assert low_signals[0].currency == "USD"
        assert low_signals[0].current_rate == 1395.0
        assert low_signals[0].indicator_value == 1400.0

    def test_n_month_low_not_generated_when_rate_above(self):
        """오늘 환율이 과거 최저가보다 높으면 n_month_low 신호를 생성하지 않는다"""
        rates = [1400.0] * 25
        mock_db = _make_mock_db(rates)
        analyzer = BuySignalAnalyzer(mock_db)

        signals = analyzer.analyze_currency("USD", 1450.0)

        low_signals = [s for s in signals if s.signal_type == "n_month_low"]
        assert len(low_signals) == 0


class TestDisparityLowSignal:
    """이격도 저평가 신호 생성 테스트"""

    def test_disparity_low_signal_generated(self):
        """오늘 환율이 장기 평균 대비 임계값 이하이면 disparity_low 신호를 생성한다"""
        # 60일 평균 1500 근처, 오늘 1400 → 이격도 약 93% (<98)
        rates = [1500.0] * 60
        mock_db = _make_mock_db(rates)
        analyzer = BuySignalAnalyzer(mock_db)

        signals = analyzer.analyze_currency("USD", 1400.0)

        disp = [s for s in signals if s.signal_type == "disparity_low"]
        assert len(disp) == 1
        assert disp[0].indicator_value is not None
        assert disp[0].indicator_value <= BuySignalAnalyzer.DISPARITY_THRESHOLD

    def test_disparity_not_generated_when_near_average(self):
        """오늘 환율이 평균과 비슷하면 disparity_low 신호를 생성하지 않는다"""
        rates = [1500.0] * 60
        mock_db = _make_mock_db(rates)
        analyzer = BuySignalAnalyzer(mock_db)

        signals = analyzer.analyze_currency("USD", 1500.0)  # 이격도 100

        disp = [s for s in signals if s.signal_type == "disparity_low"]
        assert len(disp) == 0


class TestPercentileLowSignal:
    """백분위(최저가권) 신호 생성 테스트"""

    def test_percentile_low_signal_generated(self):
        """오늘 환율이 기간 하위 백분위 이내이면 percentile_low 신호를 생성한다"""
        # 1410~1500 범위의 데이터, 오늘 1405 → 거의 모든 값보다 낮음 (하위 0%)
        rates = [1410.0 + i for i in range(30)]
        mock_db = _make_mock_db(rates)
        analyzer = BuySignalAnalyzer(mock_db)

        signals = analyzer.analyze_currency("USD", 1405.0)

        pct = [s for s in signals if s.signal_type == "percentile_low"]
        assert len(pct) == 1
        assert pct[0].indicator_value is not None
        assert pct[0].indicator_value <= BuySignalAnalyzer.PERCENTILE_THRESHOLD

    def test_percentile_not_generated_when_high(self):
        """오늘 환율이 기간 상위권이면 percentile_low 신호를 생성하지 않는다"""
        rates = [1410.0 + i for i in range(30)]
        mock_db = _make_mock_db(rates)
        analyzer = BuySignalAnalyzer(mock_db)

        signals = analyzer.analyze_currency("USD", 1500.0)  # 거의 최고가

        pct = [s for s in signals if s.signal_type == "percentile_low"]
        assert len(pct) == 0


class TestBollingerLowSignal:
    """볼린저 밴드 하단 터치 신호 생성 테스트"""

    def test_bollinger_low_signal_generated(self):
        """오늘 환율이 볼린저 밴드 하단 이하이면 bollinger_low 신호를 생성한다"""
        rates = [1400.0 + (i % 3) for i in range(30)]
        mock_db = _make_mock_db(rates)
        analyzer = BuySignalAnalyzer(mock_db)

        signals = analyzer.analyze_currency("USD", 1390.0)

        bb_signals = [s for s in signals if s.signal_type == "bollinger_low"]
        assert len(bb_signals) == 1
        assert bb_signals[0].currency == "USD"
        assert bb_signals[0].indicator_value is not None


class TestRsiOversoldSignal:
    """RSI 과매도 신호 생성 테스트"""

    def test_rsi_oversold_signal_generated(self):
        """RSI가 30 이하이면 rsi_oversold 신호를 생성한다"""
        rates = [1500.0 - i * 10.0 for i in range(30)]
        mock_db = _make_mock_db(rates)
        analyzer = BuySignalAnalyzer(mock_db)

        signals = analyzer.analyze_currency("USD", 1200.0)

        rsi_signals = [s for s in signals if s.signal_type == "rsi_oversold"]
        assert len(rsi_signals) == 1
        assert rsi_signals[0].indicator_value is not None
        assert rsi_signals[0].indicator_value <= 30


class TestDecimalTodayRate:
    """DB에서 넘어오는 Decimal today_rate 처리 테스트 (회귀 방지)"""

    def test_decimal_today_rate_does_not_raise(self):
        """today_rate가 Decimal이어도 타입 에러 없이 분석된다"""
        # 60일 평균 1500, 오늘 Decimal(1400) → 이격도/RSI 계산이 float과 혼합됨
        rates = [1500.0] * 60
        mock_db = _make_mock_db(rates)
        analyzer = BuySignalAnalyzer(mock_db)

        # Decimal 입력이 float 리스트와 연산돼도 예외가 나면 안 됨
        signals = analyzer.analyze_currency("USD", Decimal("1400.00"))

        # 저가이므로 최소 이격도 신호는 나와야 하고, current_rate는 float
        assert any(s.signal_type == "disparity_low" for s in signals)
        assert all(isinstance(s.current_rate, float) for s in signals)


class TestNoOverboughtOrCrossSignals:
    """저가매기 전략은 과매수/크로스 신호를 생성하지 않는다"""

    def test_no_overbought_or_cross_signal_types(self):
        """상승 추세 데이터에도 과매수/골든/데드 크로스 신호가 없어야 한다"""
        rates = [1300.0 + i * 10.0 for i in range(60)]
        mock_db = _make_mock_db(rates)
        analyzer = BuySignalAnalyzer(mock_db)

        signals = analyzer.analyze_currency("USD", 1900.0)

        types = {s.signal_type for s in signals}
        assert "rsi_overbought" not in types
        assert "golden_cross" not in types
        assert "dead_cross" not in types
        assert "bollinger_high" not in types


class TestCurrencyIsolation:
    """한 통화 분석 실패 시 다른 통화 정상 분석 확인 테스트"""

    def test_usd_failure_does_not_affect_jpy(self):
        """USD 분석 중 예외가 발생해도 JPY(100) 분석은 정상 수행된다"""
        # JPY(100)이 최저가 신호를 내도록 오늘값보다 높은 과거 데이터
        jpy_rates = [960.0] * 30
        rates_map = {"USD": [], "JPY(100)": jpy_rates}
        mock_db = _make_mock_db_per_currency(rates_map)
        analyzer = BuySignalAnalyzer(mock_db)

        original_analyze = analyzer.analyze_currency

        def patched_analyze(currency, today_rate):
            if currency == "USD":
                raise RuntimeError("USD 분석 실패 시뮬레이션")
            return original_analyze(currency, today_rate)

        analyzer.analyze_currency = patched_analyze

        today_rates = {"USD": 1400.0, "JPY(100)": 940.0}
        signals = analyzer.analyze(today_rates)

        jpy_signals = [s for s in signals if s.currency == "JPY(100)"]
        assert len(jpy_signals) > 0

    def test_jpy_failure_does_not_affect_usd(self):
        """JPY(100) 분석 중 예외가 발생해도 USD 분석은 정상 수행된다"""
        usd_rates = [1450.0] * 30
        rates_map = {"USD": usd_rates, "JPY(100)": []}
        mock_db = _make_mock_db_per_currency(rates_map)
        analyzer = BuySignalAnalyzer(mock_db)

        original_analyze = analyzer.analyze_currency

        def patched_analyze(currency, today_rate):
            if currency == "JPY(100)":
                raise RuntimeError("JPY 분석 실패 시뮬레이션")
            return original_analyze(currency, today_rate)

        analyzer.analyze_currency = patched_analyze

        today_rates = {"USD": 1400.0, "JPY(100)": 940.0}
        signals = analyzer.analyze(today_rates)

        usd_signals = [s for s in signals if s.currency == "USD"]
        assert len(usd_signals) > 0


class TestInsufficientData:
    """데이터 부족 시 해당 지표 건너뛰기 확인 테스트"""

    def test_insufficient_data_skips_all_indicators(self):
        """데이터가 부족하면 모든 지표를 건너뛰고 빈 신호 리스트를 반환한다"""
        rates = [1400.0, 1405.0, 1410.0, 1415.0, 1420.0]
        mock_db = _make_mock_db(rates)
        analyzer = BuySignalAnalyzer(mock_db)

        signals = analyzer.analyze_currency("USD", 1395.0)

        assert len(signals) == 0

    def test_partial_data_skips_disparity(self):
        """이격도 기간(60일) 미만이면 disparity_low 신호는 생성되지 않는다"""
        # 25개: 백분위/최저가/볼린저/RSI는 가능하나 이격도(60)는 불가
        rates = [1500.0 - i * 2.0 for i in range(25)]
        mock_db = _make_mock_db(rates)
        analyzer = BuySignalAnalyzer(mock_db)

        signals = analyzer.analyze_currency("USD", 1400.0)

        assert "disparity_low" not in {s.signal_type for s in signals}


class TestMissingCurrencyInTodayRates:
    """today_rates에 통화가 없으면 건너뛰기 테스트"""

    def test_missing_currency_skipped(self):
        """today_rates에 해당 통화가 없으면 분석을 건너뛴다"""
        mock_db = _make_mock_db([1400.0] * 30)
        analyzer = BuySignalAnalyzer(mock_db)

        today_rates = {"USD": 1400.0}
        signals = analyzer.analyze(today_rates)

        jpy_signals = [s for s in signals if s.currency == "JPY(100)"]
        assert len(jpy_signals) == 0

    def test_empty_today_rates(self):
        """today_rates가 비어있으면 빈 신호 리스트를 반환한다"""
        mock_db = _make_mock_db([])
        analyzer = BuySignalAnalyzer(mock_db)

        signals = analyzer.analyze({})

        assert signals == []

    def test_unknown_currency_in_today_rates(self):
        """TARGET_CURRENCIES에 없는 통화는 무시된다"""
        mock_db = _make_mock_db([1400.0] * 30)
        analyzer = BuySignalAnalyzer(mock_db)

        today_rates = {"EUR": 1500.0}
        signals = analyzer.analyze(today_rates)

        assert signals == []
