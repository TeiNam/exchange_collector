"""
HTMLMessageFormatter 속성 기반 테스트 (Property-Based Tests)

Feature: slack-to-telegram-migration
테스트 대상: utils/html_message_formatter.py - HTMLMessageFormatter 클래스
"""

import re
import pytest
from hypothesis import given, settings, assume
from hypothesis import strategies as st

from utils.html_message_formatter import HTMLMessageFormatter


# 지원 통화 목록
CURRENCIES = ['USD', 'JPY(100)', 'EUR']

# 통화별 이모지 매핑
CURRENCY_EMOJI = {
    'USD': '💵',
    'JPY(100)': '💴',
    'EUR': '💶',
}

# 텔레그램이 지원하는 HTML 태그 집합
ALLOWED_HTML_TAGS = {'<b>', '</b>', '<code>', '</code>', '<pre>', '</pre>'}

# 유효한 환율 값 전략: 양수, NaN/Infinity 제외
positive_rate = st.floats(min_value=0.01, max_value=99999.99, allow_nan=False, allow_infinity=False)

# 날짜 문자열 전략
date_strategy = st.dates().map(lambda d: d.strftime('%Y-%m-%d'))

# 스파크라인 블록 문자
SPARK_BLOCKS = '▁▂▃▄▅▆▇█'

# 스파크라인 전략: 블록 문자로 구성된 1~7자 문자열
sparkline_strategy = st.text(
    alphabet=list(SPARK_BLOCKS),
    min_size=1,
    max_size=7,
)

# 환율 딕셔너리 전략: 최소 1개 통화 포함
rates_strategy = st.dictionaries(
    keys=st.sampled_from(CURRENCIES),
    values=positive_rate,
    min_size=1,
    max_size=3,
)


def _build_sparklines(currencies):
    """테스트용 스파크라인 딕셔너리 생성 전략"""
    return st.fixed_dictionaries(
        {c: sparkline_strategy for c in currencies}
    )


class TestHTMLTagRestriction:
    """
    Property 11: HTML 태그 제한 (HTML Tag Restriction)

    임의의 유효한 환율 데이터에 대해,
    HTMLMessageFormatter.format_message()가 생성한 메시지에 포함된 HTML 태그는
    텔레그램이 지원하는 태그(<b>, </b>, <code>, </code>, <pre>, </pre>)만 존재해야 한다.

    Feature: slack-to-telegram-migration, Property 11: HTML 태그 제한
    **Validates: Requirements 4.1**
    """

    @given(
        date=date_strategy,
        rates=rates_strategy,
        data=st.data(),
    )
    @settings(max_examples=100)
    def test_only_allowed_html_tags(self, date, rates, data):
        """생성된 메시지에 텔레그램 지원 HTML 태그만 포함되는지 검증"""
        currencies = list(rates.keys())

        # 어제 환율: 일부 통화만 포함하거나 비어있을 수 있음
        yesterday_rates = data.draw(
            st.dictionaries(
                keys=st.sampled_from(currencies),
                values=positive_rate,
                min_size=0,
                max_size=len(currencies),
            )
        )

        # 스파크라인: 각 통화에 대해 생성
        sparklines = data.draw(
            st.fixed_dictionaries(
                {c: sparkline_strategy for c in currencies}
            )
        )

        formatter = HTMLMessageFormatter()
        result = formatter.format_message(date, rates, yesterday_rates, sparklines)

        # 메시지에서 모든 HTML 태그 추출
        found_tags = re.findall(r'</?[a-z]+>', result)

        # 모든 태그가 허용된 태그 집합에 포함되어야 함
        for tag in found_tags:
            assert tag in ALLOWED_HTML_TAGS, (
                f"허용되지 않은 HTML 태그 발견: '{tag}'\n"
                f"허용 태그: {ALLOWED_HTML_TAGS}\n"
                f"메시지:\n{result}"
            )


