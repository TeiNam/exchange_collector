# utils/exchange_rate_collector.py
import requests
import logging
from datetime import datetime
from mysql.connector import Error
from configs.apis_setting import EXCHANGE_RATE_API_CONFIG
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from urllib3.exceptions import InsecureRequestWarning
from modules.mysql_connector import MySQLConnector

# InsecureRequestWarning 경고 숨기기
requests.packages.urllib3.disable_warnings(InsecureRequestWarning)

# 로거 설정
logger = logging.getLogger(__name__)


class ExchangeRateCollector:
    def __init__(self, db_connector, search_date=None):
        self.api_key = EXCHANGE_RATE_API_CONFIG['api_key']
        self.db_connector = db_connector
        self.target_currencies = ['USD', 'JPY(100)']
        self.base_url = EXCHANGE_RATE_API_CONFIG['base_url']
        self.search_date = search_date  # 검색할 날짜 추가

        # 세션 설정
        self.session = requests.Session()

        # 재시도 전략 설정
        retry_strategy = Retry(
            total=3,
            backoff_factor=0.5,
            status_forcelist=[500, 502, 503, 504]
        )

        adapter = HTTPAdapter(max_retries=retry_strategy)
        self.session.mount("http://", adapter)
        self.session.mount("https://", adapter)

    def collect_data(self):
        """한국수출입은행 API에서 환율 데이터 수집"""
        if not self.api_key:
            raise ValueError("EXCHANGE_RATE_API_KEY가 설정되지 않았습니다.")

        # search_date가 있으면 사용, 없으면 오늘 날짜 사용
        search_date = self.search_date or datetime.now().strftime('%Y%m%d')

        params = {
            'authkey': self.api_key,
            'searchdate': search_date,
            'data': 'AP01'
        }

        try:
            response = self.session.get(
                self.base_url,
                params=params,
                verify=False,
                timeout=10
            )
            response.raise_for_status()
            data = response.json()

            if not isinstance(data, list):
                raise ValueError(f"예상치 못한 응답 형식: {data}")

            filtered_data = [item for item in data if item['cur_unit'] in self.target_currencies]
            logger.info(f"{search_date} 환율 데이터 수집 완료: {len(filtered_data)}개 통화")
            return filtered_data

        except requests.exceptions.RequestException as e:
            logger.error(f"API 호출 중 오류 발생: {str(e)}")
            raise
        finally:
            self.session.close()

    def save_data(self, exchange_rates):
        """수집된 환율 데이터를 데이터베이스에 저장"""
        insert_query = """
        INSERT INTO exchange_rates 
        (cur_unit, ttb, tts, deal_bas_r, bkpr, cur_nm, search_date)
        VALUES (%(cur_unit)s, %(ttb)s, %(tts)s, %(deal_bas_r)s, %(bkpr)s, %(cur_nm)s, %(search_date)s)
        """

        try:
            # 검색 날짜를 DATE 타입으로 변환
            search_date = datetime.strptime(self.search_date or datetime.now().strftime('%Y%m%d'), '%Y%m%d').date()

            connection = self.db_connector.get_connection()
            with connection.cursor() as cursor:
                for rate in exchange_rates:
                    cleaned_data = {
                        'cur_unit': rate['cur_unit'],
                        'ttb': float(rate['ttb'].replace(',', '')),
                        'tts': float(rate['tts'].replace(',', '')),
                        'deal_bas_r': float(rate['deal_bas_r'].replace(',', '')),
                        'bkpr': float(rate['bkpr'].replace(',', '')),
                        'cur_nm': rate['cur_nm'],
                        'search_date': search_date
                    }
                    cursor.execute(insert_query, cleaned_data)
                connection.commit()
                logger.info(f"{len(exchange_rates)}개의 환율 데이터가 저장되었습니다.")
        except Error as e:
            logger.error(f"데이터 저장 중 오류 발생: {str(e)}")
            raise

    def run(self):
        """환율 수집 및 저장 프로세스 실행"""
        try:
            exchange_rates = self.collect_data()
            if exchange_rates:
                self.save_data(exchange_rates)
                logger.info("환율 데이터 수집 및 저장이 완료되었습니다.")
            else:
                logger.warning("수집된 환율 데이터가 없습니다.")
        except Exception as e:
            logger.error(f"환율 데이터 처리 중 오류 발생: {str(e)}")
            raise


# 모듈 테스트용 코드
if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )

    try:
        # 테스트할 날짜를 직접 지정 (YYYYMMDD 형식)
        search_date = '20241227'  # 여기에 원하는 날짜를 입력

        db_connector = MySQLConnector()
        collector = ExchangeRateCollector(db_connector, search_date=search_date)
        collector.run()

    except Exception as e:
        logger.error(f"실행 중 오류 발생: {str(e)}")
    finally:
        if 'db_connector' in locals():
            db_connector.close()