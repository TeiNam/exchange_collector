"""텔레그램 HTML 포맷 환율 메시지 생성 모듈"""

from typing import Optional


class HTMLMessageFormatter:
    """텔레그램 HTML 포맷 환율 메시지 생성"""

    # 통화별 이모지 매핑
    CURRENCY_EMOJI = {
        'USD': '💵',
        'JPY(100)': '💴',
        'EUR': '💶',
    }

    # 통화별 한국어 이름
    CURRENCY_NAME = {
        'USD': '달러',
        'JPY(100)': '엔화(100)',
        'EUR': '유로',
    }

    def format_message(
        self,
        date: str,
        rates: dict,
        yesterday_rates: dict,
        sparklines: dict,
    ) -> str:
        """
        HTML 포맷 환율 메시지 생성

        Args:
            date: 날짜 문자열 (예: '2025-01-15')
            rates: 오늘 환율 {currency: float}
            yesterday_rates: 어제 환율 {currency: float} (빈 dict 가능)
            sparklines: 통화별 스파크라인 {currency: str}

        Returns:
            텔레그램 HTML 파싱 모드에 맞는 메시지 문자열
        """
        # 제목 라인
        lines = [f'📊 <b>{date} 환율 정보</b>']

        # 각 통화별 블록 생성
        for currency, today_rate in rates.items():
            yesterday_rate = yesterday_rates.get(currency)
            sparkline = sparklines.get(currency, '')
            block = self._format_currency_block(
                currency, today_rate, yesterday_rate, sparkline
            )
            lines.append('')  # 빈 줄로 블록 구분
            lines.append(block)

        return '\n'.join(lines)

    def _format_currency_block(
        self,
        currency: str,
        today_rate: float,
        yesterday_rate: Optional[float],
        sparkline: str,
    ) -> str:
        """개별 통화 블록 포맷"""
        emoji = self.CURRENCY_EMOJI.get(currency, '💱')
        name = self.CURRENCY_NAME.get(currency, currency)

        # 통화 제목 라인
        header = f'{emoji} <b>{name}({currency})</b>'

        # 환율 값 + 증감 표시 라인
        rate_str = f'<code>{self._format_rate_value(today_rate)}</code>'
        if yesterday_rate is not None:
            change_str = self._format_change(today_rate, yesterday_rate)
            rate_line = f'{rate_str} {change_str}'
        else:
            rate_line = rate_str

        # 스파크라인 라인
        parts = [header, rate_line]
        if sparkline:
            parts.append(f'<code>{sparkline}</code>')

        return '\n'.join(parts)

    def _format_change(self, today: float, yesterday: float) -> str:
        """증감 표시 포맷 (이모지 + 화살표 + 금액)"""
        diff = today - yesterday
        if diff > 0:
            return f'🟢 ↑{abs(diff):,.2f}'
        elif diff < 0:
            return f'🔴 ↓{abs(diff):,.2f}'
        else:
            return '─ 변동없음'

    def _format_rate_value(self, rate: float) -> str:
        """환율 값 포맷 (천 단위 구분자, 소수점 2자리)"""
        return f'{rate:,.2f}원'
