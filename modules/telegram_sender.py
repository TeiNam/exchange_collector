# modules/telegram_sender.py
import logging
import os
from pathlib import Path
from typing import Optional, Union

import requests

from configs.telegram_setting import get_credentials

logger = logging.getLogger(__name__)


class TelegramSender:
    """텔레그램 봇 API를 통해 메시지와 파일을 전송하는 클래스"""

    TELEGRAM_API_BASE = "https://api.telegram.org/bot{token}"
    TIMEOUT = 60  # API 호출 타임아웃 (초)

    def __init__(self, chat_id: Optional[str] = None):
        """
        TelegramSender 초기화
        :param chat_id: 메시지를 전송할 채팅 ID (선택사항)
        """
        credentials = get_credentials()
        self.bot_token = credentials['bot_token']
        self.default_chat_id = chat_id or credentials['chat_id']

        if not self.bot_token:
            raise ValueError("TELEGRAM_BOT_TOKEN이 설정되지 않았습니다.")

        self.api_base = self.TELEGRAM_API_BASE.format(token=self.bot_token)
        logger.debug(f"TelegramSender 초기화 완료 (채팅 ID: {self.default_chat_id})")

    def _validate_file_path(self, file_path: Union[str, Path]) -> Optional[Path]:
        """
        파일 경로를 검증하고 Path 객체로 변환
        :param file_path: 검증할 파일 경로
        :return: 검증된 Path 객체 또는 None
        """
        try:
            if not isinstance(file_path, (str, os.PathLike)):
                logger.error(f"잘못된 파일 경로 타입: {type(file_path)}. 문자열 또는 Path 객체여야 합니다.")
                return None

            path = Path(file_path)
            if not path.exists():
                logger.error(f"파일이 존재하지 않습니다: {path}")
                return None
            if not path.is_file():
                logger.error(f"파일이 아닙니다: {path}")
                return None

            return path

        except Exception as e:
            logger.error(f"파일 경로 검증 중 오류 발생: {str(e)}")
            return None

    def send_message(self,
                     text: str,
                     file_path: Optional[Union[str, Path]] = None,
                     chat_id: Optional[str] = None,
                     parse_mode: Optional[str] = None) -> bool:
        """
        텔레그램으로 메시지와 파일을 전송
        :param text: 전송할 메시지 텍스트
        :param file_path: 첨부할 파일 경로 (선택사항)
        :param chat_id: 메시지를 전송할 채팅 ID (선택사항)
        :param parse_mode: 메시지 파싱 모드 (예: 'HTML', 'Markdown') (선택사항)
        :return: 전송 성공 여부
        """
        try:
            # 빈 메시지 검증 (공백만 있는 경우 포함)
            if not text or not text.strip():
                logger.error("메시지 내용이 비어있습니다.")
                return False

            use_chat_id = chat_id or self.default_chat_id
            if not use_chat_id:
                logger.error("채팅 ID가 지정되지 않았습니다.")
                return False

            # 파일이 있으면 사진 전송
            if file_path:
                validated_path = self._validate_file_path(file_path)
                if not validated_path:
                    return False

                # 텍스트 메시지 먼저 전송
                if not self._send_text(use_chat_id, text, parse_mode):
                    return False

                # 사진 전송
                if not self._send_photo(use_chat_id, validated_path):
                    return False
            else:
                # 텍스트 메시지만 전송
                if not self._send_text(use_chat_id, text, parse_mode):
                    return False

            return True

        except Exception as e:
            logger.error(f"메시지 전송 중 예외 발생: {str(e)}", exc_info=True)
            return False

    def _send_text(self, chat_id: str, text: str,
                   parse_mode: Optional[str] = None) -> bool:
        """
        텍스트 메시지 전송 (sendMessage API 호출)
        :param chat_id: 대상 채팅 ID
        :param text: 전송할 텍스트
        :param parse_mode: 파싱 모드 (예: 'HTML')
        :return: 전송 성공 여부
        """
        url = f"{self.api_base}/sendMessage"
        payload = {
            "chat_id": chat_id,
            "text": text,
        }

        # parse_mode가 지정된 경우 요청에 포함
        if parse_mode:
            payload["parse_mode"] = parse_mode

        try:
            response = requests.post(url, json=payload, timeout=self.TIMEOUT)
            response.raise_for_status()

            result = response.json()
            if not result.get("ok"):
                logger.error(f"텔레그램 메시지 전송 실패: {result.get('description', '알 수 없는 오류')}")
                return False

            logger.info(f"텔레그램 메시지 전송 성공 (채팅 ID: {chat_id})")
            return True

        except requests.exceptions.RequestException as e:
            logger.error(f"텔레그램 API 호출 실패: {str(e)}")
            return False

    def _send_photo(self, chat_id: str, file_path: Path,
                    caption: str = "") -> bool:
        """
        이미지 파일 전송 (sendPhoto API 호출)
        :param chat_id: 대상 채팅 ID
        :param file_path: 전송할 이미지 파일 경로
        :param caption: 이미지 캡션 (선택사항)
        :return: 전송 성공 여부
        """
        url = f"{self.api_base}/sendPhoto"
        data = {"chat_id": chat_id}

        if caption:
            data["caption"] = caption

        try:
            with open(file_path, "rb") as photo_file:
                files = {"photo": (file_path.name, photo_file)}
                response = requests.post(
                    url, data=data, files=files, timeout=self.TIMEOUT
                )
                response.raise_for_status()

            result = response.json()
            if not result.get("ok"):
                logger.error(f"텔레그램 사진 전송 실패: {result.get('description', '알 수 없는 오류')}")
                return False

            logger.info(f"텔레그램 사진 전송 성공: {file_path.name}")
            return True

        except requests.exceptions.RequestException as e:
            logger.error(f"텔레그램 사진 API 호출 실패: {str(e)}")
            return False


# 테스트 코드
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)

    try:
        sender = TelegramSender()
        success = sender.send_message(
            text="환율 데이터 알림 테스트입니다.",
            parse_mode="HTML"
        )
        print(f"전송 {'성공' if success else '실패'}")
    except Exception as e:
        print(f"오류 발생: {str(e)}")
