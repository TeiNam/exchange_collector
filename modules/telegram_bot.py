# modules/telegram_bot.py
"""텔레그램 봇 명령어 핸들러 모듈

/start 명령어를 처리하고, 기존 스케줄러와 함께 실행된다.
python-telegram-bot 라이브러리의 Application을 사용하여 폴링 방식으로 동작한다.
"""

import logging
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes

from configs.telegram_setting import get_credentials

logger = logging.getLogger(__name__)


async def start_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    /start 명령어 핸들러
    봇이 처음 시작될 때 환영 메시지를 전송한다.
    """
    welcome_message = (
        "👋 안녕하세요! <b>환율 알림 봇</b>입니다.\n\n"
        "📊 매일 오전 11:05(KST)에 환율 정보를 알려드립니다.\n\n"
        "💵 달러(USD)\n"
        "💴 엔화(JPY)\n\n"
        "알림은 자동으로 전송됩니다. 잠시만 기다려주세요! 🙂"
    )

    await update.message.reply_text(welcome_message, parse_mode="HTML")
    logger.info(f"/start 명령어 처리 완료 (사용자: {update.effective_user.id})")


def create_bot_application() -> Application:
    """텔레그램 봇 Application 생성 및 핸들러 등록"""
    credentials = get_credentials()
    bot_token = credentials['bot_token']

    application = Application.builder().token(bot_token).build()

    # 명령어 핸들러 등록
    application.add_handler(CommandHandler("start", start_handler))

    logger.info("텔레그램 봇 핸들러 등록 완료")
    return application
