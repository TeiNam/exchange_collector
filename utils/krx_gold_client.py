# utils/krx_gold_client.py
"""KRX 금시장 Open API 클라이언트

금 99.99 일별매매정보(gold_bydd_trd)를 조회한다.
- 인증: AUTH_KEY 헤더
- 요청: {"basDd": "YYYYMMDD"}
- 응답: {"OutBlock_1": [{종목별 시고저종/거래량/대금}, ...]}
"""

import logging

import requests

from configs.apis_setting import KRX_API_CONFIG

logger = logging.getLogger(__name__)

# 대표 금현물 종목코드 (금 99.99_1kg). 미니금(04020100)은 부차적.
GOLD_1KG_ISU_CD = '04020000'

# 금 가격(원/g)의 합리적 범위 (외부 API 이상치 방어용)
PRICE_MIN = 10000.0
PRICE_MAX = 1000000.0


def _to_float(value, field: str) -> float:
    """KRX 문자열 숫자(콤마 포함 가능)를 float으로 변환한다."""
    try:
        return float(str(value).replace(',', ''))
    except (TypeError, ValueError):
        raise ValueError(f"KRX 금시세 필드 '{field}'를 숫자로 변환할 수 없습니다: {value!r}")


def _to_int(value, field: str) -> int:
    """KRX 문자열 정수(콤마 포함 가능)를 int으로 변환한다."""
    return int(_to_float(value, field))


def _validate_price(value, field: str) -> float:
    """종가/시고저 가격을 검증한다 (합리적 범위)."""
    price = _to_float(value, field)
    if not (PRICE_MIN <= price <= PRICE_MAX):
        raise ValueError(f"KRX 금시세 필드 '{field}' 값이 허용 범위를 벗어납니다: {price}")
    return price


class KRXGoldClient:
    """KRX Open API로 금 99.99 일별매매정보를 조회하는 클라이언트"""

    def __init__(self):
        self.api_key = KRX_API_CONFIG['api_key']
        self.base_url = KRX_API_CONFIG['base_url']

    def get_gold_prices(self, bas_dd: str) -> list[dict]:
        """
        기준일자의 금 일별매매정보를 조회한다.

        Args:
            bas_dd: 기준일자 'YYYYMMDD'

        Returns:
            종목별 dict 리스트. 각 dict:
                {
                    'isu_cd': str, 'isu_nm': str,
                    'clsprc': float,        # 종가 (원/g)
                    'cmpprevdd_prc': float, # 전일 대비
                    'fluc_rt': float,       # 등락률 (%)
                    'opnprc'/'hgprc'/'lwprc': float,
                    'trdvol': int, 'trdval': int,
                    'search_date': str,     # basDd
                }
            휴장일이면 빈 리스트.

        Raises:
            requests.RequestException: API 호출 실패
            ValueError: 응답 형식이 예상과 다름 / API 키 미설정
        """
        if not self.api_key:
            raise ValueError("KRX_API_KEY가 설정되지 않았습니다.")

        response = requests.get(
            self.base_url,
            params={'basDd': bas_dd},
            headers={'AUTH_KEY': self.api_key, 'Accept': 'application/json'},
            timeout=15,
        )
        response.raise_for_status()
        payload = response.json()

        rows = payload.get('OutBlock_1')
        if not isinstance(rows, list):
            keys = list(payload.keys()) if isinstance(payload, dict) else type(payload).__name__
            raise ValueError(f"KRX 금시세 응답 형식이 예상과 다릅니다 (keys={keys})")

        return [self._parse_row(row) for row in rows]

    @staticmethod
    def _parse_row(row: dict) -> dict:
        """OutBlock_1의 한 행을 검증·정규화한다."""
        try:
            return {
                'isu_cd': row['ISU_CD'],
                'isu_nm': row['ISU_NM'],
                'clsprc': _validate_price(row['TDD_CLSPRC'], 'TDD_CLSPRC'),
                'cmpprevdd_prc': _to_float(row['CMPPREVDD_PRC'], 'CMPPREVDD_PRC'),
                'fluc_rt': _to_float(row['FLUC_RT'], 'FLUC_RT'),
                'opnprc': _validate_price(row['TDD_OPNPRC'], 'TDD_OPNPRC'),
                'hgprc': _validate_price(row['TDD_HGPRC'], 'TDD_HGPRC'),
                'lwprc': _validate_price(row['TDD_LWPRC'], 'TDD_LWPRC'),
                'trdvol': _to_int(row['ACC_TRDVOL'], 'ACC_TRDVOL'),
                'trdval': _to_int(row['ACC_TRDVAL'], 'ACC_TRDVAL'),
                'search_date': row['BAS_DD'],
            }
        except KeyError as e:
            raise ValueError(f"KRX 금시세 응답에 필수 필드가 없습니다: {e}")


# 모듈 테스트용 코드
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    from datetime import timedelta
    from utils.time_utils import kst_today

    client = KRXGoldClient()
    # 최근 평일 시도
    for delta in range(0, 7):
        d = (kst_today() - timedelta(days=delta)).strftime('%Y%m%d')
        rows = client.get_gold_prices(d)
        if rows:
            print(f"basDd={d}:")
            for r in rows:
                print(r)
            break
