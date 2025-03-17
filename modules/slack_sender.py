# modules/slack_sender.py
import logging
from pathlib import Path
import os
from typing import Optional, Union, Dict, Any
from configs.slack_setting import get_credentials
from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError

logger = logging.getLogger(__name__)


class SlackSender:
    def __init__(self, channel_id: Optional[str] = None):
        """
        SlackSender 초기화
        :param channel_id: 메시지를 전송할 채널 ID (선택사항)
        """
        credentials = get_credentials()
        self.bot_token = credentials['bot_token']
        self.default_channel_id = channel_id or credentials['channel_id']

        if not self.bot_token:
            raise ValueError("SLACK_BOT_TOKEN이 설정되지 않았습니다.")

        # Slack 클라이언트 초기화
        self.client = WebClient(token=self.bot_token)
        logger.debug(f"SlackSender 초기화 완료 (채널 ID: {self.default_channel_id})")

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
                     channel_id: Optional[str] = None,
                     message_type: str = 'unknown') -> Dict[str, Any]:
        """
        슬랙으로 메시지와 파일을 전송
        :param text: 전송할 메시지 텍스트
        :param file_path: 첨부할 파일 경로 (선택사항)
        :param channel_id: 메시지를 전송할 채널 ID (선택사항)
        :param message_type: 메시지 유형 (exchange_rate, work_journal 등)
        :return: 전송 결과 딕셔너리 {
            'success': bool,  # 성공 여부
            'message_id': str,  # 메시지 ID (성공 시)
            'error': str,  # 오류 메시지 (실패 시)
            'type': str  # 메시지 유형
        }
        """
        result = {
            'success': False,
            'message_id': None,
            'error': None,
            'type': message_type
        }
        
        try:
            if not text:
                logger.error("메시지 내용이 비어있습니다.")
                result['error'] = "메시지 내용이 비어있습니다."
                return result

            use_channel_id = channel_id or self.default_channel_id
            if not use_channel_id:
                logger.error("채널 ID가 지정되지 않았습니다.")
                result['error'] = "채널 ID가 지정되지 않았습니다."
                return result

            # 메시지 전송
            try:
                response = self.client.chat_postMessage(
                    channel=use_channel_id,
                    text=text
                )
                if response and response.get('ok'):
                    message_id = response.get('ts')
                    logger.info(f"메시지 전송 성공 (채널: {use_channel_id}, ID: {message_id})")
                    result['message_id'] = message_id
                else:
                    logger.error(f"메시지 전송 실패: {response.get('error', '알 수 없는 오류')}")
                    result['error'] = f"메시지 전송 실패: {response.get('error', '알 수 없는 오류')}"
                    return result
            except SlackApiError as e:
                logger.error(f"메시지 전송 실패: {str(e)}")
                result['error'] = f"메시지 전송 실패: {str(e)}"
                return result

            # 파일 전송
            if file_path:
                file_path = self._validate_file_path(file_path)
                if not file_path:
                    result['error'] = "파일 경로가 유효하지 않습니다."
                    return result

                try:
                    # files_upload_v2 사용
                    file_response = self.client.files_upload_v2(
                        channel=use_channel_id,
                        file=str(file_path),
                        title=file_path.name,
                        thread_ts=result['message_id']  # 메시지 스레드에 파일 첨부
                    )
                    logger.info(f"파일 전송 성공: {file_path.name}")
                except SlackApiError as e:
                    logger.error(f"파일 전송 실패: {str(e)}")
                    result['error'] = f"파일 전송 실패: {str(e)}"
                    # 메시지는 성공했으므로 부분적으로 성공 처리
                    result['success'] = True
                    return result

            result['success'] = True
            return result

        except Exception as e:
            logger.error(f"메시지 전송 중 예외 발생: {str(e)}", exc_info=True)
            result['error'] = f"메시지 전송 중 예외 발생: {str(e)}"
            return result


# 테스트 코드
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)

    try:
        # 프로젝트 루트 디렉토리 찾기
        current_dir = Path(__file__).resolve().parent
        project_root = current_dir.parent  # 모듈 폴더의 상위 디렉토리가 루트

        # 그래프 파일의 전체 경로 구성
        graph_file = project_root / 'graph_files' / 'exchange_rate_20241227.png'

        sender = SlackSender()
        result = sender.send_message(
            text="환율 데이터 알림 테스트입니다.",
            file_path=graph_file,
            message_type="exchange_rate"
        )
        print(f"전송 결과: {result}")
    except Exception as e:
        print(f"오류 발생: {str(e)}")