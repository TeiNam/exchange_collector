"""
TelegramSettings 단위 테스트 (Unit Tests)

Feature: slack-to-telegram-migration
테스트 대상: configs/telegram_setting.py - TelegramSettings 클래스

속성 테스트(test_telegram_setting_properties.py)와 중복되지 않는
구체적 시나리오 및 에러 조건을 검증한다.
"""

import os
import pytest
from unittest.mock import patch

from configs.telegram_setting import TelegramSettings


@pytest.fixture(autouse=True)
def reset_singleton():
    """각 테스트 전후에 싱글톤 인스턴스를 초기화"""
    TelegramSettings._instance = None
    yield
    TelegramSettings._instance = None


class TestTelegramSettingsValidation:
    """TelegramSettings 필수 설정값 검증 테스트"""

    def test_missing_bot_token_raises_value_error(self):
        """
        토큰 미설정 시 ValueError 발생 확인

        TELEGRAM_BOT_TOKEN이 비어있으면 ValueError가 발생하고,
        에러 메시지에 누락된 설정 항목이 명시되어야 한다.

        Validates: Requirements 1.2
        """
        env_vars = {
            'TELEGRAM_BOT_TOKEN': '',
            'TELEGRAM_CHAT_ID': 'test-chat-id',
            'TELEGRAM_SEND_GRAPH': 'false',
        }

        with patch.dict(os.environ, env_vars, clear=False):
            with pytest.raises(ValueError, match="TELEGRAM_BOT_TOKEN"):
                TelegramSettings()

    def test_missing_chat_id_raises_value_error(self):
        """
        채팅 ID 미설정 시 ValueError 발생 확인

        TELEGRAM_CHAT_ID가 비어있으면 ValueError가 발생하고,
        에러 메시지에 누락된 설정 항목이 명시되어야 한다.

        Validates: Requirements 1.3
        """
        env_vars = {
            'TELEGRAM_BOT_TOKEN': 'valid-bot-token',
            'TELEGRAM_CHAT_ID': '',
            'TELEGRAM_SEND_GRAPH': 'false',
        }

        with patch.dict(os.environ, env_vars, clear=False):
            with pytest.raises(ValueError, match="TELEGRAM_CHAT_ID"):
                TelegramSettings()

    def test_send_graph_defaults_to_false_when_not_set(self):
        """
        TELEGRAM_SEND_GRAPH 미설정 시 기본값 false 확인

        TELEGRAM_SEND_GRAPH 환경변수가 설정되지 않은 경우,
        send_graph 속성은 False를 반환해야 한다.

        Validates: Requirements 1.7
        """
        # TELEGRAM_SEND_GRAPH를 환경변수에서 제거하여 미설정 상태 재현
        env_vars = {
            'TELEGRAM_BOT_TOKEN': 'valid-bot-token',
            'TELEGRAM_CHAT_ID': 'valid-chat-id',
        }

        # 기존 TELEGRAM_SEND_GRAPH 환경변수가 있을 수 있으므로 제거
        with patch.dict(os.environ, env_vars, clear=False):
            os.environ.pop('TELEGRAM_SEND_GRAPH', None)
            instance = TelegramSettings()
            assert instance.send_graph is False
