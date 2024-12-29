from pathlib import Path
from datetime import datetime, timedelta
import logging

logger = logging.getLogger(__name__)

class FileCleaner:
    def __init__(self, target_dir, days=3):
        """
        파일 정리 클래스
        :param target_dir: 정리할 디렉토리 경로
        :param days: 기준이 되는 날짜 (이 기간 이상된 파일 삭제)
        """
        self.target_dir = Path(target_dir)
        self.days = days

    def remove_old_files(self):
        """지정된 기간 이상된 파일 삭제"""
        if not self.target_dir.exists() or not self.target_dir.is_dir():
            logger.warning(f"대상 디렉토리가 존재하지 않거나 디렉토리가 아닙니다: {self.target_dir}")
            return

        now = datetime.now()
        cutoff_time = now - timedelta(days=self.days)

        try:
            for file in self.target_dir.iterdir():
                if file.is_file():
                    file_mtime = datetime.fromtimestamp(file.stat().st_mtime)
                    if file_mtime < cutoff_time:
                        file.unlink()
                        logger.info(f"삭제된 파일: {file}")
        except Exception as e:
            logger.error(f"파일 삭제 중 오류 발생: {str(e)}")
            raise