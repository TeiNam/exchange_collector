import logging
import sys
from modules.scheduler import setup_schedule, get_scheduler_status
from modules.telegram_bot import create_bot_application

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


def main():
    try:
        logger.info("환율 수집 서비스를 시작합니다.")
        logger.info("스케줄: 매일 14:00 KST (환율 알림 + 매수 신호 분석)")

        # 스케줄러 시작 (백그라운드 스레드)
        scheduler = setup_schedule(run_immediately=False)

        # 스케줄러 상태 출력
        status = get_scheduler_status()
        logger.info(f"다음 실행 시간: {status['next_runs'][0]['next_run']}")

        # 텔레그램 봇 폴링 시작 (메인 스레드에서 실행, Ctrl+C로 종료)
        logger.info("텔레그램 봇 폴링을 시작합니다.")
        application = create_bot_application()
        application.run_polling(drop_pending_updates=True)

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