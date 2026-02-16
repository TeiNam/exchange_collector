# utils/exchange_rate_visualizer.py

from pathlib import Path
import matplotlib
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import matplotlib.font_manager as fm
import pandas as pd
from datetime import datetime, timedelta
import logging
from modules.mysql_connector import MySQLConnector
from modules.cleanup import FileCleaner


logger = logging.getLogger(__name__)

# 한글 폰트 설정
def _setup_korean_font():
    """시스템에서 한글 폰트를 찾아 matplotlib에 설정"""
    import glob

    # 1) 시스템 폰트 경로에서 나눔 폰트 직접 탐색 (도커 환경 대응)
    nanum_paths = glob.glob('/usr/share/fonts/**/Nanum*.ttf', recursive=True)
    if nanum_paths:
        font_path = nanum_paths[0]
        fm.fontManager.addfont(font_path)
        font_prop = fm.FontProperties(fname=font_path)
        plt.rcParams['font.family'] = font_prop.get_name()
        plt.rcParams['axes.unicode_minus'] = False
        logger.info(f"한글 폰트 설정 (파일): {font_path}")
        return True

    # 2) 등록된 폰트 목록에서 한글 폰트 탐색 (macOS/Windows)
    korean_fonts = ['Apple SD Gothic Neo', 'Nanum Gothic', 'AppleGothic', 'Malgun Gothic']
    for font_name in korean_fonts:
        if any(f.name == font_name for f in fm.fontManager.ttflist):
            plt.rcParams['font.family'] = font_name
            plt.rcParams['axes.unicode_minus'] = False
            logger.info(f"한글 폰트 설정: {font_name}")
            return True

    logger.warning("한글 폰트를 찾을 수 없습니다. 그래프에서 한글이 깨질 수 있습니다.")
    return False

