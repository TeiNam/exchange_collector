# modules/telegram_bot.py
"""텔레그램 봇 명령어 핸들러 모듈

/start - 환영 메시지
/rate - 금일 환율 조회
하단 메뉴 버튼으로 명령어 접근 가능
"""

import logging
from datetime import datetime, timedelta

from telegram import BotCommand, InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import Application, CommandHandler, ContextTypes

from configs.telegram_setting import get_credentials
from modules.mysql_connector import MySQLConnector
from utils.sparkline_generator import SparklineGenerator
from utils.html_message_formatter import HTMLMessageFormatter
from utils.exchange_rate_visualizer import ExchangeRateVisualizer
from utils.toss_exchange_client import TossExchangeClient
from utils.time_utils import kst_today

logger = logging.getLogger(__name__)

# 토스 클라이언트는 토큰 캐시를 재사용하기 위해 봇 수명 동안 단일 인스턴스로 유지
_toss_client = TossExchangeClient()

# rateChangeType → 이모지 매핑
_CHANGE_EMOJI = {"UP": "🔺", "DOWN": "🔻", "FLAT": "➖"}


def _fmt_time(iso_str: str) -> str:
    """ISO8601 시각을 HH:MM으로 축약한다. 파싱 실패 시 원본을 반환한다."""
    try:
        return datetime.fromisoformat(iso_str).strftime("%H:%M")
    except (ValueError, TypeError):
        return iso_str


def _get_exchange_rates(db_connector, date):
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


def _get_weekly_rates(db_connector, currency, days=7):
    """최근 N일간의 환율 데이터 조회 (스파크라인용)"""
    query = """
    SELECT deal_bas_r
    FROM exchange_rates
    WHERE cur_unit = %s AND search_date >= %s
    ORDER BY search_date ASC
    """
    start_date = kst_today() - timedelta(days=days)
    connection = db_connector.get_connection()
    with connection.cursor() as cursor:
        cursor.execute(query, (currency, start_date))
        return [float(row[0]) for row in cursor.fetchall()]


async def start_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """/start 명령어 핸들러"""
    welcome_message = (
        "👋 안녕하세요! <b>환율 알림 봇</b>입니다.\n\n"
        "📊 매일 오후 3:40(KST)에 환율 정보와 저가매수 신호를 알려드립니다.\n"
        "🔴 빨간날엔 쉽니다.\n\n"
        "💵 달러(USD)\n"
        "💴 엔화(JPY)\n\n"
        "📌 <b>명령어 안내</b>\n"
        "/now - USD 실시간 환율\n"
        "/rate - 금일 환율 조회\n\n"
        "하단 메뉴에서도 사용할 수 있어요 🙂"
    )
    # 후원하기 인라인 버튼
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("☕ 후원하기", url="https://qr.kakaopay.com/Ej74xpc815dc06149")]
    ])
    await update.message.reply_text(welcome_message, parse_mode="HTML", reply_markup=keyboard)
    logger.info(f"/start 명령어 처리 완료 (사용자: {update.effective_user.id})")


async def rate_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """/rate 명령어 핸들러 - 금일 환율 조회"""
    db_connector = None
    try:
        db_connector = MySQLConnector()

        # 최신 데이터 날짜 조회
        conn = db_connector.get_connection()
        with conn.cursor() as cursor:
            cursor.execute("SELECT MAX(search_date) FROM exchange_rates")
            latest_date = cursor.fetchone()[0]

        if not latest_date:
            await update.message.reply_text("📭 환율 데이터가 없습니다.")
            return

        # 환율 조회
        today_rates = _get_exchange_rates(db_connector, latest_date)
        yesterday = latest_date - timedelta(days=1)
        yesterday_rates = _get_exchange_rates(db_connector, yesterday)

        if not today_rates:
            await update.message.reply_text("📭 환율 데이터가 없습니다.")
            return

        # 스파크라인 생성
        sparklines = {}
        for currency in ['USD', 'JPY(100)']:
            week_data = _get_weekly_rates(db_connector, currency)
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

        await update.message.reply_text(message, parse_mode="HTML")

        # 그래프 생성 및 전송
        visualizer = ExchangeRateVisualizer(db_connector)
        graph_path = visualizer.create_visualization(months=3)
        if graph_path:
            with open(graph_path, 'rb') as photo:
                await update.message.reply_photo(photo=photo)

        logger.info(f"/rate 명령어 처리 완료 (사용자: {update.effective_user.id})")

    except Exception as e:
        logger.error(f"/rate 처리 중 오류: {e}", exc_info=True)
        await update.message.reply_text("⚠️ 환율 조회 중 오류가 발생했습니다.")
    finally:
        if db_connector:
            db_connector.close()


async def now_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """/now 명령어 핸들러 - 토스 API로 USD 실시간 환율 조회 (DB 미저장)"""
    try:
        rate = _toss_client.get_usd_krw()
        change = _CHANGE_EMOJI.get(rate['rate_change_type'], "")
        message = (
            "💵 <b>USD 실시간 환율</b>\n\n"
            f"매매기준율: <b>{rate['mid_rate']:,.2f}원</b> {change}\n"
            f"매수 환율: {rate['rate']:,.2f}원\n\n"
            f"⏱ 유효: {_fmt_time(rate['valid_from'])} ~ {_fmt_time(rate['valid_until'])}\n"
            "<i>토스증권 참고용 표시 환율 (1분 갱신)</i>"
        )
        await update.message.reply_text(message, parse_mode="HTML")
        logger.info(f"/now 명령어 처리 완료 (사용자: {update.effective_user.id})")
    except Exception as e:
        logger.error(f"/now 처리 중 오류: {e}", exc_info=True)
        await update.message.reply_text("⚠️ 실시간 환율 조회 중 오류가 발생했습니다.")


async def help_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """/help 명령어 핸들러"""
    help_message = (
        "📌 <b>명령어 안내</b>\n\n"
        "/now - ⚡ USD 실시간 환율 (토스)\n"
        "/rate - 💱 금일 환율 조회\n"
        "/help - ❓ 명령어 안내\n"
        "/start - 👋 시작 메시지\n\n"
        "📊 매일 오후 3:40(KST)에 환율 알림이 자동 전송됩니다.\n"
        "🚨 저가매수 타이밍 감지 시 신호 메시지도 함께 전송됩니다."
    )
    await update.message.reply_text(help_message, parse_mode="HTML")
    logger.info(f"/help 명령어 처리 완료 (사용자: {update.effective_user.id})")


async def post_init(application: Application):
    """봇 시작 후 하단 메뉴 버튼 설정"""
    commands = [
        BotCommand("now", "⚡ USD 실시간 환율"),
        BotCommand("rate", "💱 금일 환율 조회"),
        BotCommand("help", "❓ 명령어 안내"),
        BotCommand("start", "👋 시작 메시지"),
    ]
    await application.bot.set_my_commands(commands)
    logger.info("텔레그램 봇 메뉴 버튼 설정 완료")


def create_bot_application() -> Application:
    """텔레그램 봇 Application 생성 및 핸들러 등록"""
    credentials = get_credentials()
    bot_token = credentials['bot_token']

    application = Application.builder().token(bot_token).post_init(post_init).build()

    # 명령어 핸들러 등록
    application.add_handler(CommandHandler("start", start_handler))
    application.add_handler(CommandHandler("now", now_handler))
    application.add_handler(CommandHandler("rate", rate_handler))
    application.add_handler(CommandHandler("help", help_handler))

    logger.info("텔레그램 봇 핸들러 등록 완료")
    return application
