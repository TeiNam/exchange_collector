"""
BuySignalAnalyzer 단위 테스트

Mock DB connector를 사용하여 BuySignalAnalyzer의 각 신호 유형 생성,
오류 격리, 데이터 부족 처리 등을 검증한다.
"""

import pytest
from unittest.mock import MagicMock, patch

from utils.buy_signal_analyzer import BuySignalAnalyzer, Signal


def _make_mock_db(rates: list[float]):
    """
    Mock DB connector를 생성한다.
    get_recent_rates가 내부적으로 DB 결과를 역순 정렬하므로,
    rates를 역순으로 cursor.fetchall에 넣어준다.
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
    """
    통화별로 다른 데이터를 반환하는 Mock DB connector를 생성한다.
    cursor.execute 호출 시 currency 파라미터에 따라 다른 결과를 반환한다.
    """
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


class TestNWeekLowSignal:
    """N주 최저가 신호 생성 테스트"""

    def test_n_week_low_signal_generated(self):
        """오늘 환율이 최저가 이하이면 n_week_low 신호를 생성한다"""
        # 21개 데이터: 최저가 1400.0, 오늘 환율 1395.0 (최저가 이하)
        rates = [1420.0, 1415.0, 1410.0, 1405.0, 1400.0,
                 1410.0, 1415.0, 1420.0, 1425.0, 1430.0,
                 1425.0, 1420.0, 1415.0, 1410.0, 1405.0,
                 1410.0, 1415.0, 1420.0, 1425.0, 1430.0,
                 1425.0]
        mock_db = _make_mock_db(rates)
        analyzer = BuySignalAnalyzer(mock_db)

        signals = analyzer.analyze_currency("USD", 1395.0)

        n_week_signals = [s for s in signals if s.signal_type == "n_week_low"]
        assert len(n_week_signals) == 1
        assert n_week_signals[0].currency == "USD"
        assert n_week_signals[0].current_rate == 1395.0
        assert n_week_signals[0].indicator_value == 1400.0

    def test_n_week_low_not_generated_when_rate_above(self):
        """오늘 환율이 최저가보다 높으면 n_week_low 신호를 생성하지 않는다"""
        rates = [1400.0] * 21
        mock_db = _make_mock_db(rates)
        analyzer = BuySignalAnalyzer(mock_db)

        signals = analyzer.analyze_currency("USD", 1450.0)

        n_week_signals = [s for s in signals if s.signal_type == "n_week_low"]
        assert len(n_week_signals) == 0


class TestGoldenCrossSignal:
    """골든크로스 신호 생성 테스트"""

    def test_golden_cross_signal_generated(self):
        """단기 MA가 장기 MA를 상향 돌파하면 golden_cross 신호를 생성한다"""
        # 전일(rates[:-1]): 단기 MA(90) < 장기 MA(105) → 조건 충족
        # 당일(rates): 마지막 값 급등으로 단기 MA(172) >= 장기 MA(124.5)
        rates = [110.0] * 15 + [90.0, 90.0, 90.0, 90.0, 90.0, 500.0]
        mock_db = _make_mock_db(rates)
        analyzer = BuySignalAnalyzer(mock_db)

        signals = analyzer.analyze_currency("USD", 1400.0)

        gc_signals = [s for s in signals if s.signal_type == "golden_cross"]
        assert len(gc_signals) == 1
        assert gc_signals[0].currency == "USD"
        assert gc_signals[0].message == "골든크로스 발생 - 단기 MA가 장기 MA를 상향 돌파"


class TestDeadCrossSignal:
    """데드크로스 신호 생성 테스트"""

    def test_dead_cross_signal_generated(self):
        """단기 MA가 장기 MA를 하향 돌파하면 dead_cross 신호를 생성한다"""
        # 전일까지: 단기 >= 장기, 당일: 단기 < 장기
        # 높은 값들 뒤에 마지막에 급락
        rates = [120.0] * 16 + [120.0, 120.0, 120.0, 120.0, 100.0]
        mock_db = _make_mock_db(rates)
        analyzer = BuySignalAnalyzer(mock_db)

        signals = analyzer.analyze_currency("USD", 1400.0)

        dc_signals = [s for s in signals if s.signal_type == "dead_cross"]
        assert len(dc_signals) == 1
        assert dc_signals[0].currency == "USD"
        assert dc_signals[0].message == "데드크로스 발생 - 단기 MA가 장기 MA를 하향 돌파"


class TestRsiOversoldSignal:
    """RSI 과매도 신호 생성 테스트"""

    def test_rsi_oversold_signal_generated(self):
        """RSI가 30 이하이면 rsi_oversold 신호를 생성한다"""
        # 지속적으로 하락하는 데이터 → RSI가 낮아짐
        rates = [1500.0 - i * 10.0 for i in range(21)]
        mock_db = _make_mock_db(rates)
        analyzer = BuySignalAnalyzer(mock_db)

        signals = analyzer.analyze_currency("USD", 1300.0)

        rsi_signals = [s for s in signals if s.signal_type == "rsi_oversold"]
        assert len(rsi_signals) == 1
        assert rsi_signals[0].currency == "USD"
        assert rsi_signals[0].indicator_value is not None
        assert rsi_signals[0].indicator_value <= 30


class TestRsiOverboughtSignal:
    """RSI 과매수 신호 생성 테스트"""

    def test_rsi_overbought_signal_generated(self):
        """RSI가 70 이상이면 rsi_overbought 신호를 생성한다"""
        # 지속적으로 상승하는 데이터 → RSI가 높아짐
        rates = [1300.0 + i * 10.0 for i in range(21)]
        mock_db = _make_mock_db(rates)
        analyzer = BuySignalAnalyzer(mock_db)

        signals = analyzer.analyze_currency("USD", 1500.0)

        rsi_signals = [s for s in signals if s.signal_type == "rsi_overbought"]
        assert len(rsi_signals) == 1
        assert rsi_signals[0].currency == "USD"
        assert rsi_signals[0].indicator_value is not None
        assert rsi_signals[0].indicator_value >= 70


class TestBollingerLowSignal:
    """볼린저 밴드 하단 터치 신호 생성 테스트"""

    def test_bollinger_low_signal_generated(self):
        """오늘 환율이 볼린저 밴드 하단 이하이면 bollinger_low 신호를 생성한다"""
        # 안정적인 데이터 + 오늘 환율을 매우 낮게 설정
        rates = [1400.0 + (i % 3) for i in range(21)]
        mock_db = _make_mock_db(rates)
        analyzer = BuySignalAnalyzer(mock_db)

        # 볼린저 밴드 하단보다 훨씬 낮은 값
        signals = analyzer.analyze_currency("USD", 1390.0)

        bb_signals = [s for s in signals if s.signal_type == "bollinger_low"]
        assert len(bb_signals) == 1
        assert bb_signals[0].currency == "USD"
        assert bb_signals[0].indicator_value is not None


class TestBollingerHighSignal:
    """볼린저 밴드 상단 터치 신호 생성 테스트"""

    def test_bollinger_high_signal_generated(self):
        """오늘 환율이 볼린저 밴드 상단 이상이면 bollinger_high 신호를 생성한다"""
        # 안정적인 데이터 + 오늘 환율을 매우 높게 설정
        rates = [1400.0 + (i % 3) for i in range(21)]
        mock_db = _make_mock_db(rates)
        analyzer = BuySignalAnalyzer(mock_db)

        # 볼린저 밴드 상단보다 훨씬 높은 값
        signals = analyzer.analyze_currency("USD", 1420.0)

        bb_signals = [s for s in signals if s.signal_type == "bollinger_high"]
        assert len(bb_signals) == 1
        assert bb_signals[0].currency == "USD"
        assert bb_signals[0].indicator_value is not None


class TestCurrencyIsolation:
    """한 통화 분석 실패 시 다른 통화 정상 분석 확인 테스트"""

    def test_usd_failure_does_not_affect_jpy(self):
        """USD 분석 중 예외가 발생해도 JPY(100) 분석은 정상 수행된다"""
        # JPY(100)용 안정적인 데이터 (21개)
        jpy_rates = [950.0] * 21

        rates_map = {
            "USD": [],  # USD는 빈 데이터 (에러 유발은 아니지만 신호 없음)
            "JPY(100)": jpy_rates,
        }
        mock_db = _make_mock_db_per_currency(rates_map)
        analyzer = BuySignalAnalyzer(mock_db)

        # USD의 analyze_currency에서 예외를 발생시킨다
        original_analyze = analyzer.analyze_currency

        def patched_analyze(currency, today_rate):
            if currency == "USD":
                raise RuntimeError("USD 분석 실패 시뮬레이션")
            return original_analyze(currency, today_rate)

        analyzer.analyze_currency = patched_analyze

        today_rates = {"USD": 1400.0, "JPY(100)": 940.0}
        signals = analyzer.analyze(today_rates)

        # USD 예외에도 불구하고 JPY(100) 신호가 존재해야 한다
        jpy_signals = [s for s in signals if s.currency == "JPY(100)"]
        assert len(jpy_signals) > 0

    def test_jpy_failure_does_not_affect_usd(self):
        """JPY(100) 분석 중 예외가 발생해도 USD 분석은 정상 수행된다"""
        usd_rates = [1400.0] * 21

        rates_map = {
            "USD": usd_rates,
            "JPY(100)": [],
        }
        mock_db = _make_mock_db_per_currency(rates_map)
        analyzer = BuySignalAnalyzer(mock_db)

        original_analyze = analyzer.analyze_currency

        def patched_analyze(currency, today_rate):
            if currency == "JPY(100)":
                raise RuntimeError("JPY 분석 실패 시뮬레이션")
            return original_analyze(currency, today_rate)

        analyzer.analyze_currency = patched_analyze

        today_rates = {"USD": 1390.0, "JPY(100)": 940.0}
        signals = analyzer.analyze(today_rates)

        # JPY 예외에도 불구하고 USD 신호가 존재해야 한다
        usd_signals = [s for s in signals if s.currency == "USD"]
        assert len(usd_signals) > 0


class TestInsufficientData:
    """데이터 부족 시 해당 지표 건너뛰기 확인 테스트"""

    def test_insufficient_data_skips_all_indicators(self):
        """데이터가 부족하면 모든 지표를 건너뛰고 빈 신호 리스트를 반환한다"""
        # 5개 데이터만 제공 → 모든 지표에 데이터 부족
        rates = [1400.0, 1405.0, 1410.0, 1415.0, 1420.0]
        mock_db = _make_mock_db(rates)
        analyzer = BuySignalAnalyzer(mock_db)

        signals = analyzer.analyze_currency("USD", 1395.0)

        # 데이터 부족으로 어떤 신호도 생성되지 않아야 한다
        assert len(signals) == 0

    def test_partial_data_skips_some_indicators(self):
        """일부 지표에만 충분한 데이터가 있으면 해당 지표만 분석한다"""
        # 15개 데이터: N주 최저가(10일)와 RSI(15일)는 가능, MA크로스(21일)와 볼린저(20일)는 불가
        rates = [1500.0 - i * 5.0 for i in range(15)]
        mock_db = _make_mock_db(rates)
        analyzer = BuySignalAnalyzer(mock_db)

        # 최저가보다 낮은 오늘 환율 → n_week_low 신호 기대
        today_rate = 1400.0
        signals = analyzer.analyze_currency("USD", today_rate)

        # N주 최저가 신호는 생성 가능 (10일 이상 데이터 있음)
        signal_types = [s.signal_type for s in signals]
        # MA 크로스와 볼린저 밴드는 데이터 부족으로 생성 불가
        assert "golden_cross" not in signal_types
        assert "dead_cross" not in signal_types
        assert "bollinger_low" not in signal_types
        assert "bollinger_high" not in signal_types


class TestMissingCurrencyInTodayRates:
    """today_rates에 통화가 없으면 건너뛰기 테스트"""

    def test_missing_currency_skipped(self):
        """today_rates에 해당 통화가 없으면 분석을 건너뛴다"""
        mock_db = _make_mock_db([1400.0] * 21)
        analyzer = BuySignalAnalyzer(mock_db)

        # USD만 제공, JPY(100)는 없음
        today_rates = {"USD": 1400.0}
        signals = analyzer.analyze(today_rates)

        # JPY(100) 관련 신호는 없어야 한다
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
        mock_db = _make_mock_db([1400.0] * 21)
        analyzer = BuySignalAnalyzer(mock_db)

        # EUR은 TARGET_CURRENCIES에 없음
        today_rates = {"EUR": 1500.0}
        signals = analyzer.analyze(today_rates)

        assert signals == []
