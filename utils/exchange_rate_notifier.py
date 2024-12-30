import logging
from datetime import datetime, timedelta
from modules.slack_sender import SlackSender
from utils.exchange_rate_visualizer import ExchangeRateVisualizer
from utils.exchange_rate_collector import ExchangeRateCollector
from modules.mysql_connector import MySQLConnector
from configs.slack_setting import get_credentials

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def get_exchange_rates(db_connector, date):
    """특정 날짜의 환율 정보 조회"""
    query = """
    SELECT cur_unit, deal_bas_r, bkpr
    FROM exchange_rates 
    WHERE DATE(search_date) = %s
    AND cur_unit IN ('USD', 'JPY(100)')
    """

    try:
        connection = db_connector.get_connection()
        with connection.cursor() as cursor:
            cursor.execute(query, (date,))
            return {row[0]: {"deal_bas_r": row[1], "bkpr": row[2]} for row in cursor.fetchall()}
    except Exception as e:
        logger.error(f"환율 정보 조회 중 오류 발생: {str(e)}")
        return {}


def format_rate_message(currency, today_rate, yesterday_rate):
    """환율 증감 메시지 포맷팅"""
    if not yesterday_rate:
        return f"• {currency}: {today_rate:,.2f}원"

    diff = today_rate - yesterday_rate
    change = "↑" if diff > 0 else "↓" if diff < 0 else "-"
    return f"• {currency}: {today_rate:,.2f}원 ({change}{abs(diff):,.2f})"


def main():
    """환율 데이터 수집, 시각화 및 알림을 처리하는 노티파이어"""
    try:
        # Slack 설정 가져오기
        credentials = get_credentials()
        slack = SlackSender(channel_id=credentials['channel_id'])
        logger.debug("Slack Sender 초기화 완료")

        # Database Connector 초기화
        db_connector = MySQLConnector()
        logger.info("DB Connector 초기화 완료")

        # 1. Exchange Rate Collector 실행
        collector = ExchangeRateCollector(db_connector)
        collector.run()
        logger.info("환율 데이터를 성공적으로 수집했습니다.")

        # 2. Exchange Rate Visualizer 실행
        visualizer = ExchangeRateVisualizer(db_connector)
        graph_path = visualizer.create_visualization(months=3)
        logger.info(f"환율 그래프가 생성되었습니다: {graph_path}")

        # 3. 오늘과 어제의 환율 정보 조회
        today = datetime.now().date()
        yesterday = today - timedelta(days=1)

        today_rates = get_exchange_rates(db_connector, today)
        yesterday_rates = get_exchange_rates(db_connector, yesterday)

        # 메시지 생성
        message_lines = [
            f"📊 {today.strftime('%Y-%m-%d')} 오늘의 환율 정보",
            ""  # 빈 줄 추가
        ]

        # USD 정보 추가
        if 'USD' in today_rates:
            usd_today = today_rates['USD']['deal_bas_r']
            usd_yesterday = yesterday_rates.get('USD', {}).get('deal_bas_r')
            message_lines.append(format_rate_message("달러(USD)", usd_today, usd_yesterday))

        # JPY 정보 추가
        if 'JPY(100)' in today_rates:
            jpy_today = today_rates['JPY(100)']['deal_bas_r']
            jpy_yesterday = yesterday_rates.get('JPY(100)', {}).get('deal_bas_r')
            message_lines.append(format_rate_message("엔화(JPY100)", jpy_today, jpy_yesterday))

        message_lines.extend([
            "",  # 빈 줄 추가
            "3개월간의 환율 변동 그래프를 참고하세요."
        ])

        # 메시지 전송
        message = "\n".join(message_lines)
        if not slack.send_message(message, file_path=graph_path):
            logger.error("Slack 메시지 전송 실패")

    except Exception as e:
        logger.error(f"스크립트 실행 중 오류 발생: {str(e)}", exc_info=True)
    finally:
        if 'db_connector' in locals():
            db_connector.close()


if __name__ == "__main__":
    main()