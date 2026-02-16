"""
SignalMessageFormatter 속성 기반 테스트 (Property-Based Tests)

Feature: exchange-rate-buy-signal
테스트 대상: utils/signal_message_formatter.py - SignalMessageFormatter 클래스
"""

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from utils.buy_signal_analyzer import Signal
from utils.signal_message_formatter import SignalMessageFormatter


# === 전략(Strategy) 정의 ===

# 통화 코드 전략
currency_strategy = st.sampled_from(["USD", "JPY(100)"])

# 신호 유형 전략
signal_type_strategy = st.sampled_from([
    "n_week_low", "golden_cross", "dead_cross",
    "rsi_oversold", "rsi_overbought", "bollinger_low", "bollinger_high",
])

# 양수 환율 전략
positive_rate = st.floats(min_value=0.01, max_value=10000.0, allow_nan=False, allow_infinity=False)

# 지표 값 전략 (None 포함)
indicator_value_strategy = st.one_of(
    st.none(),
    st.floats(min_value=0.0, max_value=10000.0, allow_nan=False, allow_infinity=False),
)

# 통화별로 동일한 current_rate를 가진 Signal 리스트 생성 전략
# 실제 시스템에서는 같은 통화의 신호들이 동일한 현재 환율을 공유한다
@st.composite
def signals_list_strategy(draw):
    """
    현실적인 Signal 리스트를 생성하는 전략.
    같은 통화의 Signal들은 동일한 current_rate를 가진다.
    """
    # 사용할 통화 목록 결정 (1~2개)
    currencies = draw(st.lists(
        currency_strategy, min_size=1, max_size=2, unique=True,
    ))

    signals = []
    for currency in currencies:
        # 해당 통화의 현재 환율 (통화 내 동일)
        rate = draw(positive_rate)
        # 해당 통화의 신호 개수 (1~4개)
        num_signals = draw(st.integers(min_value=1, max_value=4))
        for _ in range(num_signals):
            signal = Signal(
                currency=currency,
                signal_type=draw(signal_type_strategy),
                message=draw(st.text(min_size=1, max_size=100)),
                current_rate=rate,
                indicator_value=draw(indicator_value_strategy),
            )
            signals.append(signal)

    return signals


class TestSignalMessageCompleteness:
    """
    Property 7: 신호 메시지 완전성

    For any 하나 이상의 Signal 객체로 구성된 리스트에 대해,
    format_signals가 반환하는 HTML 문자열에는 각 Signal의
    currency(통화)와 current_rate(현재 환율) 정보가 모두 포함되어야 한다.

    Feature: exchange-rate-buy-signal, Property 7: 신호 메시지 완전성
    **Validates: Requirements 5.1, 5.2**
    """

    @given(signals=signals_list_strategy())
    @settings(max_examples=100)
    def test_format_contains_currency_and_rate(self, signals):
        """포맷 결과에 각 Signal의 currency와 current_rate가 포함되는지 검증"""
        formatter = SignalMessageFormatter()
        result = formatter.format_signals(signals)

        # 결과가 빈 문자열이 아니어야 함 (1개 이상의 신호가 있으므로)
        assert result, "1개 이상의 신호가 있는데 빈 문자열이 반환되었습니다"

        for signal in signals:
            # 각 Signal의 currency가 메시지에 포함되어야 함
            assert signal.currency in result, (
                f"통화 '{signal.currency}'가 메시지에 포함되지 않았습니다.\n"
                f"메시지: {result}"
            )

            # 각 Signal의 current_rate가 메시지에 포함되어야 함
            # 포맷터가 쉼표 구분 소수점 2자리로 포맷하므로 해당 형식으로 확인
            formatted_rate = f"{signal.current_rate:,.2f}"
            assert formatted_rate in result, (
                f"환율 '{formatted_rate}'이 메시지에 포함되지 않았습니다.\n"
                f"Signal: currency={signal.currency}, rate={signal.current_rate}\n"
                f"메시지: {result}"
            )
