import logging
from datetime import datetime, timedelta
import time
from typing import Optional, List, Dict, Any
from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError
from modules.mysql_connector import MySQLConnector
from configs.slack_setting import get_credentials

# 로깅 설정
logger = logging.getLogger(__name__)


class SlackCommentCollector:
    """Slack 댓글(스레드 메시지) 수집 및 저장 클래스"""

    def __init__(self, db_connector: MySQLConnector = None):
        """
        SlackCommentCollector 초기화

        Args:
            db_connector: MySQL 연결을 위한 커넥터 인스턴스
        """
        # Slack API 설정
        credentials = get_credentials()
        self.bot_token = credentials['bot_token']
        self.channel_id = credentials['channel_id']

        if not self.bot_token:
            raise ValueError("SLACK_BOT_TOKEN이 설정되지 않았습니다.")

        # Slack 클라이언트 초기화
        self.client = WebClient(token=self.bot_token)

        # DB 커넥터 설정
        self.db_connector = db_connector or MySQLConnector()

        logger.debug("SlackCommentCollector 초기화 완료")

    def _get_user_info(self, user_id: str) -> Dict[str, Any]:
        """
        사용자 정보 조회

        Args:
            user_id: 조회할 사용자의 ID

        Returns:
            사용자 정보 딕셔너리
        """
        try:
            response = self.client.users_info(user=user_id)
            if response and response.get('ok'):
                user = response.get('user', {})
                profile = user.get('profile', {})

                # 디스플레이 네임을 우선적으로 사용
                display_name = profile.get('display_name')
                if not display_name or display_name.strip() == '':
                    # 디스플레이 네임이 비어있으면 real_name 사용
                    display_name = profile.get('real_name') or user.get('real_name')

                # 그래도 없으면, 기본 name 사용
                if not display_name or display_name.strip() == '':
                    display_name = user.get('name', '알 수 없음')

                return {
                    'id': user_id,
                    'name': display_name,
                    'profile': profile
                }
            return {'id': user_id, 'name': '알 수 없음', 'profile': {}}
        except SlackApiError as e:
            logger.error(f"사용자 정보 조회 실패: {str(e)}")
            return {'id': user_id, 'name': '알 수 없음', 'profile': {}}

    def _check_existing_comment(self, comment_message_id: str) -> Optional[Dict[str, Any]]:
        """
        기존 댓글 정보 조회

        Args:
            comment_message_id: 댓글 메시지 ID

        Returns:
            존재하는 경우 댓글 정보 딕셔너리, 없으면 None
        """
        try:
            query = """
            SELECT id, content, edit_count
            FROM slack_comments
            WHERE comment_message_id = %s
            """

            connection = self.db_connector.get_connection()
            with connection.cursor() as cursor:
                cursor.execute(query, (comment_message_id,))
                result = cursor.fetchone()

                if result:
                    return {
                        'id': result[0],
                        'content': result[1],
                        'edit_count': result[2]
                    }
                return None

        except Exception as e:
            logger.error(f"기존 댓글 확인 중 오류 발생: {str(e)}", exc_info=True)
            return None

    def _save_comment_to_db(self,
                            parent_message_id: str,
                            comment_message_id: str,
                            user_id: str,
                            user_name: str,
                            content: str,
                            timestamp: datetime,
                            message_type: str = 'unknown') -> bool:
        """
        댓글을 데이터베이스에 저장

        Args:
            parent_message_id: 원본 메시지 ID
            comment_message_id: 댓글 메시지 ID
            user_id: 사용자 ID
            user_name: 사용자 이름
            content: 댓글 내용
            timestamp: 댓글 작성 시간
            message_type: 메시지 유형 (exchange_rate, work_journal 등)

        Returns:
            저장 성공 여부
        """
        # 환율 관련 댓글은 저장하지 않음
        if message_type == 'exchange_rate':
            logger.debug(f"환율 관련 댓글은 저장하지 않습니다: {comment_message_id}")
            return True

        try:
            # 기존 댓글 확인
            existing_comment = self._check_existing_comment(comment_message_id)
            connection = self.db_connector.get_connection()

            # 기존 댓글이 있는 경우
            if existing_comment:
                # 내용이 변경된 경우에만 업데이트
                if existing_comment['content'] != content:
                    # 수정 횟수 증가
                    edit_count = existing_comment['edit_count'] + 1

                    update_query = """
                    UPDATE slack_comments
                    SET content = %s, 
                        user_name = %s,
                        previous_content = %s,
                        is_edited = TRUE,
                        edit_count = %s
                    WHERE id = %s
                    """

                    with connection.cursor() as cursor:
                        cursor.execute(update_query, (
                            content,
                            user_name,
                            existing_comment['content'],  # 이전 내용 저장
                            edit_count,
                            existing_comment['id']
                        ))
                        connection.commit()

                    logger.info(f"댓글 내용 업데이트 완료 (메시지 ID: {comment_message_id}, 수정 횟수: {edit_count})")
                else:
                    logger.debug(f"댓글 내용이 변경되지 않았습니다: {comment_message_id}")

                return True

            # 새 댓글 저장
            insert_query = """
            INSERT INTO slack_comments (
                parent_message_id, comment_message_id, user_id, user_name, 
                content, comment_timestamp, message_type,
                is_edited, edit_count
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
            """

            with connection.cursor() as cursor:
                cursor.execute(insert_query, (
                    parent_message_id,
                    comment_message_id,
                    user_id,
                    user_name,
                    content,
                    timestamp,
                    message_type,
                    False,  # is_edited
                    0  # edit_count
                ))
                connection.commit()

            logger.info(f"새 댓글 저장 완료 (메시지 ID: {comment_message_id}, 유형: {message_type})")
            return True

        except Exception as e:
            logger.error(f"댓글 저장 중 오류 발생: {str(e)}", exc_info=True)
            return False

    def collect_thread_replies(self,
                               message_id: str,
                               parent_ts: str,
                               message_type: str = 'unknown',
                               days_back: int = 7) -> List[Dict[str, Any]]:
        """
        특정 메시지의 스레드 답글(댓글)을 수집하고 저장

        Args:
            message_id: 메시지 ID (ts 형식)
            parent_ts: 부모 메시지의 타임스탬프
            message_type: 메시지 유형 (exchange_rate, work_journal 등)
            days_back: 몇 일 전까지의 댓글을 수집할지 (기본 7일)

        Returns:
            수집된 댓글 목록
        """
        comments = []

        # 환율 관련 댓글은 수집하지 않음
        if message_type == 'exchange_rate':
            logger.debug(f"환율 관련 메시지({message_id})의 댓글은 수집하지 않습니다.")
            return comments

        try:
            # 스레드 답글 조회
            response = self.client.conversations_replies(
                channel=self.channel_id,
                ts=parent_ts
            )

            if not response.get('ok'):
                logger.error(f"스레드 답글 조회 실패: {response.get('error', '알 수 없는 오류')}")
                return comments

            messages = response.get('messages', [])

            # 첫 번째 메시지는 부모 메시지이므로 제외
            replies = messages[1:] if len(messages) > 1 else []

            if not replies:
                logger.info(f"메시지 {parent_ts}에 댓글이 없습니다.")
                return comments

            # 최소 날짜 설정 (days_back일 전)
            min_date = datetime.now() - timedelta(days=days_back)

            for reply in replies:
                # 타임스탬프를 datetime으로 변환
                ts = reply.get('ts')
                reply_datetime = datetime.fromtimestamp(float(ts))

                # 지정된 일수보다 오래된 댓글은 건너뛰기
                if reply_datetime < min_date:
                    continue

                user_id = reply.get('user')
                text = reply.get('text', '')

                # 수정 여부 확인 (Slack API에서 제공하는 경우)
                is_edited = 'edited' in reply

                # 사용자 정보 가져오기
                user_info = self._get_user_info(user_id)
                user_name = user_info.get('name')

                # 댓글 정보 구성
                comment = {
                    'parent_message_id': message_id,
                    'comment_message_id': ts,
                    'user_id': user_id,
                    'user_name': user_name,
                    'content': text,
                    'timestamp': reply_datetime,
                    'is_edited': is_edited
                }

                comments.append(comment)

                # 데이터베이스 저장 또는 업데이트
                self._save_comment_to_db(
                    parent_message_id=message_id,
                    comment_message_id=ts,
                    user_id=user_id,
                    user_name=user_name,
                    content=text,
                    timestamp=reply_datetime,
                    message_type=message_type
                )

            logger.info(f"메시지 {parent_ts}에서 {len(comments)}개의 댓글을 수집했습니다.")

        except SlackApiError as e:
            logger.error(f"Slack API 오류: {str(e)}")
        except Exception as e:
            logger.error(f"댓글 수집 중 오류 발생: {str(e)}", exc_info=True)

        return comments

    def collect_recent_message_comments(self, days_back: int = 1) -> Dict[str, List[Dict[str, Any]]]:
        """
        오늘 날짜의 업무일지 작성 알림 메시지에 달린 댓글만 수집

        Args:
            days_back: 몇 일 전까지의 댓글을 수집할지 (기본 1일)

        Returns:
            메시지별 댓글 목록 딕셔너리
        """
        all_comments = {}

        try:
            # 오늘 날짜 계산
            today = datetime.now().date()
            today_start = datetime.combine(today, datetime.min.time())
            today_end = datetime.combine(today, datetime.max.time())

            # 오늘 날짜 문자열 (YYYY-MM-DD 형식)
            today_str = today.strftime('%Y-%m-%d')

            # Unix 타임스탬프로 변환
            oldest_time = today_start.timestamp()
            latest_time = today_end.timestamp()

            logger.info(f"오늘({today_str}) 업무일지 작성 알림 메시지 및 댓글 수집 시작")

            # 오늘 날짜의 채널 메시지 조회
            response = self.client.conversations_history(
                channel=self.channel_id,
                oldest=str(oldest_time),
                latest=str(latest_time)
            )

            if not response.get('ok'):
                logger.error(f"채널 메시지 조회 실패: {response.get('error', '알 수 없는 오류')}")
                return all_comments

            messages = response.get('messages', [])
            logger.info(f"오늘 전송된 메시지 {len(messages)}개 확인")

            # 업무일지 작성 알림 메시지 찾기
            workjournal_messages = []
            for message in messages:
                # 봇 메시지이고 스레드 답글이 있는 경우만 체크
                if message.get('bot_id') and message.get('reply_count', 0) > 0:
                    message_text = message.get('text', '')

                    # 날짜와 "업무일지 작성 알림" 텍스트가 모두 포함되어 있는지 확인
                    # 이모티콘이나 다른 텍스트가 있어도 무시하고 이 두 문자열만 확인
                    if today_str in message_text and "업무일지 작성 알림" in message_text:
                        workjournal_messages.append({
                            'id': message.get('ts'),
                            'text': message_text
                        })

            logger.info(f"오늘의 업무일지 작성 알림 메시지 {len(workjournal_messages)}개 확인")

            # 각 업무일지 메시지의 스레드 답글 수집
            for message in workjournal_messages:
                message_id = message['id']

                # 스레드 답글 수집
                comments = self.collect_thread_replies(
                    message_id=message_id,
                    parent_ts=message_id,
                    message_type='work_journal',
                    days_back=days_back
                )

                if comments:
                    all_comments[message_id] = comments

            logger.info(f"오늘의 업무일지 작성 알림 메시지 {len(all_comments)}개에서 댓글을 수집했습니다.")

        except SlackApiError as e:
            logger.error(f"Slack API 오류: {str(e)}")
        except Exception as e:
            logger.error(f"댓글 수집 중 오류 발생: {str(e)}", exc_info=True)

        return all_comments

    def get_comment_edit_history(self, comment_message_id: str) -> Optional[Dict[str, Any]]:
        """
        댓글의 수정 이력 조회

        Args:
            comment_message_id: 댓글 메시지 ID

        Returns:
            수정 이력 정보 딕셔너리
        """
        try:
            query = """
            SELECT 
                comment_message_id, 
                content, 
                previous_content, 
                edit_count, 
                updated_at
            FROM 
                slack_comments
            WHERE 
                comment_message_id = %s
            """

            connection = self.db_connector.get_connection()
            with connection.cursor() as cursor:
                cursor.execute(query, (comment_message_id,))
                result = cursor.fetchone()

                if result:
                    return {
                        'comment_message_id': result[0],
                        'current_content': result[1],
                        'previous_content': result[2],
                        'edit_count': result[3],
                        'last_updated': result[4]
                    }

                return None

        except Exception as e:
            logger.error(f"댓글 수정 이력 조회 중 오류 발생: {str(e)}", exc_info=True)
            return None

    def get_user_comments_by_date(self, target_date: datetime) -> Dict[str, List[Dict[str, Any]]]:
        """
        특정 날짜의 사용자별 댓글 조회

        Args:
            target_date: 조회할 날짜

        Returns:
            사용자별 댓글 목록 딕셔너리
        """
        user_comments = {}

        try:
            # 날짜 형식 변환
            date_str = target_date.strftime('%Y-%m-%d')

            # 해당 날짜의 업무일지 댓글만 조회
            query = """
            SELECT 
                user_id, 
                user_name, 
                content, 
                comment_timestamp
            FROM 
                slack_comments
            WHERE 
                DATE(comment_timestamp) = %s
                AND message_type = 'work_journal'
            ORDER BY 
                user_name, comment_timestamp
            """

            connection = self.db_connector.get_connection()
            with connection.cursor() as cursor:
                cursor.execute(query, (date_str,))
                results = cursor.fetchall()

                for result in results:
                    user_id = result[0]
                    user_name = result[1]
                    content = result[2]
                    timestamp = result[3]

                    # 사용자 ID를 키로 사용
                    if user_id not in user_comments:
                        user_comments[user_id] = []

                    user_comments[user_id].append({
                        'user_name': user_name,
                        'content': content,
                        'timestamp': timestamp
                    })

            logger.info(f"{date_str}의 댓글 조회 완료: {len(user_comments)}명의 사용자가 댓글을 작성했습니다.")
            return user_comments

        except Exception as e:
            logger.error(f"날짜별 댓글 조회 중 오류 발생: {str(e)}", exc_info=True)
            return {}

    def format_previous_workday_comments(self, comments_by_user: Dict[str, List[Dict[str, Any]]],
                                         previous_workday: datetime) -> str:
        """
        이전 근무일의 사용자별 댓글을 포맷팅

        Args:
            comments_by_user: 사용자별 댓글 딕셔너리
            previous_workday: 이전 근무일 날짜

        Returns:
            포맷팅된 문자열
        """
        if not comments_by_user:
            return "이전 근무일에 기록된 댓글이 없습니다."

        date_str = previous_workday.strftime('%Y-%m-%d')
        lines = [f"\n📋 {date_str} 업무 기록 요약"]

        for user_id, comments in comments_by_user.items():
            if not comments:
                continue

            user_name = comments[0]['user_name']
            lines.append(f"\n👤 {user_name}")

            for i, comment in enumerate(comments, 1):
                content = comment['content']
                # 긴 내용은 요약
                if len(content) > 100:
                    content = content[:97] + "..."
                lines.append(f"  {i}. {content}")

        return "\n".join(lines)


# 테스트 코드
if __name__ == "__main__":
    # 테스트를 위한 로깅 설정
    logging.basicConfig(level=logging.INFO)

    # 댓글 수집기 초기화
    collector = SlackCommentCollector()

    # 이전 날짜 지정
    previous_date = datetime.now() - timedelta(days=1)

    # 이전 날짜의 사용자별 댓글 조회
    user_comments = collector.get_user_comments_by_date(previous_date)

    # 결과 출력
    formatted_summary = collector.format_previous_workday_comments(user_comments, previous_date)
    print(formatted_summary)