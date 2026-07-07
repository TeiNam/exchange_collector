"""GoldMessageFormatter 단위 테스트 - 등락 방향별 표시와 스파크라인 포함 여부 검증"""

from utils.gold_message_formatter import GoldMessageFormatter


def _fmt(diff, fluc, sparkline=''):
    return GoldMessageFormatter().format_message(
        date='2026-07-06',
        gold={'isu_nm': '금 99.99_1kg', 'clsprc': 203780.0,
              'cmpprevdd_prc': diff, 'fluc_rt': fluc},
        sparkline=sparkline,
    )


def test_down_shows_red_and_negative_pct():
    msg = _fmt(-560.0, -0.27)
    assert '🔴' in msg and '↓560' in msg and '(-0.27%)' in msg
    assert '203,780원/g' in msg


def test_up_shows_green_and_positive_pct():
    msg = _fmt(1200.0, 0.59)
    assert '🟢' in msg and '↑1,200' in msg and '(+0.59%)' in msg


def test_flat_shows_no_change():
    msg = _fmt(0.0, 0.0)
    assert '변동없음' in msg


def test_sparkline_included_when_present():
    assert '▁▂▃' in _fmt(-560.0, -0.27, sparkline='▁▂▃')


def test_sparkline_omitted_when_empty():
    msg = _fmt(-560.0, -0.27, sparkline='')
    # 스파크라인 라인이 없어야 함 (code 태그는 가격 라인에만)
    assert msg.count('<code>') == 1
