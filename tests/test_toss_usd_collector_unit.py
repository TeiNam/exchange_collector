"""
TossUSDCollector 단위 테스트

Mock client/DB로 컬럼 매핑(midRate→deal_bas_r/bkpr, rate→tts)과
저장 쿼리 파라미터를 검증한다.
"""

from unittest.mock import MagicMock

from utils.toss_usd_collector import TossUSDCollector


def _make_mock_db():
    mock_db = MagicMock()
    mock_conn = MagicMock()
    mock_cursor = MagicMock()
    mock_db.get_connection.return_value = mock_conn
    # with connection.cursor() as cursor: 컨텍스트 매니저 대응
    mock_conn.cursor.return_value.__enter__.return_value = mock_cursor
    return mock_db, mock_conn, mock_cursor


def test_save_data_maps_fields_correctly():
    """midRate는 deal_bas_r/bkpr/ttb에, rate는 tts에 매핑된다"""
    mock_db, mock_conn, mock_cursor = _make_mock_db()
    client = MagicMock()
    collector = TossUSDCollector(mock_db, client=client)

    rate = {
        'rate': 1534.0, 'mid_rate': 1533.5, 'basis_point': 3.0,
        'rate_change_type': 'UP', 'valid_from': 'x', 'valid_until': 'y',
    }
    collector.save_data(rate)

    # execute 호출 인자에서 파라미터 dict 추출
    _query, params = mock_cursor.execute.call_args[0]
    assert params['cur_unit'] == 'USD'
    assert params['deal_bas_r'] == 1533.5
    assert params['bkpr'] == 1533.5
    assert params['ttb'] == 1533.5
    assert params['tts'] == 1534.0
    assert params['cur_nm'] == '미국 달러'
    mock_conn.commit.assert_called_once()


def test_run_collects_and_saves():
    """run()은 client 조회 후 저장까지 수행한다"""
    mock_db, _mock_conn, mock_cursor = _make_mock_db()
    client = MagicMock()
    client.get_usd_krw.return_value = {
        'rate': 1534.0, 'mid_rate': 1533.5, 'basis_point': 3.0,
        'rate_change_type': 'FLAT', 'valid_from': 'x', 'valid_until': 'y',
    }
    collector = TossUSDCollector(mock_db, client=client)

    collector.run()

    client.get_usd_krw.assert_called_once()
    mock_cursor.execute.assert_called_once()
