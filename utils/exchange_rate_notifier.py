import logging
from datetime import datetime, timedelta

from modules.telegram_sender import TelegramSender
from configs.telegram_setting import get_credentials, is_send_graph_enabled
from utils.sparkline_generator import SparklineGenerator
from utils.html_message_formatter import HTMLMessageFormatter
from utils.exchange_rate_visualizer import ExchangeRateVisualizer
from utils.exchange_rate_collector import ExchangeRateCollector
from utils.toss_usd_collector import TossUSDCollector
from utils.gold_price_collector import GoldPriceCollector
from utils.gold_price_visualizer import GoldPriceVisualizer
from utils.gold_message_formatter import GoldMessageFormatter
from utils.krx_gold_client import GOLD_1KG_ISU_CD
from utils.buy_signal_analyzer import BuySignalAnalyzer
from utils.signal_message_formatter import SignalMessageFormatter
from utils.time_utils import kst_today
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
        end_date = kst_today()
        start_date = end_date - timedelta(days=days)
        connection = db_connector.get_connection()
        with connection.cursor() as cursor:
            cursor.execute(query, (currency, start_date))
            return [float(row[0]) for row in cursor.fetchall()]
    except Exception as e:
        logger.error(f"{currency} 주간 환율 조회 중 오류 발생: {str(e)}")
        return []


def get_latest_gold(db_connector):
    """가장 최근 거래일의 금 99.99_1kg 종가 정보 조회"""
    query = """
    SELECT isu_nm, clsprc, cmpprevdd_prc, fluc_rt, search_date
    FROM gold_prices
    WHERE isu_cd = %s
    ORDER BY search_date DESC
    LIMIT 1
    """
    try:
        connection = db_connector.get_connection()
        with connection.cursor() as cursor:
            cursor.execute(query, (GOLD_1KG_ISU_CD,))
            row = cursor.fetchone()
        if not row:
            return None
        return {
            'isu_nm': row[0],
            'clsprc': float(row[1]),
            'cmpprevdd_prc': float(row[2]),
            'fluc_rt': float(row[3]),
            'search_date': row[4],
        }
    except Exception as e:
        logger.error(f"금시세 조회 중 오류 발생: {str(e)}")
        return None


def get_weekly_gold(db_connector, days=7):
    """최근 N일간의 금 종가 조회 (스파크라인용)"""
    query = """
    SELECT clsprc
    FROM gold_prices
    WHERE isu_cd = %s AND search_date >= %s
    ORDER BY search_date ASC
    """
    try:
        start_date = kst_today() - timedelta(days=days)
        connection = db_connector.get_connection()
        with connection.cursor() as cursor:
            cursor.execute(query, (GOLD_1KG_ISU_CD, start_date))
            return [float(row[0]) for row in cursor.fetchall()]
    except Exception as e:
        logger.error(f"금시세 주간 조회 중 오류 발생: {str(e)}")
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

        # 1. 환율 수집 (USD=토스 실시간, JPY=수출입은행). 하나가 실패해도 다른 하나는 진행
        try:
            TossUSDCollector(db_connector).run()
        except Exception as e:
            logger.error(f"USD(토스) 수집 실패: {e}", exc_info=True)
        try:
            ExchangeRateCollector(db_connector).run()  # JPY(100)
        except Exception as e:
            logger.error(f"JPY(수출입은행) 수집 실패: {e}", exc_info=True)
        try:
            GoldPriceCollector(db_connector).run()  # KRX 금시세
        except Exception as e:
            logger.error(f"금시세(KRX) 수집 실패: {e}", exc_info=True)
        logger.info("환율/금시세 데이터 수집 단계 완료.")

        # 2. 오늘과 어제의 환율 정보 조회 (KST 기준)
        today = kst_today()
        yesterday = today - timedelta(days=1)

        today_rates = get_exchange_rates(db_connector, today)

        if not today_rates:
            logger.info("오늘의 환율 데이터가 없습니다 (공휴일/주말). 환율 알림을 건너뜁니다.")
            # 환율이 없어도 금시세는 별도로 전송 시도 (시장 휴일이 다를 수 있음)
            _send_gold(db_connector, telegram)
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

        # 8. 매수 신호 분석 및 전송 (하루 1회이므로 알림과 함께 처리)
        _send_buy_signals(db_connector, telegram, rates_for_formatter)

        # 9. 금시세 알림 및 그래프 전송
        _send_gold(db_connector, telegram)

    except Exception as e:
        logger.error(f"스크립트 실행 중 오류 발생: {str(e)}", exc_info=True)
    finally:
        if 'db_connector' in locals():
            db_connector.close()


def _send_buy_signals(db_connector, telegram, rates_for_analysis: dict[str, float]) -> None:
    """
    저가매기 매수 신호를 분석해 신호가 있으면 텔레그램으로 전송한다.

    모든 신호 유형이 매수 관점이므로 별도 필터링은 하지 않는다.
    분석/전송 중 오류가 나도 상위 알림 흐름을 막지 않도록 예외를 삼킨다.
    """
    try:
        if not rates_for_analysis:
            logger.warning("매수 신호 분석: 분석할 환율 데이터가 없습니다")
            return

        signals = BuySignalAnalyzer(db_connector).analyze(rates_for_analysis)
        if not signals:
            logger.info("매수 신호 분석 완료: 감지된 신호 없음")
            return

        signal_msg = SignalMessageFormatter().format_signals(signals)
        if telegram.send_message(signal_msg, parse_mode='HTML'):
            logger.info(f"매수 신호 메시지 전송 완료 ({len(signals)}개 신호)")
        else:
            logger.error("매수 신호 텔레그램 메시지 전송 실패")
    except Exception as e:
        logger.error(f"매수 신호 분석 중 오류 발생: {str(e)}", exc_info=True)


def _send_gold(db_connector, telegram) -> None:
    """금시세 메시지와 그래프를 전송한다. 오류가 나도 상위 흐름을 막지 않는다."""
    try:
        gold = get_latest_gold(db_connector)
        if not gold:
            logger.info("금시세 데이터가 없습니다. 금 알림을 건너뜁니다.")
            return

        sparkline = SparklineGenerator.generate(get_weekly_gold(db_connector))
        message = GoldMessageFormatter().format_message(
            date=gold['search_date'].strftime('%Y-%m-%d'),
            gold=gold,
            sparkline=sparkline,
        )
        if not telegram.send_message(message, parse_mode='HTML'):
            logger.error("금시세 텔레그램 메시지 전송 실패")

        if is_send_graph_enabled():
            graph_path = GoldPriceVisualizer(db_connector).create_visualization(months=3)
            if graph_path and not telegram.send_message(
                "🥇 3개월간 금시세 변동 그래프", file_path=graph_path
            ):
                logger.error("금시세 그래프 이미지 전송 실패")
    except Exception as e:
        logger.error(f"금시세 알림 처리 중 오류 발생: {str(e)}", exc_info=True)


if __name__ == "__main__":
    main()
