# utils/toss_usd_collector.py
"""토스 API 기반 USD 환율 수집기

TossExchangeClient로 USD/KRW를 조회해 exchange_rates 테이블에 저장한다.
JPY는 기존 ExchangeRateCollector(수출입은행)가 담당하는 하이브리드 구성이다.

컬럼 매핑 (토스는 midRate/rate만 제공):
    deal_bas_r, bkpr <- midRate (매매기준율; 지표·그래프가 사용하는 핵심 값)
    tts              <- rate    (매수 환율)
    ttb              <- midRate  (토스 미제공, NOT NULL 회피용 플레이스홀더)
"""

import logging

from mysql.connector import Error

from utils.toss_exchange_client import TossExchangeClient
from utils.time_utils import kst_today

logger = logging.getLogger(__name__)


class TossUSDCollector:
    """토스 API에서 USD 환율을 수집해 저장한다"""

    def __init__(self, db_connector, client=None):
        self.db_connector = db_connector
        self.client = client or TossExchangeClient()

    def collect_data(self) -> dict:
        """토스에서 USD/KRW 환율을 조회한다"""
        rate = self.client.get_usd_krw()
        logger.info(
            f"USD 환율 수집 완료: 매매기준율 {rate['mid_rate']} "
            f"(rate={rate['rate']}, {rate['rate_change_type']})"
        )
        return rate

    def save_data(self, rate: dict) -> None:
        """USD 환율을 exchange_rates 테이블에 저장한다"""
        insert_query = """
        INSERT INTO exchange_rates
        (cur_unit, ttb, tts, deal_bas_r, bkpr, cur_nm, search_date)
        VALUES (%(cur_unit)s, %(ttb)s, %(tts)s, %(deal_bas_r)s, %(bkpr)s, %(cur_nm)s, %(search_date)s)
        """
        mid = rate['mid_rate']
        data = {
            'cur_unit': 'USD',
            'ttb': mid,          # 토스 미제공 → midRate 플레이스홀더
            'tts': rate['rate'],
            'deal_bas_r': mid,
            'bkpr': mid,         # visualizer가 사용 → midRate로 채움
            'cur_nm': '미국 달러',
            'search_date': kst_today(),
        }
        try:
            connection = self.db_connector.get_connection()
            with connection.cursor() as cursor:
                cursor.execute(insert_query, data)
            connection.commit()
            logger.info(f"USD 환율 데이터가 저장되었습니다 (매매기준율 {mid}).")
        except Error as e:
            logger.error(f"USD 데이터 저장 중 오류 발생: {str(e)}")
            raise

    def run(self) -> None:
        """USD 환율 수집 및 저장 프로세스 실행"""
        try:
            rate = self.collect_data()
            self.save_data(rate)
            logger.info("USD 환율 수집 및 저장이 완료되었습니다.")
        except Exception as e:
            logger.error(f"USD 환율 처리 중 오류 발생: {str(e)}")
            raise
