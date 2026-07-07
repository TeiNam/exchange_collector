"""
GoldPriceCollector 단위 테스트

Mock client/DB로 최근 거래일 소급 조회, 저장 파라미터(날짜 변환), 휴장일 처리를 검증한다.
"""

from unittest.mock import MagicMock

from utils.gold_price_collector import GoldPriceCollector


def _make_mock_db():
    mock_db = MagicMock()
    mock_conn = MagicMock()
    mock_cursor = MagicMock()
    mock_db.get_connection.return_value = mock_conn
    mock_conn.cursor.return_value.__enter__.return_value = mock_cursor
    return mock_db, mock_conn, mock_cursor


_ROW = {
    'isu_cd': '04020000', 'isu_nm': '금 99.99_1kg',
    'clsprc': 203780.0, 'cmpprevdd_prc': -560.0, 'fluc_rt': -0.27,
    'opnprc': 205120.0, 'hgprc': 206190.0, 'lwprc': 203400.0,
    'trdvol': 177837, 'trdval': 36471170740, 'search_date': '20260706',
}


def test_collect_uses_first_available_trading_day():
    """오늘 데이터가 없으면 이전 거래일까지 소급해 조회한다"""
    client = MagicMock()
    # 첫 호출은 빈 배열(휴장), 두 번째 호출에서 데이터
    client.get_gold_prices.side_effect = [[], [_ROW]]
    collector = GoldPriceCollector(MagicMock(), client=client)

    rows = collector.collect_data()

    assert rows == [_ROW]
    assert client.get_gold_prices.call_count == 2


def test_collect_returns_empty_when_no_data():
    """소급 기간 내내 데이터가 없으면 빈 리스트를 반환한다"""
    client = MagicMock()
    client.get_gold_prices.return_value = []
    collector = GoldPriceCollector(MagicMock(), client=client)

    assert collector.collect_data() == []


def test_save_converts_date_and_upserts():
    """저장 시 basDd(YYYYMMDD)를 DATE 형식(YYYY-MM-DD)으로 변환한다"""
    mock_db, mock_conn, mock_cursor = _make_mock_db()
    collector = GoldPriceCollector(mock_db, client=MagicMock())

    collector.save_data([_ROW])

    _query, params = mock_cursor.executemany.call_args[0]
    assert params[0]['search_date'] == '2026-07-06'
    assert params[0]['isu_cd'] == '04020000'
    assert params[0]['clsprc'] == 203780.0
    mock_conn.commit.assert_called_once()


def test_save_empty_does_nothing():
    """빈 리스트 저장은 DB를 건드리지 않는다"""
    mock_db, mock_conn, mock_cursor = _make_mock_db()
    collector = GoldPriceCollector(mock_db, client=MagicMock())

    collector.save_data([])

    mock_cursor.executemany.assert_not_called()
    mock_conn.commit.assert_not_called()
