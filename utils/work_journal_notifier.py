import logging
from datetime import datetime
from modules.slack_sender import SlackSender
from utils.holiday_checker import HolidayChecker
from utils.slack_comment_collector import SlackCommentCollector
from modules.mysql_connector import MySQLConnector
from configs.slack_setting import get_credentials

# 로깅 설정
logger = logging.getLogger(__name__)


def create_work_journal_message(include_previous_workday=True):
    """
    업무일지 작성 알림 메시지 생성
    
    Args:
        include_previous_workday: 이전 근무일 댓글 포함 여부
        
    Returns:
        포맷팅된 메시지 문자열
    """
    today = datetime.now().strftime('%Y-%m-%d')
    
    message_lines = [
        f"📝 {today} 업무일지 작성 알림",
        "",
        "안녕하세요! 오늘의 업무일지를 작성할 시간입니다.",
        "",
        "✅ 오늘의 주요 업무와 진행 상황을 기록해 주세요.",
        ""
    ]
    
    # 이전 근무일 댓글 추가
    if include_previous_workday:
        try:
            # 이전 근무일 찾기
            holiday_checker = HolidayChecker()
            previous_workday = holiday_checker.find_previous_workday()
            
            # DB 연결
            db_connector = MySQLConnector()
            
            # 댓글 수집기 초기화
            collector = SlackCommentCollector(db_connector)
            
            # 이전 근무일의 사용자별 업무일지 댓글 조회
            user_comments = collector.get_user_comments_by_date(previous_workday)
            
            # 댓글 내용 포맷팅
            if user_comments:
                previous_comments = collector.format_previous_workday_comments(
                    user_comments, previous_workday
                )
                message_lines.append(previous_comments)
                message_lines.append("")
            
            # 리소스 정리
            db_connector.close()
            
        except Exception as e:
            logger.error(f"이전 근무일 댓글 조회 중 오류 발생: {str(e)}", exc_info=True)
    
    message_lines.extend([
        "",
        "좋은 하루 되세요! 🌞"
    ])
    
    return "\n".join(message_lines)


def main():
    """업무일지 작성 알림 전송"""
    try:
        # Slack 설정 가져오기
        credentials = get_credentials()
        slack = SlackSender(channel_id=credentials['channel_id'])
        logger.debug("Slack Sender 초기화 완료")
        
        # 메시지 생성 (이전 근무일 댓글 포함)
        message = create_work_journal_message(include_previous_workday=True)
        
        # 메시지 전송
        result = slack.send_message(
            text=message,
            message_type="work_journal"
        )
        
        if not result['success']:
            logger.error(f"Slack 메시지 전송 실패: {result['error']}")
        else:
            logger.info(f"업무일지 작성 알림이 성공적으로 전송되었습니다. (메시지 ID: {result['message_id']})")
            
    except Exception as e:
        logger.error(f"업무일지 알림 전송 중 오류 발생: {str(e)}", exc_info=True)


if __name__ == "__main__":
    # 테스트 실행을 위한 로깅 설정
    logging.basicConfig(level=logging.INFO)
    main()