# modules/scheduler.py
import schedule
import time
import logging
import threading
from datetime import datetime
import pytz
from utils.exchange_rate_notifier import main as run_notifier
from utils.work_journal_notifier import main as run_work_journal_notifier
from utils.holiday_checker import HolidayChecker
from utils.slack_comment_collector import SlackCommentCollector
from modules.mysql_connector import MySQLConnector

logger = logging.getLogger(__name__)

# 한국 시간대 설정
KST = pytz.timezone('Asia/Seoul')

class SchedulerThread(threading.Thread):
    def __init__(self, run_immediately=False):
        super().__init__()
        self.is_running = False
        self.exchange_rate_time = "11:05"  # 환율 알림 실행 시간 (11:05 KST)
        self.work_journal_time = "09:00"   # 업무일지 알림 실행 시간 (09:00 KST)
        self.comment_collect_time = "23:00"  # 댓글 수집 실행 시간 (23:00 KST)
        self.run_immediately = run_immediately

    def run(self):
        self.is_running = True

        # 환율 알림 스케줄 등록
        schedule.every().day.at(self.exchange_rate_time).do(run_notifier_job)
        logger.info(f"환율 알림 스케줄 등록: {self.exchange_rate_time} KST")
        
        # 업무일지 작성 알림 스케줄 등록
        schedule.every().day.at(self.work_journal_time).do(run_work_journal_job)
        logger.info(f"업무일지 작성 알림 스케줄 등록: {self.work_journal_time} KST")
        
        # 댓글 수집 스케줄 등록 (매일 실행)
        schedule.every().day.at(self.comment_collect_time).do(run_comment_collector_job)
        logger.info(f"댓글 수집 스케줄 등록: {self.comment_collect_time} KST")

        logger.info("스케줄러 시작됨")
        logger.info(f"환율 알림 실행 시간: 매일 {self.exchange_rate_time} KST")
        logger.info(f"업무일지 작성 알림 실행 시간: 매일 {self.work_journal_time} KST (주말 및 공휴일 제외)")
        logger.info(f"댓글 수집 실행 시간: 매일 {self.comment_collect_time} KST")

        # 옵션이 설정된 경우에만 즉시 실행
        if self.run_immediately:
            logger.info("초기 환율 알림 실행")
            run_notifier_job()

        while self.is_running:
            schedule.run_pending()
            time.sleep(60)

    def stop(self):
        self.is_running = False

def is_weekend(date):
    """주말(토,일) 여부 확인"""
    return date.weekday() >= 5  # 5는 토요일, 6은 일요일

def should_run_task(current_datetime):
    """작업 실행 여부 확인"""
    try:
        # 주말 체크
        if is_weekend(current_datetime):
            logger.info(f"{current_datetime.strftime('%Y-%m-%d')}은 주말입니다. 작업을 건너뜁니다.")
            return False

        # 공휴일 체크
        holiday_checker = HolidayChecker()
        holiday_result = holiday_checker.check_holiday(current_datetime)

        if holiday_result['is_holiday']:
            logger.info(f"{current_datetime.strftime('%Y-%m-%d')}은 {holiday_result['holiday_name']}입니다. 작업을 건너뜁니다.")
            return False

        return True

    except Exception as e:
        logger.error(f"작업 실행 여부 확인 중 오류 발생: {str(e)}", exc_info=True)
        # 오류 발생 시 기본적으로 실행 시도
        return True

def run_notifier_job():
    """환율 알림 작업 실행"""
    try:
        current_datetime = datetime.now(KST)
        logger.info(f"환율 알림 프로세스 시작: {current_datetime.strftime('%Y-%m-%d %H:%M')} KST")

        # 실행 여부 확인
        if not should_run_task(current_datetime):
            return {
                "status": "skipped",
                "message": "주말 또는 공휴일로 인해 환율 알림이 건너뛰어졌습니다."
            }

        # 노티파이어 실행
        run_notifier()

        logger.info("환율 알림 작업 완료")
        return {"status": "success", "message": "환율 알림 작업 완료"}

    except Exception as e:
        error_msg = f"환율 알림 실행 중 오류 발생: {str(e)}"
        logger.error(error_msg, exc_info=True)
        return {"status": "error", "message": error_msg}

def run_work_journal_job():
    """업무일지 작성 알림 작업 실행"""
    try:
        current_datetime = datetime.now(KST)
        logger.info(f"업무일지 작성 알림 프로세스 시작: {current_datetime.strftime('%Y-%m-%d %H:%M')} KST")

        # 실행 여부 확인
        if not should_run_task(current_datetime):
            return {
                "status": "skipped",
                "message": "주말 또는 공휴일로 인해 업무일지 작성 알림이 건너뛰어졌습니다."
            }

        # 업무일지 알림 실행
        run_work_journal_notifier()

        logger.info("업무일지 작성 알림 작업 완료")
        return {"status": "success", "message": "업무일지 작성 알림 작업 완료"}

    except Exception as e:
        error_msg = f"업무일지 작성 알림 실행 중 오류 발생: {str(e)}"
        logger.error(error_msg, exc_info=True)
        return {"status": "error", "message": error_msg}

def run_comment_collector_job():
    """Slack 업무일지 댓글 수집 작업 실행"""
    try:
        current_datetime = datetime.now(KST)
        logger.info(f"Slack 업무일지 댓글 수집 프로세스 시작: {current_datetime.strftime('%Y-%m-%d %H:%M')} KST")

        # 댓글 수집 작업은 주말/공휴일에도 실행
        
        # DB 커넥터 초기화
        db_connector = MySQLConnector()
        
        # 댓글 수집기 초기화
        collector = SlackCommentCollector(db_connector)
        
        # 댓글 수집 (최근 2일 동안의 메시지만)
        comments = collector.collect_recent_message_comments(days_back=2)
        
        # 결과 요약
        total_messages = len(comments)
        total_comments = sum(len(msg_comments) for msg_comments in comments.values())
        
        logger.info(f"업무일지 댓글 수집 완료: {total_messages}개 메시지에서 {total_comments}개 댓글 수집")
        
        # 리소스 정리
        if db_connector:
            db_connector.close()
            
        return {
            "status": "success", 
            "message": f"Slack 업무일지 댓글 수집 완료 ({total_messages}개 메시지, {total_comments}개 댓글)"
        }

    except Exception as e:
        error_msg = f"Slack 업무일지 댓글 수집 중 오류 발생: {str(e)}"
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