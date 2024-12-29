# utils/exchange_rate_visualizer.py

from pathlib import Path
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import pandas as pd
from datetime import datetime, timedelta
import logging
from modules.mysql_connector import MySQLConnector
from modules.cleanup import FileCleaner


logger = logging.getLogger(__name__)


class ExchangeRateVisualizer:
    def __init__(self, db_connector):
        self.db_connector = db_connector
        self.root_dir = Path(__file__).resolve().parent.parent
        self.graph_dir = self.root_dir / 'graph_files'

        # graph_files 디렉토리가 없으면 생성
        if not self.graph_dir.exists():
            self.graph_dir.mkdir(parents=True)
            logger.info(f"그래프 저장 디렉토리 생성: {self.graph_dir}")

    # utils/exchange_rate_visualizer.py

    def fetch_data_range(self, start_date, end_date):
        """기간 범위의 환율 데이터 조회"""
        query = """
        SELECT cur_unit, bkpr, search_date 
        FROM exchange_rates 
        WHERE search_date >= %s AND search_date <= %s
        AND cur_unit IN ('USD', 'JPY(100)')
        ORDER BY search_date, cur_unit
        """

        try:
            connection = self.db_connector.get_connection()
            with connection.cursor() as cursor:
                cursor.execute(query, (start_date, end_date))
                rows = cursor.fetchall()

                # DataFrame 생성
                df = pd.DataFrame(rows, columns=['cur_unit', 'bkpr', 'search_date'])
                # search_date를 datetime 타입으로 변환
                df['search_date'] = pd.to_datetime(df['search_date'])
                return df

        except Exception as e:
            logger.error(f"데이터 조회 중 오류 발생: {str(e)}")
            raise

    def create_visualization(self, months=3):
        """환율 변동 그래프 생성"""
        try:
            # 날짜 범위 계산
            end_date = datetime.now().date()
            start_date = end_date - timedelta(days=months * 31)

            # 데이터 조회
            df = self.fetch_data_range(start_date, end_date)
            if df.empty:
                logger.warning(f"해당 기간의 데이터가 없습니다.")
                return False

            # 데이터가 있는 실제 날짜 범위 확인
            actual_start_date = df['search_date'].min()
            actual_end_date = df['search_date'].max()

            # 데이터가 있는 날짜 범위에 대해서만 date_range 생성
            date_range = pd.date_range(start=actual_start_date, end=actual_end_date, freq='D')

            # USD와 JPY 데이터 분리
            usd_data = df[df['cur_unit'] == 'USD']
            jpy_data = df[df['cur_unit'] == 'JPY(100)']

            # 그래프 생성
            fig, ax1 = plt.subplots(figsize=(15, 8), facecolor='white')
            ax1.set_facecolor('#f8f9fa')

            # USD 그래프 (왼쪽 y축)
            color1 = '#1f77b4'  # 파란색
            ax1.set_xlabel('Date', fontsize=10)
            ax1.set_ylabel('USD/KRW', color=color1, fontsize=10)
            line1 = ax1.plot(usd_data['search_date'], usd_data['bkpr'],
                             color=color1, label='USD/KRW', linewidth=2, marker='o', markersize=4)
            ax1.tick_params(axis='y', labelcolor=color1)

            # Y축 범위 설정
            y1_min, y1_max = ax1.get_ylim()
            y1_margin = (y1_max - y1_min) * 0.1
            ax1.set_ylim(y1_min - y1_margin, y1_max + y1_margin)

            # USD 최고/최저 표시 (자동 위치 조정)
            usd_max_idx = usd_data['bkpr'].idxmax()
            usd_min_idx = usd_data['bkpr'].idxmin()
            usd_max = usd_data.loc[usd_max_idx]
            usd_min = usd_data.loc[usd_min_idx]

            bbox_props = dict(boxstyle='round,pad=0.5', facecolor='white', edgecolor=color1, alpha=0.7)

            # 최대값 주석 위치 조정
            ax1.annotate(f'Max: {usd_max["bkpr"]}',
                         xy=(usd_max['search_date'], usd_max['bkpr']),
                         xytext=(0, -20), textcoords='offset points',
                         color=color1, fontweight='bold',
                         bbox=bbox_props,
                         ha='center', va='bottom')

            # 최소값 주석 위치 조정
            ax1.annotate(f'Min: {usd_min["bkpr"]}',
                         xy=(usd_min['search_date'], usd_min['bkpr']),
                         xytext=(0, 20), textcoords='offset points',
                         color=color1, fontweight='bold',
                         bbox=bbox_props,
                         ha='center', va='top')

            # JPY 그래프 (오른쪽 y축)
            ax2 = ax1.twinx()
            color2 = '#ff7f0e'  # 주황색
            ax2.set_ylabel('JPY(100)/KRW', color=color2, fontsize=10)
            line2 = ax2.plot(jpy_data['search_date'], jpy_data['bkpr'],
                             color=color2, label='JPY(100)/KRW', linewidth=2, marker='o', markersize=4)
            ax2.tick_params(axis='y', labelcolor=color2)

            # Y축 범위 설정 (JPY)
            y2_min, y2_max = ax2.get_ylim()
            y2_margin = (y2_max - y2_min) * 0.1
            ax2.set_ylim(y2_min - y2_margin, y2_max + y2_margin)

            # JPY 최고/최저 표시
            jpy_max_idx = jpy_data['bkpr'].idxmax()
            jpy_min_idx = jpy_data['bkpr'].idxmin()
            jpy_max = jpy_data.loc[jpy_max_idx]
            jpy_min = jpy_data.loc[jpy_min_idx]

            bbox_props2 = dict(boxstyle='round,pad=0.5', facecolor='white', edgecolor=color2, alpha=0.7)

            # 최대값 주석 위치 조정
            ax2.annotate(f'Max: {jpy_max["bkpr"]}',
                         xy=(jpy_max['search_date'], jpy_max['bkpr']),
                         xytext=(0, -20), textcoords='offset points',
                         color=color2, fontweight='bold',
                         bbox=bbox_props2,
                         ha='center', va='bottom')

            # 최소값 주석 위치 조정
            ax2.annotate(f'Min: {jpy_min["bkpr"]}',
                         xy=(jpy_min['search_date'], jpy_min['bkpr']),
                         xytext=(0, 20), textcoords='offset points',
                         color=color2, fontweight='bold',
                         bbox=bbox_props2,
                         ha='center', va='top')

            # 범례 추가
            lines = line1 + line2
            labels = [l.get_label() for l in lines]
            ax1.legend(lines, labels, loc='upper left', frameon=True,
                       facecolor='white', edgecolor='gray',
                       bbox_to_anchor=(0.01, 0.99))

            # 그리드 설정
            ax1.yaxis.grid(True, linestyle='-', alpha=0.2)

            # 모든 날짜에 대한 세로선 추가
            for date in date_range:
                ax1.axvline(x=date, color='gray', linestyle=':', alpha=0.2)

            # x축 날짜 설정
            ax1.xaxis.set_major_formatter(mdates.DateFormatter('%Y-%m-%d'))
            ax1.set_xticks(date_range)
            x_labels = [date.strftime('%Y-%m-%d') for date in date_range]
            ax1.set_xticklabels(x_labels, rotation=45, ha='right', fontsize=8)

            # 그래프 제목 설정
            plt.title(
                f'Exchange Rate Trends\n({actual_start_date.strftime("%Y.%m.%d")} ~ {actual_end_date.strftime("%Y.%m.%d")})',
                pad=20, fontsize=12, fontweight='bold')

            # 테두리 설정
            for spine in ax1.spines.values():
                spine.set_visible(True)
                spine.set_linewidth(0.5)
                spine.set_color('#cccccc')

            # 여백 조정
            plt.tight_layout()

            # 그래프 저장 경로 설정 및 저장
            filename = f'exchange_rate_{actual_end_date.strftime("%Y%m%d")}.png'
            save_path = self.graph_dir / filename
            plt.savefig(save_path, dpi=300, bbox_inches='tight')
            plt.close()
            logger.info(f"그래프가 저장되었습니다: {save_path}")

            # 그래프 생성 후 오래된 파일 삭제
            self.clean_old_graph_files(days=3)
            logger.info(f"오래된 그래프를 삭제하였습니다.")

            # Path 객체 반환 (bool 대신)
            return save_path

        except Exception as e:
            logger.error(f"그래프 생성 중 오류 발생: {str(e)}")
            raise

    # 그래프 저장 후 오래된 파일 정리
    def clean_old_graph_files(self, days=3):
        """오래된 그래프 파일 삭제"""
        cleaner = FileCleaner(target_dir=self.graph_dir, days=days)
        cleaner.remove_old_files()


# 모듈 테스트용 코드
if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )

    try:
        db_connector = MySQLConnector()
        visualizer = ExchangeRateVisualizer(db_connector)

        # 최근 3개월 데이터로 그래프 생성
        visualizer.create_visualization(months=3)

        # 오래된 그래프 파일 삭제
        visualizer.clean_old_graph_files(days=3)

    except Exception as e:
        logger.error(f"실행 중 오류 발생: {str(e)}")
    finally:
        if 'db_connector' in locals():
            db_connector.close()