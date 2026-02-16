"""HTMLMessageFormatter 단위 테스트"""

import re
import pytest
from utils.html_message_formatter import HTMLMessageFormatter


@pytest.fixture
def formatter():
    return HTMLMessageFormatter()


class TestFormatMessage:
    """format_message 메서드 테스트"""

    def test_header_contains_date_and_emoji(self, formatter):
        """메시지 상단에 날짜와 📊 이모지가 포함된 제목 표시 (요구사항 4.5)"""
        result = formatter.format_message(
            date='2025-01-15',
            rates={'USD': 1450.50},
            yesterday_rates={'USD': 1438.20},
            sparklines={'USD': '▂▃▁▄▆▅█'},
        )
        assert '📊' in result
        assert '2025-01-15' in result
        assert '<b>2025-01-15 환율 정보</b>' in result

    def test_currency_emoji_included(self, formatter):
        """통화별 이모지 지시자 포함 (요구사항 4.2)"""
        result = formatter.format_message(
            date='2025-01-15',
            rates={'USD': 1450.50, 'JPY(100)': 985.20, 'EUR': 1580.00},
            yesterday_rates={},
            sparklines={},
        )
        assert '💵' in result
        assert '💴' in result
        assert '💶' in result

    def test_rate_value_format(self, formatter):
        """환율 값 천 단위 구분자, 소수점 2자리 포맷 (요구사항 4.7)"""
        result = formatter.format_message(
            date='2025-01-15',
            rates={'USD': 1450.50},
            yesterday_rates={},
            sparklines={},
        )
        assert '1,450.50원' in result

    def test_increase_indicator(self, formatter):
        """환율 상승 시 🟢 ↑ 표시 (요구사항 4.3)"""
        result = formatter.format_message(
            date='2025-01-15',
            rates={'USD': 1450.50},
            yesterday_rates={'USD': 1438.20},
            sparklines={},
        )
        assert '🟢' in result
        assert '↑' in result
        assert '12.30' in result

    def test_decrease_indicator(self, formatter):
        """환율 하락 시 🔴 ↓ 표시 (요구사항 4.3)"""
        result = formatter.format_message(
            date='2025-01-15',
            rates={'USD': 1438.20},
            yesterday_rates={'USD': 1450.50},
            sparklines={},
        )
        assert '🔴' in result
        assert '↓' in result
        assert '12.30' in result

    def test_no_change_indicator(self, formatter):
        """환율 변동 없을 시 ─ 표시 (요구사항 4.3)"""
        result = formatter.format_message(
            date='2025-01-15',
            rates={'USD': 1450.50},
            yesterday_rates={'USD': 1450.50},
            sparklines={},
        )
        assert '─' in result
        assert '변동없음' in result

    def test_no_yesterday_rates_omits_change(self, formatter):
        """어제 환율 없는 경우 증감 표시 생략 (요구사항 4.6)"""
        result = formatter.format_message(
            date='2025-01-15',
            rates={'USD': 1450.50},
            yesterday_rates={},
            sparklines={},
        )
        assert '🟢' not in result
        assert '🔴' not in result
        assert '↑' not in result
        assert '↓' not in result

    def test_sparkline_included(self, formatter):
        """스파크라인 문자열 포함 (요구사항 4.4)"""
        sparkline = '▂▃▁▄▆▅█'
        result = formatter.format_message(
            date='2025-01-15',
            rates={'USD': 1450.50},
            yesterday_rates={},
            sparklines={'USD': sparkline},
        )
        assert sparkline in result
        assert f'<code>{sparkline}</code>' in result

    def test_only_telegram_supported_html_tags(self, formatter):
        """텔레그램 지원 HTML 태그만 사용 (요구사항 4.1)"""
        result = formatter.format_message(
            date='2025-01-15',
            rates={'USD': 1450.50, 'JPY(100)': 985.20},
            yesterday_rates={'USD': 1438.20, 'JPY(100)': 988.30},
            sparklines={'USD': '▂▃▁▄▆▅█', 'JPY(100)': '▇▆▅▄▃▂▁'},
        )
        # 허용된 태그만 존재하는지 확인
        allowed_tags = {'<b>', '</b>', '<code>', '</code>', '<pre>', '</pre>'}
        found_tags = set(re.findall(r'</?[a-z]+>', result))
        assert found_tags.issubset(allowed_tags), (
            f"허용되지 않은 태그 발견: {found_tags - allowed_tags}"
        )

    def test_multiple_currencies(self, formatter):
        """여러 통화가 모두 포함되는지 확인"""
        result = formatter.format_message(
            date='2025-01-15',
            rates={'USD': 1450.50, 'JPY(100)': 985.20, 'EUR': 1580.00},
            yesterday_rates={'USD': 1438.20, 'JPY(100)': 988.30},
            sparklines={'USD': '▂▃▁▄▆▅█'},
        )
        # 각 통화 이름 포함 확인
        assert '달러' in result
        assert '엔화(100)' in result
        assert '유로' in result
        # USD는 어제 환율 있으므로 증감 표시
        assert '🟢' in result
        # JPY(100)은 어제 환율 있으므로 증감 표시
        assert '🔴' in result
        # EUR은 어제 환율 없으므로 증감 표시 없음 (별도 확인 불필요)


class TestFormatChange:
    """_format_change 메서드 테스트"""

    def test_positive_change(self, formatter):
        result = formatter._format_change(1450.50, 1438.20)
        assert result == '🟢 ↑12.30'

    def test_negative_change(self, formatter):
        result = formatter._format_change(985.20, 988.30)
        assert result == '🔴 ↓3.10'

    def test_zero_change(self, formatter):
        result = formatter._format_change(1450.50, 1450.50)
        assert result == '─ 변동없음'


class TestFormatRateValue:
    """_format_rate_value 메서드 테스트"""

    def test_thousands_separator(self, formatter):
        assert formatter._format_rate_value(1450.50) == '1,450.50원'

    def test_no_thousands_separator(self, formatter):
        assert formatter._format_rate_value(985.20) == '985.20원'

    def test_large_value(self, formatter):
        assert formatter._format_rate_value(12345.67) == '12,345.67원'

    def test_round_value(self, formatter):
        assert formatter._format_rate_value(1000.00) == '1,000.00원'
