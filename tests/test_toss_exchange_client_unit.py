"""
TossExchangeClient 단위 테스트

requests를 모킹하여 토큰 발급/캐시, USD/KRW 응답 파싱, 오류 처리를 검증한다.
"""

from unittest.mock import MagicMock, patch

import pytest

from utils.toss_exchange_client import TossExchangeClient


def _mock_response(json_data):
    resp = MagicMock()
    resp.json.return_value = json_data
    resp.raise_for_status.return_value = None
    return resp


@pytest.fixture
def client():
    c = TossExchangeClient()
    c.client_id = "test-id"
    c.client_secret = "test-secret"
    return c


class TestTokenIssuance:
    """토큰 발급 및 캐시 테스트"""

    def test_token_issued_and_cached(self, client):
        """토큰을 한 번 발급하면 캐시되어 재요청하지 않는다"""
        token_resp = _mock_response({
            "access_token": "abc123", "token_type": "Bearer", "expires_in": 86399
        })
        with patch("utils.toss_exchange_client.requests.post", return_value=token_resp) as mock_post:
            assert client._get_token() == "abc123"
            assert client._get_token() == "abc123"  # 캐시 사용
            mock_post.assert_called_once()  # 토큰 요청은 1회만

    def test_missing_credentials_raises(self):
        """client_id/secret이 없으면 ValueError를 발생시킨다"""
        c = TossExchangeClient()
        c.client_id = None
        c.client_secret = None
        with pytest.raises(ValueError, match="TOSS_CLIENT"):
            c._get_token()

    def test_token_response_without_access_token_raises(self, client):
        """응답에 access_token이 없으면 ValueError를 발생시킨다"""
        bad_resp = _mock_response({"token_type": "Bearer"})
        with patch("utils.toss_exchange_client.requests.post", return_value=bad_resp):
            with pytest.raises(ValueError, match="access_token"):
                client._get_token()


class TestGetUsdKrw:
    """USD/KRW 환율 조회 파싱 테스트"""

    def test_parses_rate_fields(self, client):
        """문자열 응답 필드를 float으로 파싱한다"""
        client._token = "cached"
        client._token_expires_at = float("inf")

        fx_resp = _mock_response({
            "result": {
                "baseCurrency": "USD", "quoteCurrency": "KRW",
                "rate": "1534", "midRate": "1533.5", "basisPoint": "3",
                "rateChangeType": "UP",
                "validFrom": "2026-07-04T02:55:40.000+09:00",
                "validUntil": "2026-07-04T03:00:39.000+09:00",
            }
        })
        with patch("utils.toss_exchange_client.requests.get", return_value=fx_resp):
            result = client.get_usd_krw()

        assert result["rate"] == 1534.0
        assert result["mid_rate"] == 1533.5
        assert result["basis_point"] == 3.0
        assert result["rate_change_type"] == "UP"
        assert result["valid_from"].startswith("2026-07-04")

    def test_malformed_response_raises(self, client):
        """result 키가 없으면 ValueError를 발생시킨다"""
        client._token = "cached"
        client._token_expires_at = float("inf")

        bad_resp = _mock_response({"unexpected": "shape"})
        with patch("utils.toss_exchange_client.requests.get", return_value=bad_resp):
            with pytest.raises(ValueError, match="응답 형식"):
                client.get_usd_krw()
