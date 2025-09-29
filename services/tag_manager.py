# services/tag_manager.py
import yaml
import logging
from pathlib import Path

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

if not logger.hasHandlers():
    handler = logging.StreamHandler()
    handler.setLevel(logging.INFO)  # 핸들러의 레벨도 INFO로 설정
    formatter = logging.Formatter('[%(levelname)s] %(asctime)s - %(message)s')
    handler.setFormatter(formatter)
    logger.addHandler(handler)

class PLCTagManager:
    def __init__(self, config_path="config/plc_tags.yaml"):
        self.config_path = Path(config_path)
        self.memory_areas = {}
        self.tube1_tags = {}
        self.load_config()

    def load_config(self):
        """YAML 설정 파일 로드"""
        try:
            with open(self.config_path, 'r', encoding='utf-8') as f:
                config = yaml.safe_load(f)
                self.memory_areas = config.get('memory_areas', {})
                self.tube1_tags = config.get('Tube1_tags', {})
            logger.info(f"태그 설정 로드 완료: {len(self.tube1_tags)} Tube1 태그")
        except Exception as e:
            logger.error(f"태그 설정 로드 실패: {e}")
            raise

    def get_tag_info(self, tag_name):
        """
        태그 이름으로 태그 정보 조회
        Returns:
            dict: {
                'area': 메모리 영역 코드(int),
                'word_addr': 워드 주소(int),
                'word_count': 워드 개수(int),
                'data_type': 데이터 타입(str),
                'description': 설명(str)
            }
        """
        if tag_name not in self.tube1_tags:
            raise KeyError(f"태그를 찾을 수 없음: {tag_name}")

        tag_info = self.tube1_tags[tag_name].copy()
        # 메모리 영역 문자열을 코드값으로 변환
        tag_info['area'] = self.memory_areas[tag_info['area']]
        return tag_info