_setup_korean_font()


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

    @staticmethod
    def _compute_indicators(currency_df: pd.DataFrame) -> pd.DataFrame:
        """통화 DataFrame에 기술적 지표 컬럼을 추가한다."""
        df = currency_df.copy().sort_values('search_date').reset_index(drop=True)
        prices = df['bkpr']

        # 이동평균선 (5일, 20일)
        df['ma5'] = prices.rolling(window=5).mean()
        df['ma20'] = prices.rolling(window=20).mean()

        # 볼린저 밴드 (20일, 2σ)
        df['bb_mid'] = df['ma20']
        rolling_std = prices.rolling(window=20).std(ddof=0)
        df['bb_upper'] = df['bb_mid'] + 2 * rolling_std
        df['bb_lower'] = df['bb_mid'] - 2 * rolling_std

        # RSI (14일, Wilder 방식)
        delta = prices.diff()
        gain = delta.clip(lower=0)
        loss = (-delta.clip(upper=0))
        avg_gain = gain.ewm(alpha=1 / 14, min_periods=14, adjust=False).mean()
        avg_loss = loss.ewm(alpha=1 / 14, min_periods=14, adjust=False).mean()
        rs = avg_gain / avg_loss
        df['rsi'] = 100 - (100 / (1 + rs))

        return df

    def _plot_price_chart(self, ax, df: pd.DataFrame, label: str,
                          main_color: str, bg_color: str, grid_color: str,
                          y_margin: float = 20):
        """환율 + MA + 볼린저 밴드 차트를 그린다."""
        ax.set_facecolor(bg_color)

        # 볼린저 밴드 영역
        valid_bb = df.dropna(subset=['bb_upper', 'bb_lower'])
        if not valid_bb.empty:
            ax.fill_between(valid_bb['search_date'],
                            valid_bb['bb_lower'], valid_bb['bb_upper'],
                            alpha=0.10, color='#9CA3AF', label='볼린저 밴드')

        # 환율 라인
        ax.plot(df['search_date'], df['bkpr'],
                color=main_color, linewidth=2, label=label, zorder=3)

        # 이동평균선
        ax.plot(df['search_date'], df['ma5'],
                color='#EF4444', linewidth=1, alpha=0.8, label='MA5', zorder=2)
        ax.plot(df['search_date'], df['ma20'],
                color='#8B5CF6', linewidth=1, alpha=0.8, label='MA20', zorder=2)

        # 최고/최저 포인트
        idx_max = df['bkpr'].idxmax()
        idx_min = df['bkpr'].idxmin()
        row_max = df.loc[idx_max]
        row_min = df.loc[idx_min]

        ax.scatter(row_max['search_date'], row_max['bkpr'],
                   color='#DC2626', s=50, zorder=5, edgecolors='white', linewidth=1.5)
        ax.scatter(row_min['search_date'], row_min['bkpr'],
                   color='#16A34A', s=50, zorder=5, edgecolors='white', linewidth=1.5)
        ax.annotate(f'▲ {row_max["bkpr"]:,.0f}',
                    xy=(row_max['search_date'], row_max['bkpr']),
                    xytext=(0, 10), textcoords='offset points',
                    fontsize=8, fontweight='bold', color='#DC2626', ha='center')
        ax.annotate(f'▼ {row_min["bkpr"]:,.0f}',
                    xy=(row_min['search_date'], row_min['bkpr']),
                    xytext=(0, -14), textcoords='offset points',
                    fontsize=8, fontweight='bold', color='#16A34A', ha='center')

        # 최신값 표시
        latest = df.iloc[-1]
        ax.annotate(f'{latest["bkpr"]:,.0f}',
                    xy=(latest['search_date'], latest['bkpr']),
                    xytext=(8, 0), textcoords='offset points',
                    fontsize=9, fontweight='bold', color=main_color, va='center')

        # y축 범위
        y_min = df['bkpr'].min() - y_margin
        y_max = df['bkpr'].max() + y_margin
        ax.set_ylim(y_min, y_max)

        ax.set_ylabel(f'{label} (원)', fontsize=10, fontweight='bold', color=main_color)
        ax.legend(loc='upper left', fontsize=7, framealpha=0.7)
        ax.yaxis.grid(True, color=grid_color, linewidth=0.8)
        ax.xaxis.grid(False)
        ax.tick_params(axis='y', labelsize=8, colors='#374151')
        for spine in ax.spines.values():
            spine.set_visible(False)

    @staticmethod
    def _plot_rsi_chart(ax, df: pd.DataFrame, label: str,
                        main_color: str, bg_color: str, grid_color: str):
        """RSI 차트를 그린다."""
        ax.set_facecolor(bg_color)

        valid_rsi = df.dropna(subset=['rsi'])
        if valid_rsi.empty:
            ax.text(0.5, 0.5, 'RSI 데이터 부족', transform=ax.transAxes,
                    ha='center', va='center', fontsize=10, color='#9CA3AF')
            return

        ax.plot(valid_rsi['search_date'], valid_rsi['rsi'],
                color=main_color, linewidth=1.5)

        # 과매수/과매도 기준선
        ax.axhline(y=70, color='#DC2626', linewidth=0.8, linestyle='--', alpha=0.6)
        ax.axhline(y=30, color='#16A34A', linewidth=0.8, linestyle='--', alpha=0.6)
        ax.axhline(y=50, color='#9CA3AF', linewidth=0.5, linestyle=':', alpha=0.5)

        # 과매수/과매도 영역 색칠
        ax.fill_between(valid_rsi['search_date'], 70, 100, alpha=0.05, color='#DC2626')
        ax.fill_between(valid_rsi['search_date'], 0, 30, alpha=0.05, color='#16A34A')

        # 최신 RSI 값 표시
        latest_rsi = valid_rsi.iloc[-1]['rsi']
        ax.annotate(f'{latest_rsi:.1f}',
                    xy=(valid_rsi.iloc[-1]['search_date'], latest_rsi),
                    xytext=(8, 0), textcoords='offset points',
                    fontsize=9, fontweight='bold', color=main_color, va='center')

        ax.set_ylim(0, 100)
        ax.set_ylabel(f'{label} RSI', fontsize=10, fontweight='bold', color=main_color)
        ax.yaxis.grid(True, color=grid_color, linewidth=0.8)
        ax.xaxis.grid(False)
        ax.tick_params(axis='y', labelsize=8, colors='#374151')
        for spine in ax.spines.values():
            spine.set_visible(False)

    def create_visualization(self, months=3):
        """환율 변동 + 기술적 지표 그래프 생성"""
        try:
            # 날짜 범위 계산 (지표 계산용 여유분 포함)
            end_date = datetime.now().date()
            start_date = end_date - timedelta(days=months * 31 + 30)

            # 데이터 조회
            df = self.fetch_data_range(start_date, end_date)
            if df.empty:
                logger.warning("해당 기간의 데이터가 없습니다.")
                return False

            # USD / JPY 분리 및 지표 계산
            usd = self._compute_indicators(df[df['cur_unit'] == 'USD'])
            jpy = self._compute_indicators(df[df['cur_unit'] == 'JPY(100)'])

            # 표시 범위 필터링 (지표 계산 후 원래 기간만 표시)
            display_start = end_date - timedelta(days=months * 31)
            usd = usd[usd['search_date'] >= pd.Timestamp(display_start)]
            jpy = jpy[jpy['search_date'] >= pd.Timestamp(display_start)]

            actual_start = min(usd['search_date'].min(), jpy['search_date'].min())
            actual_end = max(usd['search_date'].max(), jpy['search_date'].max())

            # 색상 팔레트
            usd_color = '#2563EB'
            jpy_color = '#F59E0B'
            bg_color = '#FAFBFC'
            grid_color = '#E5E7EB'

            # 4행 레이아웃: USD 환율, USD RSI, JPY 환율, JPY RSI (통화별 그룹)
            fig, axes = plt.subplots(
                4, 1, figsize=(12, 12), facecolor='white',
                sharex=True,
                gridspec_kw={'height_ratios': [3, 1, 3, 1], 'hspace': 0.12}
            )
            ax_usd, ax_rsi_usd, ax_jpy, ax_rsi_jpy = axes

            # USD 환율 + MA + 볼린저 밴드
            self._plot_price_chart(ax_usd, usd, 'USD/KRW',
                                   usd_color, bg_color, grid_color, y_margin=20)

            # USD RSI
            self._plot_rsi_chart(ax_rsi_usd, usd, 'USD',
                                 usd_color, bg_color, grid_color)

            # JPY 환율 + MA + 볼린저 밴드
            self._plot_price_chart(ax_jpy, jpy, 'JPY(100)/KRW',
                                   jpy_color, bg_color, grid_color, y_margin=15)

            # JPY RSI
            self._plot_rsi_chart(ax_rsi_jpy, jpy, 'JPY',
                                 jpy_color, bg_color, grid_color)

            # x축 설정 (최하단)
            ax_rsi_jpy.xaxis.set_major_locator(mdates.WeekdayLocator(byweekday=mdates.MO))
            ax_rsi_jpy.xaxis.set_major_formatter(mdates.DateFormatter('%m/%d'))
            ax_rsi_jpy.tick_params(axis='x', labelsize=8, rotation=0, colors='#374151')

            # 제목
            fig.suptitle(
                f'환율 동향 + 기술적 지표  ({actual_start.strftime("%Y.%m.%d")} ~ {actual_end.strftime("%Y.%m.%d")})',
                fontsize=13, fontweight='bold', color='#1F2937', y=0.99
            )

            plt.tight_layout(rect=[0, 0, 1, 0.97])

            # 저장
            filename = f'exchange_rate_{actual_end.strftime("%Y%m%d")}.png'
            save_path = self.graph_dir / filename
            plt.savefig(save_path, dpi=150, bbox_inches='tight',
                        facecolor='white', edgecolor='none')
            plt.close()
            logger.info(f"그래프가 저장되었습니다: {save_path}")

            self.clean_old_graph_files(days=3)
            logger.info("오래된 그래프를 삭제하였습니다.")

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