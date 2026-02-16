"""
TelegramSender 단위 테스트 (Unit Tests)

Feature: slack-to-telegram-migration
테스트 대상: modules/telegram_sender.py - TelegramSender 클래스

속성 테스트(Property-Based Tests)에서 커버하지 않는 구체적 시나리오를 검증한다:
1. 파일 전송 시 sendPhoto 엔드포인트 호출 확인 (Property 5)
2. parse_mode='HTML' 전달 시 요청 본문에 포함 확인
3. 메서드 시그니처 호환성 확인

Validates: Requirements 2.2, 2.3, 2.8
"""

import inspect
import tempfile
from pathlib import Path
from typing import Optional, Union
from unittest.mock import MagicMock, patch

import pytest

from configs.telegram_setting import TelegramSettings


# --- 헬퍼 함수 ---

MOCK_CREDENTIALS = {
    "bot_token": "test-bot-token-12345",
    "chat_id": "test-chat-id-67890",
}


def _make_success_response():
    """텔레그램 API 성공 응답 Mock 생성"""
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {"ok": True, "result": {"message_id": 1}}
    mock_resp.raise_for_status.return_value = None
    return mock_resp


def _create_sender():
    """테스트용 TelegramSender 인스턴스 생성 (get_credentials 모킹)"""
    from modules.telegram_sender import TelegramSender

    with patch("modules.telegram_sender.get_credentials", return_value=MOCK_CREDENTIALS):
        sender = TelegramSender()
    return sender


# --- 픽스처 ---

@pytest.fixture(autouse=True)
def reset_singleton():
    """각 테스트 전에 싱글톤 인스턴스를 초기화"""
    TelegramSettings._instance = None
    yield
    TelegramSettings._instance = None


# --- 테스트 1: 파일 전송 시 sendPhoto 엔드포인트 호출 확인 (Property 5) ---

class TestSendPhotoEndpoint:
    """
    파일 전송 시 sendPhoto 엔드포인트가 호출되는지 검증한다.

    Validates: Requirements 2.3
    Property 5: 유효한 파일 전송 (Valid File Sends Photo)
    """

    def test_file_send_calls_send_photo_endpoint(self):
        """파일 경로가 주어지면 sendPhoto 엔드포인트로 요청이 전송되어야 한다"""
        sender = _create_sender()

        # 임시 파일 생성
        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp:
            tmp.write(b"\x89PNG\r\n\x1a\n")  # PNG 헤더 바이트
            tmp_path = tmp.name

        try:
            with patch("modules.telegram_sender.requests.post") as mock_post:
                mock_post.return_value = _make_success_response()

                result = sender.send_message(
                    text="테스트 메시지",
                    file_path=tmp_path,
                )

                assert result is True, "파일 전송이 성공해야 합니다"

                # requests.post 호출 내역에서 sendPhoto URL 확인
                call_urls = [
                    call.args[0] if call.args else call.kwargs.get("url", "")
                    for call in mock_post.call_args_list
                ]

                send_photo_calls = [url for url in call_urls if "sendPhoto" in url]
                assert len(send_photo_calls) == 1, (
                    f"sendPhoto 엔드포인트가 정확히 1번 호출되어야 합니다. "
                    f"호출된 URL 목록: {call_urls}"
                )
        finally:
            Path(tmp_path).unlink(missing_ok=True)

    def test_file_send_also_calls_send_message_for_text(self):
        """파일 전송 시 텍스트 메시지도 sendMessage로 먼저 전송되어야 한다"""
        sender = _create_sender()

        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp:
            tmp.write(b"\x89PNG\r\n\x1a\n")
            tmp_path = tmp.name

        try:
            with patch("modules.telegram_sender.requests.post") as mock_post:
                mock_post.return_value = _make_success_response()

                sender.send_message(text="텍스트와 파일 함께 전송", file_path=tmp_path)

                call_urls = [
                    call.args[0] if call.args else call.kwargs.get("url", "")
                    for call in mock_post.call_args_list
                ]

                # sendMessage와 sendPhoto 모두 호출되어야 함
                assert any("sendMessage" in url for url in call_urls), (
                    "텍스트 메시지를 위한 sendMessage 호출이 있어야 합니다"
                )
                assert any("sendPhoto" in url for url in call_urls), (
                    "파일 전송을 위한 sendPhoto 호출이 있어야 합니다"
                )
        finally:
            Path(tmp_path).unlink(missing_ok=True)


