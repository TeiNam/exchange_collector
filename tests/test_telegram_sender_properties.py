"""
TelegramSender 속성 기반 테스트 (Property-Based Tests)

Feature: slack-to-telegram-migration
테스트 대상: modules/telegram_sender.py - TelegramSender 클래스
"""

import os
import json
import pytest
from hypothesis import given, settings, assume
from hypothesis import strategies as st
from unittest.mock import patch, MagicMock, PropertyMock
import requests

from configs.telegram_setting import TelegramSettings


# 비어있지 않은 텍스트 전략 (공백만으로 이루어지지 않은 문자열)
non_empty_text = st.text(
    alphabet=st.characters(
        whitelist_categories=('L', 'N', 'P', 'S', 'Z'),
    ),
    min_size=1,
).filter(lambda s: s.strip() != '')

# parse_mode 전략: None 또는 유효한 파싱 모드
parse_mode_strategy = st.sampled_from([None, 'HTML', 'Markdown'])

# 공백 문자열 전략 (빈 문자열 포함)
whitespace_text = st.from_regex(r'^[\s]*$', fullmatch=True)


def _make_success_response():
    """텔레그램 API 성공 응답 Mock 생성"""
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {"ok": True, "result": {"message_id": 1}}
    mock_response.raise_for_status.return_value = None
    return mock_response


@pytest.fixture(autouse=True)
def reset_singleton():
    """각 테스트 전에 싱글톤 인스턴스를 초기화"""
    TelegramSettings._instance = None
    yield
    TelegramSettings._instance = None


def _create_sender():
    """테스트용 TelegramSender 인스턴스 생성 (get_credentials 모킹)"""
    from modules.telegram_sender import TelegramSender

    mock_creds = {
        'bot_token': 'test-bot-token-12345',
        'chat_id': 'test-chat-id-67890',
    }
    with patch('modules.telegram_sender.get_credentials', return_value=mock_creds):
        sender = TelegramSender()
    return sender


class TestValidMessageSendsSuccessfully:
    """
    Property 4: 유효한 메시지 전송 성공 (Valid Message Sends Successfully)

    임의의 비어있지 않은 텍스트 메시지와 선택적 parse_mode 값에 대해,
    텔레그램 API가 성공 응답을 반환하면 send_message()는 True를 반환하고
    올바른 엔드포인트(sendMessage)로 요청이 전송되어야 하며,
    parse_mode가 지정된 경우 요청 본문에 포함되어야 한다.

    Feature: slack-to-telegram-migration, Property 4: 유효한 메시지 전송 성공
    Validates: Requirements 2.1, 2.2, 2.7
    """

    @given(
        text=non_empty_text,
        parse_mode=parse_mode_strategy,
    )
    @settings(max_examples=100)
    def test_valid_message_sends_successfully(self, text, parse_mode):
        """유효한 메시지와 선택적 parse_mode로 전송 시 True 반환 및 올바른 엔드포인트 호출 검증"""
        sender = _create_sender()

        with patch('modules.telegram_sender.requests.post') as mock_post:
            mock_post.return_value = _make_success_response()

            result = sender.send_message(text=text, parse_mode=parse_mode)

            # send_message()는 True를 반환해야 함
            assert result is True, f"유효한 메시지 전송이 실패했습니다: text='{text}', parse_mode={parse_mode}"

            # requests.post가 호출되었는지 확인
            mock_post.assert_called_once()

            # 올바른 엔드포인트(sendMessage)로 호출되었는지 확인
            call_args = mock_post.call_args
            called_url = call_args[0][0] if call_args[0] else call_args[1].get('url', '')
            assert 'sendMessage' in called_url, (
                f"sendMessage 엔드포인트가 아닌 URL로 호출됨: {called_url}"
            )

            # 요청 본문 검증
            called_payload = call_args[1].get('json', {})
            assert called_payload.get('text') == text, "요청 본문에 텍스트가 포함되어야 합니다"

            # parse_mode가 지정된 경우 요청 본문에 포함되어야 함
            if parse_mode is not None:
                assert called_payload.get('parse_mode') == parse_mode, (
                    f"parse_mode가 요청에 포함되어야 합니다: expected={parse_mode}, "
                    f"actual={called_payload.get('parse_mode')}"
                )
            else:
                # parse_mode가 None이면 요청에 포함되지 않아야 함
                assert 'parse_mode' not in called_payload, (
                    "parse_mode가 None일 때 요청에 포함되면 안 됩니다"
                )


