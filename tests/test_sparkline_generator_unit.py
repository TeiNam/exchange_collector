"""SparklineGenerator 단위 테스트

Requirements: 3.1, 3.2, 3.3, 3.4, 3.5
"""
import pytest

from utils.sparkline_generator import SPARK_BLOCKS, SparklineGenerator


class TestSparklineGeneratorEmpty:
    """빈 리스트 처리 테스트 (Requirement 3.3)"""

    def test_empty_list_returns_empty_string(self):
        """빈 리스트 → 빈 문자열 반환"""
        assert SparklineGenerator.generate([]) == ""


class TestSparklineGeneratorAllSame:
    """모든 값 동일 시 중간 블록 반환 테스트 (Requirement 3.5)"""

    def test_all_same_values_returns_middle_blocks(self):
        """모든 값 동일 → 중간 블록(▄) 반환"""
        result = SparklineGenerator.generate([100.0, 100.0, 100.0])
        assert result == "▄▄▄"

    def test_single_value_returns_middle_block(self):
        """단일 값 → 중간 블록(▄) 반환"""
        result = SparklineGenerator.generate([50.0])
        assert result == "▄"


class TestSparklineGeneratorMinMaxMapping:
    """최솟값/최댓값 매핑 테스트 (Requirement 3.4)"""

    def test_min_maps_to_lowest_block(self):
        """최솟값 → ▁ 매핑"""
        result = SparklineGenerator.generate([10.0, 20.0])
        assert result[0] == "▁"

    def test_max_maps_to_highest_block(self):
        """최댓값 → █ 매핑"""
        result = SparklineGenerator.generate([10.0, 20.0])
        assert result[1] == "█"

    def test_min_max_with_multiple_values(self):
        """여러 값에서 최솟값/최댓값 위치 확인"""
        values = [5.0, 10.0, 1.0, 8.0, 15.0]
        result = SparklineGenerator.generate(values)
        # 최솟값(1.0)은 인덱스 2, 최댓값(15.0)은 인덱스 4
        assert result[2] == "▁"
        assert result[4] == "█"


class TestSparklineGeneratorOutputValidity:
    """출력 유효성 테스트 (Requirements 3.1, 3.2)"""

    def test_output_length_matches_input(self):
        """출력 길이 == 입력 길이"""
        values = [1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0]
        result = SparklineGenerator.generate(values)
        assert len(result) == len(values)

    def test_all_characters_are_valid_blocks(self):
        """모든 출력 문자가 유니코드 블록 문자"""
        values = [1450.0, 1452.5, 1448.0, 1455.0, 1460.0, 1458.0, 1462.0]
        result = SparklineGenerator.generate(values)
        for char in result:
            assert char in SPARK_BLOCKS

    def test_fewer_than_seven_days(self):
        """7일 미만 데이터도 정상 처리 (Requirement 3.2)"""
        values = [100.0, 200.0, 150.0]
        result = SparklineGenerator.generate(values)
        assert len(result) == 3
        for char in result:
            assert char in SPARK_BLOCKS

    def test_realistic_exchange_rate_data(self):
        """실제 환율 데이터 시나리오"""
        # 7일간 USD/KRW 환율 예시
        values = [1450.0, 1452.5, 1448.0, 1455.0, 1460.0, 1458.0, 1462.0]
        result = SparklineGenerator.generate(values)
        assert len(result) == 7
        # 최솟값(1448.0) 위치 → ▁
        assert result[2] == "▁"
        # 최댓값(1462.0) 위치 → █
        assert result[6] == "█"
