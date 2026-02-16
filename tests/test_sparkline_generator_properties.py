"""
SparklineGenerator 속성 기반 테스트 (Property-Based Tests)

Feature: slack-to-telegram-migration
테스트 대상: utils/sparkline_generator.py - SparklineGenerator 클래스
"""

import pytest
from hypothesis import given, settings, assume
from hypothesis import strategies as st

from utils.sparkline_generator import SPARK_BLOCKS, SparklineGenerator


# 유효한 float 전략: NaN, Infinity 제외, 합리적 범위
finite_floats = st.floats(min_value=-1e6, max_value=1e6, allow_nan=False, allow_infinity=False)


class TestSparklineOutputValidity:
    """
    Property 9: 스파크라인 출력 유효성 (Sparkline Output Validity)

    임의의 비어있지 않은 숫자 리스트에 대해,
    SparklineGenerator.generate()는 입력과 동일한 길이의 문자열을 반환하고,
    모든 문자가 유니코드 블록 문자(▁▂▃▄▅▆▇█) 중 하나여야 한다.

    Feature: slack-to-telegram-migration, Property 9: 스파크라인 출력 유효성
    **Validates: Requirements 3.1, 3.2**
    """

    @given(
        values=st.lists(finite_floats, min_size=1, max_size=30),
    )
    @settings(max_examples=100)
    def test_output_length_and_valid_characters(self, values):
        """비어있지 않은 숫자 리스트 → 출력 길이 일치 및 유효 문자 검증"""
        result = SparklineGenerator.generate(values)

        # 출력 길이가 입력 길이와 동일해야 함
        assert len(result) == len(values), (
            f"입력 길이({len(values)})와 출력 길이({len(result)})가 다릅니다. "
            f"입력: {values}, 출력: '{result}'"
        )

        # 모든 문자가 유니코드 블록 문자 중 하나여야 함
        for i, char in enumerate(result):
            assert char in SPARK_BLOCKS, (
                f"인덱스 {i}의 문자 '{char}'가 유효한 블록 문자가 아닙니다. "
                f"유효 문자: {SPARK_BLOCKS}"
            )


class TestSparklineMinMaxMapping:
    """
    Property 10: 스파크라인 최솟값/최댓값 매핑 (Sparkline Min/Max Mapping)

    임의의 서로 다른 값을 2개 이상 포함하는 숫자 리스트에 대해,
    SparklineGenerator.generate()의 출력에서
    최솟값 위치의 문자는 ▁이고 최댓값 위치의 문자는 █이어야 한다.

    Feature: slack-to-telegram-migration, Property 10: 스파크라인 최솟값/최댓값 매핑
    **Validates: Requirements 3.4**
    """

    @given(
        values=st.lists(finite_floats, min_size=2, max_size=30),
    )
    @settings(max_examples=100)
    def test_min_maps_to_lowest_max_maps_to_highest(self, values):
        """최솟값 → ▁, 최댓값 → █ 매핑 검증"""
        # 모든 값이 동일한 경우 제외 (min != max 보장)
        assume(min(values) != max(values))

        result = SparklineGenerator.generate(values)

        min_val = min(values)
        max_val = max(values)

        # 최솟값의 첫 번째 위치 찾기
        min_idx = values.index(min_val)
        # 최댓값의 첫 번째 위치 찾기
        max_idx = values.index(max_val)

        # 최솟값 위치 → 가장 낮은 블록(▁)
        assert result[min_idx] == '▁', (
            f"최솟값({min_val}) 위치({min_idx})의 문자가 '▁'이 아닙니다. "
            f"실제: '{result[min_idx]}', 전체 출력: '{result}'"
        )

        # 최댓값 위치 → 가장 높은 블록(█)
        assert result[max_idx] == '█', (
            f"최댓값({max_val}) 위치({max_idx})의 문자가 '█'이 아닙니다. "
            f"실제: '{result[max_idx]}', 전체 출력: '{result}'"
        )
