"""실제 환율 데이터를 텔레그램으로 전송하는 테스트 스크립트"""

import logging
from datetime import datetime, timedelta

from modules.mysql_connector import MySQLConnector
from modules.telegram_sender import TelegramSender
from utils.sparkline_generator import SparklineGenerator
from utils.html_message_formatter import HTMLMessageFormatter
from utils.exchange_rate_visualizer import ExchangeRateVisualizer
from utils.buy_signal_analyzer import Signal
from utils.signal_message_formatter import SignalMessageFormatter
from configs.telegram_setting import get_credentials

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
    connection = db_connector.get_connection()
    with connection.cursor() as cursor:
        cursor.execute(query, (date,))
        return {row[0]: {"deal_bas_r": row[1], "bkpr": row[2]} for row in cursor.fetchall()}


def get_weekly_rates(db_connector, currency, days=7):
    """최근 N일간의 환율 데이터 조회 (스파크라인용)"""
    query = """
    SELECT deal_bas_r
    FROM exchange_rates
    WHERE cur_unit = %s
    AND search_date >= %s
    ORDER BY search_date ASC
    """
    end_date = datetime.now().date()
    start_date = end_date - timedelta(days=days)
    connection = db_connector.get_connection()
    with connection.cursor() as cursor:
        cursor.execute(query, (currency, start_date))
        return [float(row[0]) for row in cursor.fetchall()]


def main():
    db_connector = None
    try:
        # 초기화
        db_connector = MySQLConnector()
        credentials = get_credentials()
        telegram = TelegramSender(chat_id=credentials['chat_id'])

        # 최근 데이터가 있는 날짜 조회
        conn = db_connector.get_connection()
        with conn.cursor() as cursor:
            cursor.execute("SELECT MAX(search_date) FROM exchange_rates")
            latest_date = cursor.fetchone()[0]

        logger.info(f"최신 데이터 날짜: {latest_date}")

        # 환율 조회
        today_rates = get_exchange_rates(db_connector, latest_date)
        yesterday = latest_date - timedelta(days=1)
        yesterday_rates = get_exchange_rates(db_connector, yesterday)

        # 스파크라인 생성
        sparklines = {}
        for currency in ['USD', 'JPY(100)']:
            week_data = get_weekly_rates(db_connector, currency)
            sparklines[currency] = SparklineGenerator.generate(week_data)

        # HTML 메시지 생성
        rates = {c: d['deal_bas_r'] for c, d in today_rates.items()}
        y_rates = {c: d['deal_bas_r'] for c, d in yesterday_rates.items()}

        formatter = HTMLMessageFormatter()
        message = formatter.format_message(
            date=latest_date.strftime('%Y-%m-%d'),
            rates=rates,
            yesterday_rates=y_rates,
            sparklines=sparklines,
        )

        # 텍스트 메시지 전송
        if telegram.send_message(message, parse_mode='HTML'):
            logger.info("텍스트 메시지 전송 성공")
        else:
            logger.error("텍스트 메시지 전송 실패")

        # 그래프 생성 및 전송
        visualizer = ExchangeRateVisualizer(db_connector)
        graph_path = visualizer.create_visualization(months=3)
        if graph_path and telegram.send_message("📈 3개월간 환율 변동 그래프", file_path=graph_path):
            logger.info("그래프 전송 성공")
        else:
            logger.error("그래프 전송 실패")

        # 가짜 매수 신호 생성 및 전송 (테스트용)
        usd_rate = rates.get('USD', 1425.0)
        jpy_rate = rates.get('JPY(100)', 945.0)
        fake_signals = [
            Signal(
                currency="USD",
                signal_type="n_week_low",
                message="4주(20 영업일) 만에 최저가입니다. 매수를 고려해보세요",
                current_rate=float(usd_rate),
                indicator_value=float(usd_rate) + 5.0,
            ),
            Signal(
                currency="USD",
                signal_type="rsi_oversold",
                message="RSI 28.5 - 과매도 구간, 반등 가능성",
                current_rate=float(usd_rate),
                indicator_value=28.5,
            ),
            Signal(
                currency="JPY(100)",
                signal_type="golden_cross",
                message="골든크로스 발생 - 단기 MA가 장기 MA를 상향 돌파",
                current_rate=float(jpy_rate),
                indicator_value=None,
            ),
            Signal(
                currency="JPY(100)",
                signal_type="bollinger_low",
                message=f"볼린저 밴드 하단({float(jpy_rate) + 3:.2f}) 터치 - 매수 신호",
                current_rate=float(jpy_rate),
                indicator_value=float(jpy_rate) + 3.0,
            ),
        ]

        signal_msg = SignalMessageFormatter().format_signals(fake_signals)
        if telegram.send_message(signal_msg, parse_mode='HTML'):
            logger.info("매수 신호 테스트 메시지 전송 성공")
        else:
            logger.error("매수 신호 테스트 메시지 전송 실패")

    except Exception as e:
        logger.error(f"오류 발생: {e}", exc_info=True)
    finally:
        if db_connector:
            db_connector.close()


if __name__ == "__main__":
    main()
