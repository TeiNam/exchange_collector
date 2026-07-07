"""
KRXGoldClient 단위 테스트

requests를 모킹하여 금 일별매매정보 응답 파싱, 휴장일 처리, 검증/오류 처리를 검증한다.
"""

from unittest.mock import MagicMock, patch

import pytest

from utils.krx_gold_client import KRXGoldClient


def _mock_response(json_data):
    resp = MagicMock()
    resp.json.return_value = json_data
    resp.raise_for_status.return_value = None
    return resp


_SAMPLE_ROW = {
    "BAS_DD": "20260706", "ISU_CD": "04020000", "ISU_NM": "금 99.99_1kg",
    "TDD_CLSPRC": "203780", "CMPPREVDD_PRC": "-560", "FLUC_RT": "-0.27",
    "TDD_OPNPRC": "205120", "TDD_HGPRC": "206190", "TDD_LWPRC": "203400",
    "ACC_TRDVOL": "177837", "ACC_TRDVAL": "36471170740",
}


@pytest.fixture
def client():
    c = KRXGoldClient()
    c.api_key = "test-key"
    return c


class TestGetGoldPrices:
    def test_parses_row_fields(self, client):
        """문자열 응답 필드를 숫자로 파싱한다"""
        resp = _mock_response({"OutBlock_1": [_SAMPLE_ROW]})
        with patch("utils.krx_gold_client.requests.get", return_value=resp):
            rows = client.get_gold_prices("20260706")

        assert len(rows) == 1
        r = rows[0]
        assert r["isu_cd"] == "04020000"
        assert r["isu_nm"] == "금 99.99_1kg"
        assert r["clsprc"] == 203780.0
        assert r["cmpprevdd_prc"] == -560.0
        assert r["fluc_rt"] == -0.27
        assert r["trdvol"] == 177837
        assert r["trdval"] == 36471170740
        assert r["search_date"] == "20260706"

    def test_holiday_returns_empty(self, client):
        """휴장일이면 빈 OutBlock_1 → 빈 리스트를 반환한다"""
        resp = _mock_response({"OutBlock_1": []})
        with patch("utils.krx_gold_client.requests.get", return_value=resp):
            assert client.get_gold_prices("20260705") == []

    def test_comma_separated_numbers(self, client):
        """콤마 포함 숫자도 파싱한다"""
        row = {**_SAMPLE_ROW, "TDD_CLSPRC": "203,780", "ACC_TRDVAL": "36,471,170,740"}
        resp = _mock_response({"OutBlock_1": [row]})
        with patch("utils.krx_gold_client.requests.get", return_value=resp):
            r = client.get_gold_prices("20260706")[0]
        assert r["clsprc"] == 203780.0
        assert r["trdval"] == 36471170740

    def test_malformed_response_raises(self, client):
        """OutBlock_1이 없으면 ValueError를 발생시킨다"""
        resp = _mock_response({"unexpected": "shape"})
        with patch("utils.krx_gold_client.requests.get", return_value=resp):
            with pytest.raises(ValueError, match="응답 형식"):
                client.get_gold_prices("20260706")

    def test_price_out_of_range_raises(self, client):
        """가격이 허용 범위를 벗어나면 ValueError를 발생시킨다"""
        row = {**_SAMPLE_ROW, "TDD_CLSPRC": "5"}  # PRICE_MIN 미만
        resp = _mock_response({"OutBlock_1": [row]})
        with patch("utils.krx_gold_client.requests.get", return_value=resp):
            with pytest.raises(ValueError, match="허용 범위"):
                client.get_gold_prices("20260706")

    def test_non_numeric_price_raises(self, client):
        """숫자가 아닌 가격이면 ValueError를 발생시킨다"""
        row = {**_SAMPLE_ROW, "TDD_CLSPRC": "-"}
        resp = _mock_response({"OutBlock_1": [row]})
        with patch("utils.krx_gold_client.requests.get", return_value=resp):
            with pytest.raises(ValueError, match="숫자로 변환"):
                client.get_gold_prices("20260706")

    def test_missing_field_raises_valueerror(self, client):
        """필수 필드가 누락되면 KeyError가 아닌 ValueError를 발생시킨다 (계약 유지)"""
        row = {k: v for k, v in _SAMPLE_ROW.items() if k != 'ISU_NM'}
        resp = _mock_response({"OutBlock_1": [row]})
        with patch("utils.krx_gold_client.requests.get", return_value=resp):
            with pytest.raises(ValueError, match="필수 필드"):
                client.get_gold_prices("20260706")

    def test_missing_api_key_raises(self):
        """API 키가 없으면 ValueError를 발생시킨다"""
        c = KRXGoldClient()
        c.api_key = None
        with pytest.raises(ValueError, match="KRX_API_KEY"):
            c.get_gold_prices("20260706")
