"""
TelegramSettings 속성 기반 테스트 (Property-Based Tests)

Feature: slack-to-telegram-migration
테스트 대상: configs/telegram_setting.py - TelegramSettings 클래스
"""

import os
import pytest
from hypothesis import given, settings, assume
from hypothesis import strategies as st
from unittest.mock import patch

from configs.telegram_setting import TelegramSettings


# 유효한 토큰/ID 문자열 전략: 비어있지 않은 출력 가능한 문자열
# 따옴표로 시작/끝나는 문자열은 strip 로직에 의해 변형되므로 제외
non_empty_printable = st.text(
    alphabet=st.characters(
        whitelist_categories=('L', 'N', 'P', 'S'),
        blacklist_characters='"\'',
    ),
    min_size=1,
).filter(lambda s: s.strip() != '')


@pytest.fixture(autouse=True)
def reset_singleton():
    """각 테스트 전에 싱글톤 인스턴스를 초기화"""
    TelegramSettings._instance = None
    yield
    TelegramSettings._instance = None


class TestConfigurationRoundTrip:
    """
    Property 1: 설정 라운드트립 (Configuration Round-Trip)

    임의의 유효한 봇 토큰 문자열과 채팅 ID 문자열에 대해,
    환경변수에 설정한 후 get_credentials()를 호출하면
    동일한 bot_token과 chat_id 값이 포함된 딕셔너리가 반환되어야 한다.

    Feature: slack-to-telegram-migration, Property 1: 설정 라운드트립
    Validates: Requirements 1.1, 1.5
    """

    @given(
        bot_token=non_empty_printable,
        chat_id=non_empty_printable,
    )
    @settings(max_examples=100)
    def test_credentials_round_trip(self, bot_token, chat_id):
        """환경변수에 설정한 값이 get_credentials()로 동일하게 반환되는지 검증"""
        # 싱글톤 초기화
        TelegramSettings._instance = None

        env_vars = {
            'TELEGRAM_BOT_TOKEN': bot_token,
            'TELEGRAM_CHAT_ID': chat_id,
            'TELEGRAM_SEND_GRAPH': 'false',
        }

        with patch.dict(os.environ, env_vars, clear=False):
            instance = TelegramSettings()
            credentials = instance.get_credentials()

            # 라운드트립 검증: 설정한 값과 반환된 값이 동일해야 함
            assert credentials['bot_token'] == bot_token
            assert credentials['chat_id'] == chat_id


class TestSingletonGuarantee:
    """
    Property 2: 싱글톤 보장 (Singleton Guarantee)

    임의의 횟수만큼 TelegramSettings()를 생성해도,
    모든 인스턴스는 동일한 객체(id가 같음)여야 한다.

    Feature: slack-to-telegram-migration, Property 2: 싱글톤 보장
    Validates: Requirements 1.4
    """

    @given(
        num_instances=st.integers(min_value=2, max_value=10),
    )
    @settings(max_examples=100)
    def test_singleton_identity(self, num_instances):
        """N번 생성해도 모든 인스턴스가 동일한 객체인지 검증"""
        # 싱글톤 초기화
        TelegramSettings._instance = None

        env_vars = {
            'TELEGRAM_BOT_TOKEN': 'test-token-singleton',
            'TELEGRAM_CHAT_ID': 'test-chat-id-singleton',
            'TELEGRAM_SEND_GRAPH': 'false',
        }

        with patch.dict(os.environ, env_vars, clear=False):
            instances = [TelegramSettings() for _ in range(num_instances)]

            # 모든 인스턴스의 id가 첫 번째 인스턴스와 동일해야 함
            first_id = id(instances[0])
            for i, inst in enumerate(instances):
                assert id(inst) == first_id, (
                    f"인스턴스 {i}의 id({id(inst)})가 "
                    f"첫 번째 인스턴스의 id({first_id})와 다릅니다"
                )


class TestGraphSendSettingParsing:
    """
    Property 3: 그래프 전송 설정 파싱 (Graph Send Setting Parsing)

    임의의 문자열 값에 대해, TELEGRAM_SEND_GRAPH 환경변수가
    대소문자 무관하게 "true"일 때만 send_graph 속성이 True를 반환하고,
    그 외 모든 값(빈 문자열, 미설정 포함)에서는 False를 반환해야 한다.

    Feature: slack-to-telegram-migration, Property 3: 그래프 전송 설정 파싱
    Validates: Requirements 1.6, 1.7
    """

    @given(
        # 환경변수에 null 바이트(\x00)는 설정 불가하므로 제외
        send_graph_value=st.text(
            alphabet=st.characters(blacklist_characters='\x00'),
            min_size=0,
            max_size=50,
        ),
    )
    @settings(max_examples=100)
    def test_send_graph_parsing(self, send_graph_value):
        """임의의 문자열에 대해 send_graph가 올바르게 파싱되는지 검증"""
        # 싱글톤 초기화
        TelegramSettings._instance = None

        env_vars = {
            'TELEGRAM_BOT_TOKEN': 'test-token-graph',
            'TELEGRAM_CHAT_ID': 'test-chat-id-graph',
            'TELEGRAM_SEND_GRAPH': send_graph_value,
        }

        with patch.dict(os.environ, env_vars, clear=False):
            instance = TelegramSettings()

            # "true" (대소문자 무관)일 때만 True, 그 외 모든 값은 False
            expected = send_graph_value.strip().lower() == 'true'
            assert instance.send_graph == expected, (
                f"TELEGRAM_SEND_GRAPH='{send_graph_value}' → "
                f"expected={expected}, actual={instance.send_graph}"
            )
