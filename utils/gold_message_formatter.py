"""텔레그램 HTML 포맷 금시세 메시지 생성 모듈"""


class GoldMessageFormatter:
    """텔레그램 HTML 포맷 금시세 메시지 생성"""

    def format_message(self, date: str, gold: dict, sparkline: str = '') -> str:
        """
        금시세 HTML 메시지 생성

        Args:
            date: 기준일 문자열 (예: '2026-07-06')
            gold: {'isu_nm', 'clsprc', 'cmpprevdd_prc', 'fluc_rt'} (원/g)
            sparkline: 최근 종가 스파크라인 문자열

        Returns:
            텔레그램 HTML 파싱 모드용 메시지
        """
        clsprc = gold['clsprc']
        diff = gold['cmpprevdd_prc']
        fluc = gold['fluc_rt']

        if diff > 0:
            change = f'🟢 ↑{abs(diff):,.0f} (+{fluc:.2f}%)'
        elif diff < 0:
            change = f'🔴 ↓{abs(diff):,.0f} ({fluc:.2f}%)'
        else:
            change = '─ 변동없음'

        lines = [
            f'🥇 <b>{date} 금시세</b>',
            '',
            f'🪙 <b>{gold["isu_nm"]}</b>',
            f'<code>{clsprc:,.0f}원/g</code> {change}',
        ]
        if sparkline:
            lines.append(f'<code>{sparkline}</code>')
        return '\n'.join(lines)