# --- 테스트 2: parse_mode='HTML' 전달 시 요청 본문에 포함 확인 ---

class TestParseModeHTML:
    """
    parse_mode='HTML' 지정 시 sendMessage 요청 본문에 포함되는지 검증한다.

    Validates: Requirements 2.2
    """

    def test_parse_mode_html_included_in_request_body(self):
        """parse_mode='HTML' 전달 시 요청 JSON에 parse_mode 필드가 포함되어야 한다"""
        sender = _create_sender()

        with patch("modules.telegram_sender.requests.post") as mock_post:
            mock_post.return_value = _make_success_response()

            result = sender.send_message(text="<b>굵은 텍스트</b>", parse_mode="HTML")

            assert result is True

            # 요청 본문에서 parse_mode 확인
            call_kwargs = mock_post.call_args
            payload = call_kwargs.kwargs.get("json", {}) if call_kwargs.kwargs else {}

            assert payload.get("parse_mode") == "HTML", (
                f"요청 본문에 parse_mode='HTML'이 포함되어야 합니다. "
                f"실제 payload: {payload}"
            )

    def test_parse_mode_not_included_when_none(self):
        """parse_mode가 None이면 요청 본문에 parse_mode 필드가 없어야 한다"""
        sender = _create_sender()

        with patch("modules.telegram_sender.requests.post") as mock_post:
            mock_post.return_value = _make_success_response()

            sender.send_message(text="일반 텍스트 메시지")

            call_kwargs = mock_post.call_args
            payload = call_kwargs.kwargs.get("json", {}) if call_kwargs.kwargs else {}

            assert "parse_mode" not in payload, (
                "parse_mode가 None일 때 요청 본문에 포함되면 안 됩니다"
            )


# --- 테스트 3: 메서드 시그니처 호환성 확인 ---

class TestMethodSignatureCompatibility:
    """
    send_message 메서드가 기존 SlackSender와 호환되는 시그니처를 유지하는지 검증한다.
    필수 파라미터: text, file_path, chat_id
    추가 파라미터: parse_mode

    Validates: Requirements 2.8
    """

    def test_send_message_accepts_required_parameters(self):
        """send_message가 text, file_path, chat_id, parse_mode 파라미터를 모두 수용해야 한다"""
        from modules.telegram_sender import TelegramSender

        sig = inspect.signature(TelegramSender.send_message)
        param_names = list(sig.parameters.keys())

        # self를 제외한 파라미터 확인
        assert "text" in param_names, "text 파라미터가 존재해야 합니다"
        assert "file_path" in param_names, "file_path 파라미터가 존재해야 합니다"
        assert "chat_id" in param_names, "chat_id 파라미터가 존재해야 합니다"
        assert "parse_mode" in param_names, "parse_mode 파라미터가 존재해야 합니다"

    def test_file_path_and_chat_id_are_optional(self):
        """file_path, chat_id, parse_mode는 선택적 파라미터여야 한다"""
        from modules.telegram_sender import TelegramSender

        sig = inspect.signature(TelegramSender.send_message)
        params = sig.parameters

        # file_path, chat_id, parse_mode는 기본값이 있어야 함 (선택적)
        assert params["file_path"].default is not inspect.Parameter.empty, (
            "file_path는 기본값이 있어야 합니다 (선택적 파라미터)"
        )
        assert params["chat_id"].default is not inspect.Parameter.empty, (
            "chat_id는 기본값이 있어야 합니다 (선택적 파라미터)"
        )
        assert params["parse_mode"].default is not inspect.Parameter.empty, (
            "parse_mode는 기본값이 있어야 합니다 (선택적 파라미터)"
        )

    def test_send_message_returns_bool(self):
        """send_message는 bool 값을 반환해야 한다"""
        sender = _create_sender()

        with patch("modules.telegram_sender.requests.post") as mock_post:
            mock_post.return_value = _make_success_response()

            result = sender.send_message(text="반환값 타입 테스트")

            assert isinstance(result, bool), (
                f"send_message의 반환값은 bool이어야 합니다. 실제 타입: {type(result)}"
            )
