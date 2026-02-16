# modules/scheduler.py
import schedule
import time
import logging
import threading
from datetime import datetime
import pytz
from utils.exchange_rate_notifier import main as run_notifier
from utils.exchange_rate_notifier import run_buy_signal_analysis
from utils.holiday_checker import HolidayChecker

logger = logging.getLogger(__name__)

# 한국 시간대 설정
KST = pytz.timezone('Asia/Seoul')

class SchedulerThread(threading.Thread):
    def __init__(self, run_immediately=False):
        super().__init__()
        self.is_running = False
        self.schedule_time = "14:00"  # 노티파이어 실행 시간 (14:00 KST)
        self.buy_signal_time = "14:00"  # 매수 신호 분석 및 전송 시간 (14:00 KST)
        self.run_immediately = run_immediately

    def run(self):
        self.is_running = True

        # 스케줄 등록
        schedule.every().day.at(self.schedule_time).do(run_notifier_job)
        schedule.every().day.at(self.buy_signal_time).do(run_buy_signal_job)
        logger.info(f"노티파이어 스케줄 등록: {self.schedule_time} KST")
        logger.info(f"매수 신호 분석 스케줄 등록: {self.buy_signal_time} KST")

        logger.info("노티파이어 스케줄러 시작됨")
        logger.info(f"실행 시간: 매일 {self.schedule_time} KST (환율 알림)")
        logger.info(f"실행 시간: 매일 {self.buy_signal_time} KST (매수 신호 분석/전송)")

        # 옵션이 설정된 경우에만 즉시 실행
        if self.run_immediately:
            logger.info("초기 노티파이어 실행")
            run_notifier_job()

        while self.is_running:
            schedule.run_pending()
            time.sleep(60)

    def stop(self):
        self.is_running = False

def is_weekend(date):
    """주말(토,일) 여부 확인"""
    return date.weekday() >= 5  # 5는 토요일, 6은 일요일

def should_run_notifier(current_datetime):
    """노티파이어 실행 여부 확인"""
    try:
        # 주말 체크
        if is_weekend(current_datetime):
            logger.info(f"{current_datetime.strftime('%Y-%m-%d')}은 주말입니다. 노티파이어를 건너뜁니다.")
            return False

        # 공휴일 체크
        holiday_checker = HolidayChecker()
        holiday_result = holiday_checker.check_holiday(current_datetime)

        if holiday_result['is_holiday']:
            logger.info(f"{current_datetime.strftime('%Y-%m-%d')}은 {holiday_result['holiday_name']}입니다. 노티파이어를 건너뜁니다.")
            return False

        return True

    except Exception as e:
        logger.error(f"노티파이어 실행 여부 확인 중 오류 발생: {str(e)}", exc_info=True)
        # 오류 발생 시 기본적으로 실행 시도
        return True

def run_notifier_job():
    """노티파이어 실행"""
    try:
        current_datetime = datetime.now(KST)
        logger.info(f"노티파이어 프로세스 시작: {current_datetime.strftime('%Y-%m-%d %H:%M')} KST")

        # 실행 여부 확인
        if not should_run_notifier(current_datetime):
            return {
                "status": "skipped",
                "message": "주말 또는 공휴일로 인해 노티파이어가 건너뛰어졌습니다."
            }

        # 노티파이어 실행
        run_notifier()

        logger.info("노티파이어 작업 완료")
        return {"status": "success", "message": "노티파이어 작업 완료"}

    except Exception as e:
        error_msg = f"노티파이어 실행 중 오류 발생: {str(e)}"
        logger.error(error_msg, exc_info=True)
        return {"status": "error", "message": error_msg}


def run_buy_signal_job():
    """매수 신호 분석 및 전송 (평일만 실행)"""
    try:
        current_datetime = datetime.now(KST)
        logger.info(f"매수 신호 분석 시작: {current_datetime.strftime('%Y-%m-%d %H:%M')} KST")

        # 주말/공휴일 체크
        if not should_run_notifier(current_datetime):
            return {
                "status": "skipped",
                "message": "주말 또는 공휴일로 인해 매수 신호 분석이 건너뛰어졌습니다."
            }

        run_buy_signal_analysis()

        logger.info("매수 신호 분석 작업 완료")
        return {"status": "success", "message": "매수 신호 분석 작업 완료"}

    except Exception as e:
        error_msg = f"매수 신호 분석 실행 중 오류 발생: {str(e)}"
        logger.error(error_msg, exc_info=True)
        return {"status": "error", "message": error_msg}

def setup_schedule(run_immediately=False):
    """스케줄러 설정 및 시작"""
    scheduler_thread = SchedulerThread(run_immediately=run_immediately)
    scheduler_thread.start()
    return scheduler_thread

def get_scheduler_status():
    """스케줄러 상태 조회"""
    return {
        "next_runs": [
            {
                "job": job.job_func.__name__,
                "next_run": str(job.next_run)
            }
            for job in schedule.get_jobs()
        ]
    }