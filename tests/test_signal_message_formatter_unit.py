"""
SignalMessageFormatter 단위 테스트

테스트 대상: utils/signal_message_formatter.py - SignalMessageFormatter 클래스
빈 리스트, 단일 신호, 복수 통화 신호 포맷을 검증한다.

Requirements: 5.1, 5.2
"""

import pytest

from utils.buy_signal_analyzer import Signal
from utils.signal_message_formatter import SignalMessageFormatter


@pytest.fixture
def formatter():
    """SignalMessageFormatter 인스턴스 생성"""
    return SignalMessageFormatter()


class TestFormatSignalsEmpty:
    """빈 리스트 시 빈 문자열 반환 확인 (Requirements 5.1)"""

    def test_empty_list_returns_empty_string(self, formatter):
        """빈 신호 리스트를 전달하면 빈 문자열을 반환해야 한다"""
        result = formatter.format_signals([])
        assert result == ""

    def test_none_like_empty_signals(self, formatter):
        """신호가 없는 경우 메시지를 생성하지 않아야 한다"""
        result = formatter.format_signals([])
        assert not result  # falsy 확인


class TestFormatSignalsSingle:
    """단일 신호 포맷 확인 (Requirements 5.1, 5.2)"""

    def test_single_usd_n_week_low_signal(self, formatter):
        """USD N주 최저가 신호가 올바르게 포맷되는지 확인"""
        signals = [
            Signal(
                currency="USD",
                signal_type="n_week_low",
                message="3주(15 영업일) 만에 최저가입니다. 매수를 고려해보세요",
                current_rate=1425.00,
                indicator_value=1425.00,
            )
        ]
        result = formatter.format_signals(signals)

        # 헤더 포함 확인
        assert "🚨" in result
        assert "환율 매수 신호 감지" in result
        # 통화 정보 포함 확인
        assert "USD" in result
        assert "💵" in result
        assert "달러" in result
        # 현재 환율 포함 확인
        assert "1,425.00" in result
        # 신호 이모지 및 메시지 포함 확인
        assert "📉" in result
        assert "3주(15 영업일) 만에 최저가입니다" in result

    def test_single_jpy_bollinger_low_signal(self, formatter):
        """JPY(100) 볼린저 밴드 하단 신호가 올바르게 포맷되는지 확인"""
        signals = [
            Signal(
                currency="JPY(100)",
                signal_type="bollinger_low",
                message="볼린저 밴드 하단(940.50) 터치 - 매수 신호",
                current_rate=945.00,
                indicator_value=940.50,
            )
        ]
        result = formatter.format_signals(signals)

        # 통화 정보 포함 확인
        assert "JPY(100)" in result
        assert "💴" in result
        assert "엔화" in result
        # 현재 환율 포함 확인
        assert "945.00" in result
        # 신호 이모지 및 메시지 포함 확인
        assert "📊" in result
        assert "볼린저 밴드 하단" in result

    def test_single_golden_cross_signal(self, formatter):
        """골든크로스 신호의 이모지가 올바른지 확인"""
        signals = [
            Signal(
                currency="USD",
                signal_type="golden_cross",
                message="골든크로스 발생 - 단기 MA가 장기 MA를 상향 돌파",
                current_rate=1400.00,
                indicator_value=None,
            )
        ]
        result = formatter.format_signals(signals)

        assert "✨" in result
        assert "골든크로스 발생" in result

    def test_single_rsi_oversold_signal(self, formatter):
        """RSI 과매도 신호가 올바르게 포맷되는지 확인"""
        signals = [
            Signal(
                currency="USD",
                signal_type="rsi_oversold",
                message="RSI 28.5 - 과매도 구간, 반등 가능성",
                current_rate=1380.00,
                indicator_value=28.5,
            )
        ]
        result = formatter.format_signals(signals)

        assert "🔋" in result
        assert "RSI 28.5" in result
        assert "1,380.00" in result


class TestFormatSignalsMultipleCurrencies:
    """복수 통화 신호 포맷 확인 (Requirements 5.1, 5.2)"""

    def test_multiple_currencies_grouped(self, formatter):
        """USD와 JPY(100) 신호가 통화별로 그룹핑되는지 확인"""
        signals = [
            Signal(
                currency="USD",
                signal_type="n_week_low",
                message="3주(15 영업일) 만에 최저가입니다. 매수를 고려해보세요",
                current_rate=1425.00,
                indicator_value=1425.00,
            ),
            Signal(
                currency="JPY(100)",
                signal_type="bollinger_low",
                message="볼린저 밴드 하단(940.50) 터치 - 매수 신호",
                current_rate=945.00,
                indicator_value=940.50,
            ),
        ]
        result = formatter.format_signals(signals)

        # 두 통화 모두 포함 확인
        assert "USD" in result
        assert "JPY(100)" in result
        assert "💵" in result
        assert "💴" in result
        # 각 통화의 환율 포함 확인
        assert "1,425.00" in result
        assert "945.00" in result

    def test_multiple_signals_same_currency(self, formatter):
        """같은 통화에 여러 신호가 있을 때 하나의 블록으로 표시되는지 확인"""
        signals = [
            Signal(
                currency="USD",
                signal_type="n_week_low",
                message="4주(20 영업일) 만에 최저가입니다. 매수를 고려해보세요",
                current_rate=1425.00,
                indicator_value=1425.00,
            ),
            Signal(
                currency="USD",
                signal_type="golden_cross",
                message="골든크로스 발생 - 단기 MA가 장기 MA를 상향 돌파",
                current_rate=1425.00,
                indicator_value=None,
            ),
            Signal(
                currency="USD",
                signal_type="rsi_oversold",
                message="RSI 28.5 - 과매도 구간, 반등 가능성",
                current_rate=1425.00,
                indicator_value=28.5,
            ),
        ]
        result = formatter.format_signals(signals)

        # 헤더는 한 번만 나와야 함
        assert result.count("💵") == 1
        # 세 가지 신호 이모지 모두 포함
        assert "📉" in result
        assert "✨" in result
        assert "🔋" in result

    def test_mixed_buy_and_warning_signals(self, formatter):
        """매수 신호와 주의 신호가 혼합된 경우 모두 포맷되는지 확인"""
        signals = [
            Signal(
                currency="USD",
                signal_type="rsi_overbought",
                message="RSI 75.0 - 과매수 구간, 주의 필요",
                current_rate=1500.00,
                indicator_value=75.0,
            ),
            Signal(
                currency="JPY(100)",
                signal_type="dead_cross",
                message="데드크로스 발생 - 단기 MA가 장기 MA를 하향 돌파",
                current_rate=960.00,
                indicator_value=None,
            ),
        ]
        result = formatter.format_signals(signals)

        # 주의 신호 이모지 확인
        assert "🔥" in result
        assert "⚠️" in result
        # 각 메시지 포함 확인
        assert "과매수 구간" in result
        assert "데드크로스 발생" in result
