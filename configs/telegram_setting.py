import os
from pathlib import Path
from dotenv import load_dotenv
import logging

logger = logging.getLogger(__name__)


class TelegramSettings:
    """텔레그램 봇 설정을 관리하는 싱글톤 클래스"""
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialize()
        return cls._instance

    def _initialize(self):
        """환경변수에서 텔레그램 설정 로드"""
        # 프로젝트 루트 디렉토리 찾기
        project_root = Path(__file__).parent.parent
        env_path = project_root / '.env'

        # .env 파일 로드
        if env_path.exists():
            load_dotenv(dotenv_path=env_path)
        else:
            logger.warning(f".env 파일을 찾을 수 없습니다: {env_path}")

        # 텔레그램 설정 로드
        self.bot_token = self._get_env_value('TELEGRAM_BOT_TOKEN')
        self.chat_id = self._get_env_value('TELEGRAM_CHAT_ID')

        # 그래프 전송 설정 로드 (기본값: false)
        send_graph_value = self._get_env_value('TELEGRAM_SEND_GRAPH')
        self._send_graph = send_graph_value.lower() == 'true'

        # 필수 설정 검증
        self._validate_settings()

    def _get_env_value(self, key: str) -> str:
        """환경변수 값을 가져오고 정리"""
        value = os.getenv(key, '').strip()
        if value and value[0] in ['"', "'"] and value[-1] in ['"', "'"]:
            value = value[1:-1]
        return value

    def _validate_settings(self):
        """필수 설정값 검증"""
        if not self.bot_token:
            raise ValueError("TELEGRAM_BOT_TOKEN이 설정되지 않았습니다.")
        if not self.chat_id:
            raise ValueError("TELEGRAM_CHAT_ID가 설정되지 않았습니다.")

    @property
    def send_graph(self) -> bool:
        """그래프 이미지 전송 여부"""
        return self._send_graph

    def get_credentials(self) -> dict:
        """텔레그램 인증 정보 반환"""
        return {
            'bot_token': self.bot_token,
            'chat_id': self.chat_id
        }


# 싱글톤 인스턴스 생성
telegram_settings = TelegramSettings()


def get_credentials() -> dict:
    """텔레그램 인증 정보 반환"""
    return telegram_settings.get_credentials()


def is_send_graph_enabled() -> bool:
    """그래프 전송 활성화 여부 반환"""
    return telegram_settings.send_graph
