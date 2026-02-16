# 유니코드 블록 문자 (8단계)
SPARK_BLOCKS = '▁▂▃▄▅▆▇█'


class SparklineGenerator:
    """환율 데이터를 유니코드 스파크라인으로 변환"""

    @staticmethod
    def generate(values: list[float]) -> str:
        """
        숫자 리스트를 스파크라인 문자열로 변환

        - 빈 리스트: 빈 문자열 반환
        - 모든 값 동일: 중간 블록(▄) 반환
        - 최솟값 → ▁, 최댓값 → █ 매핑
        """
        if not values:
            return ""

        min_val = min(values)
        max_val = max(values)

        if min_val == max_val:
            return '▄' * len(values)

        # 각 값을 0~7 인덱스로 매핑
        scale = len(SPARK_BLOCKS) - 1
        result = []
        for v in values:
            idx = int((v - min_val) / (max_val - min_val) * scale)
            result.append(SPARK_BLOCKS[idx])

        return ''.join(result)
