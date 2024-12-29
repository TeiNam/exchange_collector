# utils/holiday_checker.py

import requests
import xml.etree.ElementTree as ET
from datetime import datetime
import logging
from configs.apis_setting import HOLIDAY_API_CONFIG

# 로거 설정
logger = logging.getLogger(__name__)


class HolidayChecker:
    """공휴일 조회 클래스"""

    def __init__(self):
        """
        HolidayChecker 초기화
        configs/apis_setting.py에서 API 설정을 로드하여 사용
        """
        self.api_key = HOLIDAY_API_CONFIG['api_key']
        self.base_url = HOLIDAY_API_CONFIG['base_url']

        if not self.api_key:
            raise ValueError("HOLIDAY_API_KEY가 환경변수에 설정되지 않았습니다.")

        logger.debug("HolidayChecker가 초기화되었습니다.")

    def _check_response_status(self, root):
        """API 응답 상태 확인"""
        header = root.find('.//header')
        if header is not None:
            result_code = header.find('resultCode')
            result_msg = header.find('resultMsg')

            if result_code is not None and result_code.text != '00':
                error_msg = result_msg.text if result_msg is not None else "알 수 없는 오류"
                raise ValueError(f"API 오류: {error_msg}")

            if result_code is None or result_msg is None:
                raise ValueError("API 응답에 필수 헤더 정보가 없습니다.")

    def check_holiday(self, date=None):
        """
        특정 날짜가 공휴일인지 확인

        Args:
            date (datetime, optional): 확인할 날짜. 기본값은 None (현재 날짜 사용)

        Returns:
            dict: {
                'is_holiday': bool,  # 공휴일 여부
                'holiday_name': str or None,  # 공휴일 이름 (공휴일이 아닌 경우 None)
                'date': str  # 확인한 날짜 (YYYYMMDD 형식)
            }

        Raises:
            ValueError: API 응답 오류
            requests.RequestException: API 호출 오류
            ET.ParseError: XML 파싱 오류
        """
        try:
            if date is None:
                date = datetime.now()

            target_date = date.strftime('%Y%m%d')
            params = {
                'serviceKey': self.api_key,
                'solYear': date.strftime('%Y'),
                'solMonth': date.strftime('%m')
            }

            logger.debug(f"공휴일 API 호출: {date.strftime('%Y년 %m월')} 조회")
            response = requests.get(self.base_url, params=params)
            response.raise_for_status()

            # XML 파싱
            root = ET.fromstring(response.content)

            # 응답 상태 확인
            self._check_response_status(root)

            # 공휴일 데이터 확인
            items = root.find('.//items')
            if items is not None:
                for item in items.findall('item'):
                    locdate = item.find('locdate')
                    is_holiday = item.find('isHoliday')

                    if (locdate is not None and locdate.text == target_date and
                            is_holiday is not None and is_holiday.text == 'Y'):
                        date_name = item.find('dateName')
                        holiday_name = date_name.text if date_name is not None else "공휴일"

                        logger.info(f"공휴일 확인: {target_date}은 {holiday_name}입니다.")
                        return {
                            'is_holiday': True,
                            'holiday_name': holiday_name,
                            'date': target_date
                        }

            logger.info(f"공휴일 아님: {target_date}")
            return {
                'is_holiday': False,
                'holiday_name': None,
                'date': target_date
            }

        except requests.RequestException as e:
            logger.error(f"API 호출 중 오류 발생: {str(e)}", exc_info=True)
            raise
        except ET.ParseError as e:
            logger.error(f"XML 파싱 중 오류 발생: {str(e)}", exc_info=True)
            raise
        except Exception as e:
            logger.error(f"공휴일 확인 중 오류 발생: {str(e)}", exc_info=True)
            raise


# 모듈 테스트용 코드
if __name__ == "__main__":
    # 테스트를 위한 로깅 설정
    logging.basicConfig(
        level=logging.DEBUG,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )

    try:
        checker = HolidayChecker()
        result = checker.check_holiday()

        if result['is_holiday']:
            print(f"오늘({result['date']})은 {result['holiday_name']}입니다.")
        else:
            print(f"오늘({result['date']})은 공휴일이 아닙니다.")

    except Exception as e:
        print(f"오류 발생: {str(e)}")