# utils/gold_price_visualizer.py
"""금시세 시각화

ExchangeRateVisualizer의 지표 계산/차트 헬퍼를 재사용해 금 99.99_1kg(원/g)의
가격 + MA + 볼린저 밴드 + RSI 차트를 생성한다.
헬퍼들이 'bkpr' 컬럼을 사용하므로 종가(clsprc)를 그 이름으로 매핑해 넘긴다.
"""

import logging
from datetime import datetime, timedelta
from pathlib import Path

import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import pandas as pd

from modules.cleanup import FileCleaner
from modules.mysql_connector import MySQLConnector
from utils.exchange_rate_visualizer import ExchangeRateVisualizer
from utils.krx_gold_client import GOLD_1KG_ISU_CD

logger = logging.getLogger(__name__)


class GoldPriceVisualizer:
    """금시세(금 99.99_1kg) 기술적 지표 그래프 생성"""

    def __init__(self, db_connector):
        self.db_connector = db_connector
        self.root_dir = Path(__file__).resolve().parent.parent
        self.graph_dir = self.root_dir / 'graph_files'
        if not self.graph_dir.exists():
            self.graph_dir.mkdir(parents=True)

    def fetch_data_range(self, start_date, end_date) -> pd.DataFrame:
        """기간 범위의 금 종가 조회 (bkpr 컬럼명으로 반환해 헬퍼와 호환)."""
        query = """
        SELECT clsprc, search_date
        FROM gold_prices
        WHERE isu_cd = %s AND search_date >= %s AND search_date <= %s
        ORDER BY search_date
        """
        connection = self.db_connector.get_connection()
        with connection.cursor() as cursor:
            cursor.execute(query, (GOLD_1KG_ISU_CD, start_date, end_date))
            rows = cursor.fetchall()
        df = pd.DataFrame(rows, columns=['bkpr', 'search_date'])
        df['bkpr'] = df['bkpr'].astype(float)
        df['search_date'] = pd.to_datetime(df['search_date'])
        return df

    def create_visualization(self, months=3):
        """금시세 변동 + 기술적 지표 그래프 생성"""
        try:
            end_date = datetime.now().date()
            start_date = end_date - timedelta(days=months * 31 + 30)

            df = self.fetch_data_range(start_date, end_date)
            if df.empty:
                logger.warning("해당 기간의 금시세 데이터가 없습니다.")
                return False

            gold = ExchangeRateVisualizer._compute_indicators(df)

            display_start = end_date - timedelta(days=months * 31)
            gold = gold[gold['search_date'] >= pd.Timestamp(display_start)]
            if gold.empty:
                logger.warning("표시 기간의 금시세 데이터가 없습니다.")
                return False

            actual_start = gold['search_date'].min()
            actual_end = gold['search_date'].max()

            gold_color = '#D4A017'   # 금색
            bg_color = '#FAFBFC'
            grid_color = '#E5E7EB'

            # 2행: 금 가격, 금 RSI
            fig, (ax_price, ax_rsi) = plt.subplots(
                2, 1, figsize=(12, 7), facecolor='white', sharex=True,
                gridspec_kw={'height_ratios': [3, 1], 'hspace': 0.12}
            )

            # 가격 스케일이 20만원대라 y_margin을 넉넉히
            viz = ExchangeRateVisualizer(self.db_connector)
            viz._plot_price_chart(ax_price, gold, '금 99.99 (1kg)',
                                  gold_color, bg_color, grid_color, y_margin=2000)
            ExchangeRateVisualizer._plot_rsi_chart(ax_rsi, gold, '금',
                                                   gold_color, bg_color, grid_color)

            ax_rsi.xaxis.set_major_locator(mdates.WeekdayLocator(byweekday=mdates.MO))
            ax_rsi.xaxis.set_major_formatter(mdates.DateFormatter('%m/%d'))
            ax_rsi.tick_params(axis='x', labelsize=8, rotation=0, colors='#374151')

            fig.suptitle(
                f'금시세 동향 + 기술적 지표  '
                f'({actual_start.strftime("%Y.%m.%d")} ~ {actual_end.strftime("%Y.%m.%d")})',
                fontsize=13, fontweight='bold', color='#1F2937', y=0.99
            )
            plt.tight_layout(rect=[0, 0, 1, 0.97])

            filename = f'gold_price_{actual_end.strftime("%Y%m%d")}.png'
            save_path = self.graph_dir / filename
            plt.savefig(save_path, dpi=150, bbox_inches='tight',
                        facecolor='white', edgecolor='none')
            plt.close()
            logger.info(f"금시세 그래프가 저장되었습니다: {save_path}")

            FileCleaner(target_dir=self.graph_dir, days=3).remove_old_files()
            return save_path

        except Exception as e:
            logger.error(f"금시세 그래프 생성 중 오류 발생: {str(e)}")
            raise


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    db = MySQLConnector()
    try:
        GoldPriceVisualizer(db).create_visualization(months=3)
    finally:
        db.close()
