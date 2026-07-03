# utils/time_utils.py
"""앱 공통 시각 유틸

배포 환경(Docker)의 시스템 타임존이 UTC일 수 있으므로, 날짜 기준은
항상 KST로 통일한다. 수집 저장 날짜·조회 기준일·스케줄이 어긋나지 않도록
모든 "오늘" 판단은 이 모듈을 거친다.
"""

from datetime import date, datetime

import pytz

KST = pytz.timezone('Asia/Seoul')


def kst_now() -> datetime:
    """현재 KST 시각 (tz-aware)"""
    return datetime.now(KST)


def kst_today() -> date:
    """KST 기준 오늘 날짜"""
    return datetime.now(KST).date()
