import logging
from datetime import datetime, timedelta
import pandas as pd
import matplotlib.pyplot as plt
from pathlib import Path
from modules.mysql_connector import MySQLConnector
from modules.slack_sender import SlackSender
from configs.slack_setting import get_credentials

# 로깅 설정
logger = logging.getLogger(__name__)


class CommentAnalyzer:
    """Slack 댓글 분석 클래스"""
    
    def __init__(self, db_connector: MySQLConnector = None):
        """
        CommentAnalyzer 초기화
        
        Args:
            db_connector: MySQL 연결을 위한 커넥터 인스턴스
        """
        self.db_connector = db_connector or MySQLConnector()
        
    def get_comment_stats(self, days: int = 7) -> pd.DataFrame:
        """
        지정된 기간 동안의 댓글 통계 조회
        
        Args:
            days: 조회할 일수 (기본값: 7일)
            
        Returns:
            댓글 통계를 담은 DataFrame
        """
        try:
            # 시작 날짜 계산
            start_date = (datetime.now() - timedelta(days=days)).strftime('%Y-%m-%d')
            
            # SQL 쿼리 작성 - 업무일지 메시지만 조회
            query = """
            SELECT 
                DATE(comment_timestamp) AS comment_date,
                message_type,
                COUNT(*) AS comment_count,
                COUNT(DISTINCT user_id) AS user_count
            FROM 
                slack_comments
            WHERE 
                comment_timestamp >= %s
                AND message_type = 'work_journal'
            GROUP BY 
                DATE(comment_timestamp), message_type
            ORDER BY 
                comment_date DESC, message_type
            """
            
            # 쿼리 실행
            connection = self.db_connector.get_connection()
            df = pd.read_sql(query, connection, params=[start_date])
            
            # 결과가 비어있으면 빈 데이터프레임 반환
            if df.empty:
                return pd.DataFrame(columns=['comment_date', 'message_type', 'comment_count', 'user_count'])
                
            # 데이터 변환
            df['comment_date'] = pd.to_datetime(df['comment_date']).dt.date
            
            return df
            
        except Exception as e:
            logger.error(f"댓글 통계 조회 중 오류 발생: {str(e)}", exc_info=True)
            return pd.DataFrame(columns=['comment_date', 'message_type', 'comment_count', 'user_count'])
            
    def get_active_users(self, days: int = 7, limit: int = 5) -> pd.DataFrame:
        """
        가장 활발한 사용자 목록 조회
        
        Args:
            days: 조회할 일수 (기본값: 7일)
            limit: 반환할 사용자 수 (기본값: 5명)
            
        Returns:
            활발한 사용자 통계를 담은 DataFrame
        """
        try:
            # 시작 날짜 계산
            start_date = (datetime.now() - timedelta(days=days)).strftime('%Y-%m-%d')
            
            # SQL 쿼리 작성 - 업무일지 메시지만 조회
            query = """
            SELECT 
                user_id,
                user_name,
                COUNT(*) AS comment_count
            FROM 
                slack_comments
            WHERE 
                comment_timestamp >= %s
                AND message_type = 'work_journal'
            GROUP BY 
                user_id, user_name
            ORDER BY 
                comment_count DESC
            LIMIT %s
            """
            
            # 쿼리 실행
            connection = self.db_connector.get_connection()
            df = pd.read_sql(query, connection, params=[start_date, limit])
            
            return df
            
        except Exception as e:
            logger.error(f"활발한 사용자 조회 중 오류 발생: {str(e)}", exc_info=True)
            return pd.DataFrame(columns=['user_id', 'user_name', 'comment_count'])
    
    def create_comment_graph(self, stats_df: pd.DataFrame, output_path: str = None) -> str:
        """
        댓글 통계 그래프 생성
        
        Args:
            stats_df: 댓글 통계 DataFrame
            output_path: 그래프 저장 경로 (선택사항)
            
        Returns:
            생성된 그래프 파일 경로
        """
        try:
            # 경로 설정
            if not output_path:
                # 프로젝트 루트 디렉토리 찾기
                current_dir = Path(__file__).resolve().parent
                project_root = current_dir.parent  # utils 폴더의 상위 디렉토리가 루트
                
                # 그래프 파일 저장 경로
                graph_dir = project_root / 'graph_files'
                graph_dir.mkdir(exist_ok=True)
                
                today = datetime.now().strftime('%Y%m%d')
                output_path = graph_dir / f'work_journal_comments_{today}.png'
            else:
                output_path = Path(output_path)
                output_path.parent.mkdir(exist_ok=True)
            
            # 데이터가 없으면 기본 그래프 생성
            if stats_df.empty:
                plt.figure(figsize=(10, 6))
                plt.title('업무일지 댓글 통계 (데이터 없음)')
                plt.text(0.5, 0.5, '해당 기간에 수집된 업무일지 댓글이 없습니다', 
                         horizontalalignment='center', verticalalignment='center',
                         transform=plt.gca().transAxes)
                plt.tight_layout()
                plt.savefig(output_path)
                plt.close()
                return str(output_path)
            
            # 날짜별 댓글 수 그래프 생성
            plt.figure(figsize=(12, 6))
            
            # 막대 그래프 생성
            ax = plt.subplot(111)
            stats_df.plot(x='comment_date', y='comment_count', kind='bar', ax=ax, color='skyblue')
            
            # 제목 및 레이블 설정
            plt.title('일별 업무일지 댓글 통계', fontsize=16)
            plt.xlabel('날짜', fontsize=12)
            plt.ylabel('댓글 수', fontsize=12)
            plt.grid(axis='y', linestyle='--', alpha=0.7)
            
            # 데이터 레이블 추가
            for p in ax.patches:
                height = p.get_height()
                if height > 0:
                    ax.annotate(f'{int(height)}', 
                               (p.get_x() + p.get_width() / 2., height), 
                               ha='center', va='bottom')
            
            plt.tight_layout()
            plt.savefig(output_path, dpi=100)
            plt.close()
            
            logger.info(f"업무일지 댓글 통계 그래프 생성 완료: {output_path}")
            return str(output_path)
            
        except Exception as e:
            logger.error(f"그래프 생성 중 오류 발생: {str(e)}", exc_info=True)
            return None
    
    def create_weekly_report(self) -> dict:
        """
        주간 업무일지 댓글 보고서 생성
        
        Returns:
            보고서 결과 {
                'stats': DataFrame,
                'active_users': DataFrame,
                'graph_path': str
            }
        """
        try:
            # 통계 데이터 가져오기
            stats_df = self.get_comment_stats(days=7)
            active_users_df = self.get_active_users(days=7, limit=5)
            
            # 그래프 생성
            graph_path = self.create_comment_graph(stats_df)
            
            # 결과 반환
            return {
                'stats': stats_df,
                'active_users': active_users_df,
                'graph_path': graph_path
            }
            
        except Exception as e:
            logger.error(f"주간 보고서 생성 중 오류 발생: {str(e)}", exc_info=True)
            return {
                'stats': pd.DataFrame(),
                'active_users': pd.DataFrame(),
                'graph_path': None
            }
    
    def generate_report_message(self, report_data: dict) -> str:
        """
        보고서 메시지 생성
        
        Args:
            report_data: 보고서 데이터
            
        Returns:
            포맷팅된 메시지 문자열
        """
        stats_df = report_data['stats']
        active_users_df = report_data['active_users']
        
        today = datetime.now().strftime('%Y-%m-%d')
        week_ago = (datetime.now() - timedelta(days=7)).strftime('%Y-%m-%d')
        
        message_lines = [
            f"📊 주간 업무일지 댓글 리포트 ({week_ago} ~ {today})",
            ""
        ]
        
        # 댓글 통계 요약
        if not stats_df.empty:
            total_comments = stats_df['comment_count'].sum()
            total_users = stats_df['user_count'].sum()
            
            message_lines.extend([
                f"전체 댓글 수: {total_comments}개",
                f"참여 사용자 수: {total_users}명",
                ""
            ])
        else:
            message_lines.extend([
                "이번 주에 수집된 업무일지 댓글이 없습니다.",
                ""
            ])
        
        # 활발한 사용자
        if not active_users_df.empty:
            message_lines.append("가장 활발한 사용자:")
            for _, row in active_users_df.iterrows():
                message_lines.append(f"• {row['user_name']}: {row['comment_count']}개 댓글")
            message_lines.append("")
        
        message_lines.append("자세한 통계는 첨부된 그래프를 참고하세요.")
        
        return "\n".join(message_lines)
    
    def send_weekly_report(self) -> bool:
        """
        주간 업무일지 댓글 보고서 생성 및 전송
        
        Returns:
            전송 성공 여부
        """
        try:
            # 보고서 데이터 생성
            report_data = self.create_weekly_report()
            
            # 메시지 생성
            message = self.generate_report_message(report_data)
            
            # Slack 전송
            credentials = get_credentials()
            slack = SlackSender(channel_id=credentials['channel_id'])
            
            result = slack.send_message(
                text=message,
                file_path=report_data['graph_path'],
                message_type="work_journal_report"
            )
            
            if result['success']:
                logger.info("주간 업무일지 댓글 보고서가 성공적으로 전송되었습니다.")
                return True
            else:
                logger.error(f"보고서 전송 실패: {result['error']}")
                return False
                
        except Exception as e:
            logger.error(f"보고서 전송 중 오류 발생: {str(e)}", exc_info=True)
            return False


# 모듈 테스트 코드
def main():
    """주간 업무일지 댓글 보고서 생성 및 전송"""
    try:
        # DB 커넥터 초기화
        db_connector = MySQLConnector()
        
        # 댓글 분석기 초기화
        analyzer = CommentAnalyzer(db_connector)
        
        # 주간 보고서 전송
        success = analyzer.send_weekly_report()
        
        if success:
            logger.info("주간 업무일지 댓글 보고서 전송 완료")
        else:
            logger.error("주간 업무일지 댓글 보고서 전송 실패")
        
    except Exception as e:
        logger.error(f"댓글 분석 중 오류 발생: {str(e)}", exc_info=True)
    finally:
        if 'db_connector' in locals():
            db_connector.close()


if __name__ == "__main__":
    # 테스트 실행을 위한 로깅 설정
    logging.basicConfig(level=logging.INFO)
    main()