class TestHTMLMessageRequiredElements:
    """
    Property 12: HTML 메시지 필수 요소 포함 (HTML Message Required Elements)

    임의의 유효한 날짜, 환율 데이터, 어제 환율 데이터, 스파크라인에 대해,
    HTMLMessageFormatter.format_message()가 생성한 메시지는 다음을 포함해야 한다:
    (1) 날짜와 📊 이모지가 포함된 제목
    (2) 각 통화의 이모지 지시자
    (3) 증감 방향에 맞는 추세 이모지(🟢/🔴)와 화살표(↑/↓/─)
    (4) 각 통화의 스파크라인 문자열
    (5) 천 단위 구분자와 소수점 2자리로 포맷된 환율 값

    Feature: slack-to-telegram-migration, Property 12: HTML 메시지 필수 요소 포함
    **Validates: Requirements 4.2, 4.3, 4.4, 4.5, 4.7**
    """

    @given(
        date=date_strategy,
        rates=rates_strategy,
        data=st.data(),
    )
    @settings(max_examples=100)
    def test_message_contains_required_elements(self, date, rates, data):
        """생성된 메시지에 모든 필수 요소가 포함되는지 검증"""
        currencies = list(rates.keys())

        # 어제 환율: 모든 통화에 대해 생성 (증감 검증을 위해)
        yesterday_rates = data.draw(
            st.fixed_dictionaries(
                {c: positive_rate for c in currencies}
            )
        )

        # 스파크라인: 각 통화에 대해 생성
        sparklines = data.draw(
            st.fixed_dictionaries(
                {c: sparkline_strategy for c in currencies}
            )
        )

        formatter = HTMLMessageFormatter()
        result = formatter.format_message(date, rates, yesterday_rates, sparklines)

        # (1) 날짜와 📊 이모지가 포함된 제목 검증
        assert '📊' in result, f"📊 이모지가 메시지에 없습니다:\n{result}"
        assert date in result, f"날짜 '{date}'가 메시지에 없습니다:\n{result}"

        # (2) 각 통화의 이모지 지시자 검증
        for currency in currencies:
            expected_emoji = CURRENCY_EMOJI.get(currency, '💱')
            assert expected_emoji in result, (
                f"통화 '{currency}'의 이모지 '{expected_emoji}'가 메시지에 없습니다:\n{result}"
            )

        # (3) 증감 방향에 맞는 추세 이모지와 화살표 검증
        for currency in currencies:
            today = rates[currency]
            yesterday = yesterday_rates[currency]
            diff = today - yesterday

            if diff > 0:
                assert '🟢' in result, (
                    f"상승({currency}: {yesterday}→{today})인데 🟢가 없습니다:\n{result}"
                )
                assert '↑' in result, (
                    f"상승({currency}: {yesterday}→{today})인데 ↑가 없습니다:\n{result}"
                )
            elif diff < 0:
                assert '🔴' in result, (
                    f"하락({currency}: {yesterday}→{today})인데 🔴가 없습니다:\n{result}"
                )
                assert '↓' in result, (
                    f"하락({currency}: {yesterday}→{today})인데 ↓가 없습니다:\n{result}"
                )
            else:
                assert '─' in result, (
                    f"변동없음({currency}: {yesterday}→{today})인데 ─가 없습니다:\n{result}"
                )

        # (4) 각 통화의 스파크라인 문자열 검증
        for currency in currencies:
            sparkline = sparklines[currency]
            assert sparkline in result, (
                f"통화 '{currency}'의 스파크라인 '{sparkline}'이 메시지에 없습니다:\n{result}"
            )

        # (5) 천 단위 구분자와 소수점 2자리로 포맷된 환율 값 검증
        for currency in currencies:
            rate = rates[currency]
            formatted_rate = f'{rate:,.2f}원'
            assert formatted_rate in result, (
                f"통화 '{currency}'의 포맷된 환율 '{formatted_rate}'이 메시지에 없습니다:\n{result}"
            )
