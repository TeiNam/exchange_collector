import logging
from datetime import datetime, timedelta

from modules.telegram_sender import TelegramSender
from configs.telegram_setting import get_credentials, is_send_graph_enabled
from utils.sparkline_generator import SparklineGenerator
from utils.html_message_formatter import HTMLMessageFormatter
from utils.exchange_rate_visualizer import ExchangeRateVisualizer
from utils.exchange_rate_collector import ExchangeRateCollector
from utils.buy_signal_analyzer import BuySignalAnalyzer
from utils.signal_message_formatter import SignalMessageFormatter
from modules.mysql_connector import MySQLConnector

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


def get_weekly_rates(db_connector, currency, days=7):
    """최근 N일간의 환율 데이터 조회 (스파크라인용)"""
    query = """
    SELECT deal_bas_r
    FROM exchange_rates
    WHERE cur_unit = %s
    AND search_date >= %s
    ORDER BY search_date ASC
    """
    try:
        end_date = datetime.now().date()
        start_date = end_date - timedelta(days=days)
        connection = db_connector.get_connection()
        with connection.cursor() as cursor:
            cursor.execute(query, (currency, start_date))
            return [float(row[0]) for row in cursor.fetchall()]
    except Exception as e:
        logger.error(f"{currency} 주간 환율 조회 중 오류 발생: {str(e)}")
        return []


def main():
    """환율 데이터 수집, 시각화 및 알림을 처리하는 노티파이어"""
    try:
        # 텔레그램 설정 가져오기
        credentials = get_credentials()
        telegram = TelegramSender(chat_id=credentials['chat_id'])
        logger.debug("텔레그램 Sender 초기화 완료")

        # Database Connector 초기화
        db_connector = MySQLConnector()
        logger.info("DB Connector 초기화 완료")

        # 1. Exchange Rate Collector 실행
        collector = ExchangeRateCollector(db_connector)
        collector.run()
        logger.info("환율 데이터를 성공적으로 수집했습니다.")

        # 2. 오늘과 어제의 환율 정보 조회
        today = datetime.now().date()
        yesterday = today - timedelta(days=1)

        today_rates = get_exchange_rates(db_connector, today)

        if not today_rates:
            logger.info("오늘의 환율 데이터가 없습니다 (공휴일/주말). 알림을 건너뜁니다.")
            return

        yesterday_rates = get_exchange_rates(db_connector, yesterday)

        # 3. 7일간 환율 데이터로 스파크라인 생성
        sparklines = {}
        for currency in ['USD', 'JPY(100)']:
            week_data = get_weekly_rates(db_connector, currency)
            sparklines[currency] = SparklineGenerator.generate(week_data)

        # 4. HTMLMessageFormatter로 rates를 {currency: float} 형태로 변환
        rates_for_formatter = {}
        for currency, data in today_rates.items():
            rates_for_formatter[currency] = data['deal_bas_r']

        yesterday_rates_for_formatter = {}
        for currency, data in yesterday_rates.items():
            yesterday_rates_for_formatter[currency] = data['deal_bas_r']

        # 5. HTML 포맷 메시지 생성
        formatter = HTMLMessageFormatter()
        message = formatter.format_message(
            date=today.strftime('%Y-%m-%d'),
            rates=rates_for_formatter,
            yesterday_rates=yesterday_rates_for_formatter,
            sparklines=sparklines,
        )

        # 6. 텍스트 메시지 전송 (기본)
        if not telegram.send_message(message, parse_mode='HTML'):
            logger.error("텔레그램 메시지 전송 실패")

        # 7. 그래프 이미지 전송 (선택)
        if is_send_graph_enabled():
            visualizer = ExchangeRateVisualizer(db_connector)
            graph_path = visualizer.create_visualization(months=3)
            logger.info(f"환율 그래프가 생성되었습니다: {graph_path}")
            if graph_path and not telegram.send_message(
                "📈 3개월간 환율 변동 그래프", file_path=graph_path
            ):
                logger.error("텔레그램 그래프 이미지 전송 실패")

    except Exception as e:
        logger.error(f"스크립트 실행 중 오류 발생: {str(e)}", exc_info=True)
    finally:
        if 'db_connector' in locals():
            db_connector.close()


def run_buy_signal_analysis() -> None:
    """
    매수 신호 분석 후 신호가 있으면 즉시 텔레그램으로 전송한다.
    스케줄러에서 평일 오후 2:40에 호출된다.
    """
    try:
        db_connector = MySQLConnector()
        try:
            today = datetime.now().date()
            today_rates = get_exchange_rates(db_connector, today)

            rates_for_analysis: dict[str, float] = {}
            for currency, data in today_rates.items():
                rates_for_analysis[currency] = data['deal_bas_r']

            if not rates_for_analysis:
                logger.warning("매수 신호 분석: 오늘의 환율 데이터가 없습니다")
                return

            analyzer = BuySignalAnalyzer(db_connector)
            signals = analyzer.analyze(rates_for_analysis)

            if not signals:
                logger.info("매수 신호 분석 완료: 감지된 신호 없음")
                return

            # 매수 신호만 필터링 (주의 신호 제외)
            buy_signal_types = {"n_week_low", "golden_cross", "rsi_oversold", "bollinger_low"}
            buy_signals = [s for s in signals if s.signal_type in buy_signal_types]

            if not buy_signals:
                logger.info("매수 신호 분석 완료: 매수 타이밍 신호 없음 (주의 신호만 감지)")
                return

            # 매수 신호가 있으면 즉시 전송
            credentials = get_credentials()
            telegram = TelegramSender(chat_id=credentials['chat_id'])
            signal_msg = SignalMessageFormatter().format_signals(buy_signals)
            if telegram.send_message(signal_msg, parse_mode='HTML'):
                logger.info(f"매수 신호 메시지 전송 완료 ({len(buy_signals)}개 신호)")
            else:
                logger.error("매수 신호 텔레그램 메시지 전송 실패")
        finally:
            db_connector.close()
    except Exception as e:
        logger.error(f"매수 신호 분석 중 오류 발생: {str(e)}", exc_info=True)


if __name__ == "__main__":
    main()
