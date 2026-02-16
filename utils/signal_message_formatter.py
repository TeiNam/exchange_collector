"""
매수 신호 텔레그램 HTML 메시지 포맷 모듈

Signal 리스트를 통화별로 그룹핑하여 텔레그램 HTML 메시지로 변환한다.
"""

from utils.buy_signal_analyzer import Signal


class SignalMessageFormatter:
    """매수 신호 텔레그램 HTML 메시지 포맷터"""

    # 신호 유형별 이모지 매핑
    SIGNAL_EMOJI = {
        "n_week_low": "📉",
        "golden_cross": "✨",
        "dead_cross": "⚠️",
        "rsi_oversold": "🔋",
        "rsi_overbought": "🔥",
        "bollinger_low": "📊",
        "bollinger_high": "📈",
    }

    # 통화별 이모지
    CURRENCY_EMOJI = {
        "USD": "💵",
        "JPY(100)": "💴",
    }

    # 통화별 한국어 이름
    CURRENCY_NAME = {
        "USD": "달러",
        "JPY(100)": "엔화",
    }

    def format_signals(self, signals: list[Signal]) -> str:
        """
        Signal 리스트를 텔레그램 HTML 메시지로 변환한다.

        통화별로 그룹핑하여 각 신호에 이모지, 설명, 현재 환율, 지표 값을 포함한다.
        신호가 없으면 빈 문자열을 반환한다.

        Args:
            signals: Signal 객체 리스트

        Returns:
            텔레그램 HTML 파싱 모드에 맞는 메시지 문자열, 또는 빈 문자열
        """
        if not signals:
            return ""

        lines = ["🚨 <b>환율 매수 신호 감지</b>"]

        # 통화별로 그룹핑 (입력 순서 유지를 위해 dict 사용)
        grouped: dict[str, list[Signal]] = {}
        for signal in signals:
            grouped.setdefault(signal.currency, []).append(signal)

        # 통화별 블록 생성
        for currency, currency_signals in grouped.items():
            lines.append("")  # 빈 줄로 블록 구분
            lines.append(self._format_currency_block(currency, currency_signals))

        return "\n".join(lines)

    def _format_currency_block(
        self, currency: str, signals: list[Signal]
    ) -> str:
        """
        단일 통화의 신호 블록을 포맷한다.

        Args:
            currency: 통화 코드 (예: "USD", "JPY(100)")
            signals: 해당 통화의 Signal 리스트

        Returns:
            통화 헤더 + 신호 라인들로 구성된 문자열
        """
        emoji = self.CURRENCY_EMOJI.get(currency, "💱")
        name = self.CURRENCY_NAME.get(currency, currency)
        current_rate = signals[0].current_rate

        # 통화 헤더 라인: 💵 <b>달러(USD)</b> - 현재: 1,425.00원
        header = (
            f"{emoji} <b>{name}({currency})</b>"
            f" - 현재: {current_rate:,.2f}원"
        )

        # 각 신호 라인 생성
        signal_lines = [
            self._format_signal_line(signal) for signal in signals
        ]

        return "\n".join([header] + signal_lines)

    def _format_signal_line(self, signal: Signal) -> str:
        """
        개별 신호를 이모지 + 메시지 형태로 포맷한다.

        Args:
            signal: Signal 객체

        Returns:
            이모지와 메시지가 포함된 한 줄 문자열
        """
        emoji = self.SIGNAL_EMOJI.get(signal.signal_type, "📌")
        return f"{emoji} {signal.message}"