class TestEmptyMessageRejection:
    """
    Property 6: 빈 메시지 거부 (Empty Message Rejection)

    임의의 공백 문자로만 이루어진 문자열(빈 문자열 포함)에 대해,
    send_message()는 API를 호출하지 않고 False를 반환해야 한다.

    Feature: slack-to-telegram-migration, Property 6: 빈 메시지 거부
    Validates: Requirements 2.4
    """

    @given(
        text=whitespace_text,
    )
    @settings(max_examples=100)
    def test_empty_message_rejected(self, text):
        """공백 문자열 또는 빈 문자열 전송 시 False 반환 및 API 미호출 검증"""
        sender = _create_sender()

        with patch('modules.telegram_sender.requests.post') as mock_post:
            result = sender.send_message(text=text)

            # send_message()는 False를 반환해야 함
            assert result is False, f"빈 메시지가 거부되지 않았습니다: text='{repr(text)}'"

            # API가 호출되지 않아야 함
            mock_post.assert_not_called(), (
                f"빈 메시지에 대해 API가 호출되었습니다: text='{repr(text)}'"
            )


class TestApiFailureReturnsFalse:
    """
    Property 7: API 실패 시 False 반환 (API Failure Returns False)

    임의의 유효한 메시지에 대해, 텔레그램 API가 에러 응답(HTTP 4xx/5xx)을
    반환하면 send_message()는 False를 반환해야 한다.

    Feature: slack-to-telegram-migration, Property 7: API 실패 시 False 반환
    Validates: Requirements 2.5
    """

    @given(
        text=non_empty_text,
        status_code=st.sampled_from([400, 401, 403, 404, 429, 500, 502, 503]),
    )
    @settings(max_examples=100)
    def test_api_failure_returns_false(self, text, status_code):
        """API 에러 응답 시 False 반환 검증"""
        sender = _create_sender()

        with patch('modules.telegram_sender.requests.post') as mock_post:
            # HTTP 에러 응답 시뮬레이션: raise_for_status()가 예외를 발생시킴
            mock_response = MagicMock()
            mock_response.status_code = status_code
            mock_response.raise_for_status.side_effect = requests.exceptions.HTTPError(
                f"{status_code} Error"
            )
            mock_post.return_value = mock_response

            result = sender.send_message(text=text)

            # send_message()는 False를 반환해야 함
            assert result is False, (
                f"API 에러({status_code})에도 True가 반환되었습니다: text='{text}'"
            )


class TestInvalidFilePathRejection:
    """
    Property 8: 유효하지 않은 파일 경로 거부 (Invalid File Path Rejection)

    임의의 존재하지 않는 파일 경로에 대해,
    send_message()는 False를 반환해야 한다.

    Feature: slack-to-telegram-migration, Property 8: 유효하지 않은 파일 경로 거부
    Validates: Requirements 2.6
    """

    @given(
        text=non_empty_text,
        file_path=st.text(
            alphabet=st.characters(
                whitelist_categories=('L', 'N'),
            ),
            min_size=1,
            max_size=100,
        ).map(lambda s: f"/nonexistent/path/{s}.png"),
    )
    @settings(max_examples=100)
    def test_invalid_file_path_rejected(self, text, file_path):
        """존재하지 않는 파일 경로 전달 시 False 반환 검증"""
        sender = _create_sender()

        with patch('modules.telegram_sender.requests.post') as mock_post:
            result = sender.send_message(text=text, file_path=file_path)

            # send_message()는 False를 반환해야 함
            assert result is False, (
                f"유효하지 않은 파일 경로가 거부되지 않았습니다: file_path='{file_path}'"
            )

            # 파일 경로가 유효하지 않으므로 API가 호출되지 않아야 함
            mock_post.assert_not_called(), (
                f"유효하지 않은 파일 경로에 대해 API가 호출되었습니다: file_path='{file_path}'"
            )
