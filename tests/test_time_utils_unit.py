"""
time_utils 단위 테스트

시스템 타임존과 무관하게 kst_today/kst_now가 KST 기준을 반환하는지 검증한다.
"""

from datetime import date

from utils.time_utils import KST, kst_now, kst_today


def test_kst_now_is_timezone_aware_kst():
    """kst_now()는 tz-aware이며 KST 오프셋(+09:00)을 가진다"""
    now = kst_now()
    assert now.tzinfo is not None
    assert now.utcoffset().total_seconds() == 9 * 3600


def test_kst_today_returns_date():
    """kst_today()는 date 객체를 반환한다"""
    assert isinstance(kst_today(), date)


def test_kst_today_matches_kst_now_date():
    """kst_today()는 kst_now()의 날짜 부분과 일치한다"""
    # 자정 경계에서 극히 드물게 어긋날 수 있으나, 같은 tz라 사실상 항상 일치
    assert kst_today() == kst_now().date()


def test_kst_is_seoul():
    """KST는 Asia/Seoul 타임존이다"""
    assert str(KST) == 'Asia/Seoul'
