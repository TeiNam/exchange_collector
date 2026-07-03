# utils/toss_exchange_client.py
"""토스증권 Open API 클라이언트

OAuth2 client_credentials 토큰 발급/캐시 + USD/KRW 실시간 환율 조회.
토큰은 약 24시간(expires_in=86399) 유효하므로 만료 전까지 메모리에 캐시한다.
"""

import logging
import threading
import time

import requests

from configs.apis_setting import TOSS_API_CONFIG

logger = logging.getLogger(__name__)

# 토큰 만료 안전 마진 (초): 실제 만료보다 이만큼 일찍 갱신
TOKEN_EXPIRY_MARGIN = 60

# USD/KRW 환율의 합리적 범위 (외부 API 이상치 방어용)
RATE_MIN = 100.0
RATE_MAX = 100000.0


def _validate_rate(value, field: str) -> float:
    """외부 API의 환율 값을 float으로 변환하고 합리적 범위인지 검증한다."""
    try:
        rate = float(value)
    except (TypeError, ValueError):
        raise ValueError(f"토스 환율 필드 '{field}'를 숫자로 변환할 수 없습니다: {value!r}")
    if not (RATE_MIN <= rate <= RATE_MAX):
        raise ValueError(f"토스 환율 필드 '{field}' 값이 허용 범위를 벗어납니다: {rate}")
    return rate


class TossExchangeClient:
    """토스 Open API로 USD/KRW 환율을 조회하는 클라이언트"""

    def __init__(self):
        self.client_id = TOSS_API_CONFIG['client_id']
        self.client_secret = TOSS_API_CONFIG['client_secret']
        self.token_url = TOSS_API_CONFIG['token_url']
        self.base_url = TOSS_API_CONFIG['base_url']

        # 토큰 캐시: access token과 monotonic 기준 만료 시각
        self._token: str | None = None
        self._token_expires_at: float = 0.0
        # 봇 스레드와 스케줄러 스레드가 동시에 토큰을 갱신하지 않도록 보호
        self._token_lock = threading.Lock()

    def _get_token(self) -> str:
        """유효한 access token을 반환한다 (캐시 우선, 만료 시 재발급).

        토큰 조회 빈도가 낮으므로(하루 수집 1회 + 온디맨드) 락 밖 빠른 경로 없이
        항상 락 안에서 _token/_token_expires_at를 일관되게 읽어 레이스를 배제한다.
        """
        with self._token_lock:
            if self._token and time.monotonic() < self._token_expires_at:
                return self._token

            if not self.client_id or not self.client_secret:
                raise ValueError("TOSS_CLIENT_ID / TOSS_CLIENT_SECRET이 설정되지 않았습니다.")

            return self._refresh_token()

    def _refresh_token(self) -> str:
        """토큰을 실제로 재발급한다 (호출자가 _token_lock을 보유한 상태여야 함)."""
        response = requests.post(
            self.token_url,
            data={
                'grant_type': 'client_credentials',
                'client_id': self.client_id,
                'client_secret': self.client_secret,
            },
            headers={'Content-Type': 'application/x-www-form-urlencoded'},
            timeout=10,
        )
        response.raise_for_status()
        data = response.json()

        token = data.get('access_token')
        if not token:
            # 응답 본문 전체 출력은 토큰 유출 위험이 있으므로 키 목록만 노출
            raise ValueError(f"토스 토큰 발급 응답에 access_token이 없습니다 (keys={list(data.keys())})")

        expires_in = int(data.get('expires_in', 3600))
        # monotonic 기준으로 만료 시각 저장 (시스템 시계 변경에 영향받지 않음)
        self._token_expires_at = time.monotonic() + expires_in - TOKEN_EXPIRY_MARGIN
        self._token = token
        logger.info(f"토스 access token 발급 완료 (유효 {expires_in}초)")
        return token

    def get_usd_krw(self) -> dict:
        """
        USD/KRW 현재 환율을 조회한다.

        Returns:
            {
                'rate': float,            # 매수 환율
                'mid_rate': float,        # 매매기준율
                'basis_point': float,     # midRate 대비 basis points
                'rate_change_type': str,  # 등락 구분 (UP/DOWN/FLAT 등)
                'valid_from': str,        # 유효 시작 시각 (ISO8601)
                'valid_until': str,       # 유효 종료 시각 (ISO8601)
            }

        Raises:
            requests.RequestException: API 호출 실패
            ValueError: 응답 형식이 예상과 다름
        """
        token = self._get_token()
        response = requests.get(
            f"{self.base_url}/api/v1/exchange-rate",
            params={'baseCurrency': 'USD', 'quoteCurrency': 'KRW'},
            headers={'Authorization': f'Bearer {token}', 'Accept': 'application/json'},
            timeout=10,
        )
        response.raise_for_status()
        payload = response.json()

        result = payload.get('result')
        if not isinstance(result, dict) or 'midRate' not in result:
            # 응답 전체 대신 최상위 키만 노출 (민감 정보 유출 방지)
            keys = list(payload.keys()) if isinstance(payload, dict) else type(payload).__name__
            raise ValueError(f"토스 환율 응답 형식이 예상과 다릅니다 (keys={keys})")

        try:
            basis_point = float(result['basisPoint'])
        except (TypeError, ValueError, KeyError):
            basis_point = 0.0  # 부가 정보이므로 실패 시 0으로 대체

        return {
            'rate': _validate_rate(result['rate'], 'rate'),
            'mid_rate': _validate_rate(result['midRate'], 'midRate'),
            'basis_point': basis_point,
            'rate_change_type': result.get('rateChangeType', ''),
            'valid_from': result.get('validFrom', ''),
            'valid_until': result.get('validUntil', ''),
        }


# 모듈 테스트용 코드
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    client = TossExchangeClient()
    print(client.get_usd_krw())
