import logging
import sys
import signal
from modules.scheduler import setup_schedule, get_scheduler_status

# 로깅 설정
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('exchange_rate_collector.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


def signal_handler(signum, frame):
    """시그널 핸들러: 프로그램 종료 시 처리"""
    logger.info("프로그램 종료 신호를 받았습니다.")
    sys.exit(0)


def main():
    try:
        # 시그널 핸들러 등록
        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)

        logger.info("환율 수집 서비스를 시작합니다.")
        logger.info("스케줄: 매일 11:05 KST")

        # 스케줄러 시작 (초기 수집 없이)
        scheduler = setup_schedule(run_immediately=False)

        # 스케줄러 상태 출력
        status = get_scheduler_status()
        logger.info(f"다음 실행 시간: {status['next_runs'][0]['next_run']}")

        # 메인 스레드 유지
        while True:
            signal.pause()

    except KeyboardInterrupt:
        logger.info("프로그램이 사용자에 의해 중단되었습니다.")
    except Exception as e:
        logger.error(f"프로그램 실행 중 오류 발생: {str(e)}", exc_info=True)
        sys.exit(1)
    finally:
        if 'scheduler' in locals():
            scheduler.stop()
        logger.info("환율 수집 서비스를 종료합니다.")


if __name__ == "__main__":
    main()