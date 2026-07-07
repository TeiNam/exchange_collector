# utils/gold_price_collector.py
"""KRX 금시세 수집기

KRXGoldClient로 금 99.99 일별매매정보를 조회해 gold_prices 테이블에 저장한다.
KRX는 T일 종가를 당일 저녁 이후 제공하므로, 기준일 데이터가 없으면
최근 평일까지 거슬러 올라가며 조회한다(최대 7일).
"""

import logging
from datetime import timedelta

from mysql.connector import Error

from utils.krx_gold_client import KRXGoldClient
from utils.time_utils import kst_today

logger = logging.getLogger(__name__)

# 데이터가 없을 때(휴장일 등) 거슬러 올라가며 조회할 최대 일수
MAX_LOOKBACK_DAYS = 7


class GoldPriceCollector:
    """KRX API에서 금시세를 수집해 저장한다"""

    def __init__(self, db_connector, client=None):
        self.db_connector = db_connector
        self.client = client or KRXGoldClient()

    def collect_data(self) -> list[dict]:
        """가장 최근 거래일의 금시세를 조회한다 (없으면 최대 7일 소급)."""
        today = kst_today()
        for delta in range(MAX_LOOKBACK_DAYS):
            bas_dd = (today - timedelta(days=delta)).strftime('%Y%m%d')
            rows = self.client.get_gold_prices(bas_dd)
            if rows:
                logger.info(f"금시세 수집 완료: {bas_dd} 기준 {len(rows)}종목")
                return rows
        logger.warning(f"최근 {MAX_LOOKBACK_DAYS}일간 금시세 데이터가 없습니다.")
        return []

    def save_data(self, rows: list[dict]) -> None:
        """금시세를 gold_prices 테이블에 저장한다 (종목+날짜 중복 시 갱신)."""
        if not rows:
            return

        # 같은 (종목, 기준일) 중복 저장 방지 + 정정 반영을 위해 UPSERT
        insert_query = """
        INSERT INTO gold_prices
        (isu_cd, isu_nm, clsprc, cmpprevdd_prc, fluc_rt,
         opnprc, hgprc, lwprc, trdvol, trdval, search_date)
        VALUES
        (%(isu_cd)s, %(isu_nm)s, %(clsprc)s, %(cmpprevdd_prc)s, %(fluc_rt)s,
         %(opnprc)s, %(hgprc)s, %(lwprc)s, %(trdvol)s, %(trdval)s, %(search_date)s)
        ON DUPLICATE KEY UPDATE
            clsprc=VALUES(clsprc), cmpprevdd_prc=VALUES(cmpprevdd_prc),
            fluc_rt=VALUES(fluc_rt), opnprc=VALUES(opnprc),
            hgprc=VALUES(hgprc), lwprc=VALUES(lwprc),
            trdvol=VALUES(trdvol), trdval=VALUES(trdval)
        """
        # search_date는 'YYYYMMDD' → DATE 컬럼에 그대로 넣어도 MySQL이 파싱하지만
        # 명시적으로 하이픈 형식으로 변환해 안전하게 저장
        params = [
            {**r, 'search_date': f"{r['search_date'][:4]}-{r['search_date'][4:6]}-{r['search_date'][6:]}"}
            for r in rows
        ]
        try:
            connection = self.db_connector.get_connection()
            with connection.cursor() as cursor:
                cursor.executemany(insert_query, params)
            connection.commit()
            logger.info(f"금시세 {len(params)}종목이 저장되었습니다.")
        except Error as e:
            logger.error(f"금시세 저장 중 오류 발생: {str(e)}")
            raise

    def run(self) -> None:
        """금시세 수집 및 저장 프로세스 실행"""
        try:
            rows = self.collect_data()
            self.save_data(rows)
            logger.info("금시세 수집 및 저장이 완료되었습니다.")
        except Exception as e:
            logger.error(f"금시세 처리 중 오류 발생: {str(e)}")
            raise
