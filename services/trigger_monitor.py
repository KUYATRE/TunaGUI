from PySide6.QtCore import QTimer, QObject, Signal
import logging
import services.tag_manager as TM

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

if not logger.hasHandlers():
    handler = logging.StreamHandler()
    handler.setLevel(logging.INFO)  # 핸들러의 레벨도 INFO로 설정
    formatter = logging.Formatter('[%(levelname)s] %(asctime)s - %(message)s')
    handler.setFormatter(formatter)
    logger.addHandler(handler)

class TriggerMonitor(QObject):
    data_received = Signal(str, int)  # tube_id, job_id
    error_occurred = Signal(str)
    tuning_data_updated = Signal(dict)

    def __init__(self, fins_client, is_reconnecting=False, interval_ms=1000, bit_offsets=None):
        super().__init__()
        self.fins_client = fins_client
        self.is_reconnecting = is_reconnecting
        self.timer = QTimer()
        self.timer.timeout.connect(self.check_trigger)
        self.interval_ms = interval_ms
        self.tag_manager = TM.PLCTagManager()
        self.tuning_data = None

        # bit_offsets를 리스트로 처리
        self.bit_offsets = bit_offsets if isinstance(bit_offsets, list) else [bit_offsets] if bit_offsets is not None else [0]
        self.previous_states = {offset: False for offset in self.bit_offsets}


    def start(self):
        """모니터링 시작"""
        self.timer.start(self.interval_ms)
        logger.info(f"Trigger monitoring started for bit offsets: {self.bit_offsets}")

    def stop(self):
        """모니터링 중지"""
        self.timer.stop()
        logger.info("Trigger monitoring stopped")

    def check_trigger(self):
        """각 비트 오프셋에 대해 트리거 상태 확인"""
        try:
            for bit_offset in self.bit_offsets:
                # FINS 통신으로 PLC의 해당 비트 읽기
                current_state = self.fins_client.read_word_bit(mem_area=0xAF, word_addr=0, bit_offset=bit_offset)
                previous_state = self.previous_states[bit_offset]

                # Rising edge 감지 (False → True)
                if current_state and not previous_state:
                    logger.info(f"Trigger detected at bit offset {bit_offset}")
                    self.handle_trigger_detection(bit_offset)
                    self.tuning_data = self.handle_tuning_data_trigger_detection(bit_offset)
                    # logger.info(f"Tuning data in trigger monitoring: {self.tuning_data}")

                # 현재 상태 저장
                self.previous_states[bit_offset] = current_state

        except Exception as e:
            error_msg = f"Trigger monitor error: {str(e)}"
            logger.error(error_msg)
            self.error_occurred.emit(error_msg)

    def handle_tuning_data_trigger_detection(self, bit_offset):
        """트리거 감지 시 처리 (bit offset이 1일 때만)"""
        if (bit_offset<1) or (bit_offset>6):
            logger.info("tuning data trigger not detected (bit offset is out of rage) - skipping...")
            return

        logger.info("tuning data trigger detected")

        try:
            tuning_data = self.read_tuning_data(bit_offset, self.fins_client, self.tag_manager)
            if tuning_data is not None:
                logger.info("tuning data read successfully")
                logger.info(tuning_data)
                self.tuning_data = tuning_data
                self.tuning_data_updated.emit(tuning_data)
                return tuning_data
            else:
                logger.error("tuning data read failed")
                return None
        except Exception as e:
            error_msg = f"Error reading tuning data: {str(e)}"
            logger.error(error_msg)
        
    def read_tuning_data(self, bit_offset, fins_client, tag_manager):
        """
        Zone 1~8까지의 튜닝 파라미터 데이터를 읽어오는 함수
        반환값: 
            {
                'T1_Z1': {'NP1': val, 'NP2': val, 'HP1': val, 'HP2': val},
                'T1_Z2': {'NP1': val, 'NP2': val, 'HP1': val, 'HP2': val},
                ...
            }
        """
        try:
            tuning_data = {}
            param_names = ['NP1', 'NP2', 'HP1', 'HP2']
            
            # Zone 1~8까지 순회
            for zone_num in range(1, 9):
                tag_name = f"Tube{bit_offset}_para_read_Z{zone_num}"
                
                try:
                    # 태그 정보 가져오기
                    tag_info = tag_manager.get_tag_info(tag_name)
                    
                    # 해당 zone의 4개 워드 데이터 읽기
                    words = fins_client.read_word(
                        mem_area=tag_info['area'],
                        word_addr=tag_info['word_addr'],
                        word_count=tag_info['word_count']
                    )
                    
                    # 읽은 데이터를 딕셔너리로 구성
                    zone_data = {
                        param_names[i]: words[i] 
                        for i in range(len(param_names))
                    }
                    
                    tuning_data[f'Tube{bit_offset}_Z{zone_num}'] = zone_data
                    
                    logger.debug(f"Tube{bit_offset}_Zone {zone_num} 튜닝 파라미터 읽기 성공: {zone_data}")
                    
                except Exception as e:
                    logger.error(f"Tube{bit_offset}_Zone {zone_num} 튜닝 파라미터 읽기 실패: {e}")
                    tuning_data[f'Tube{bit_offset}_Z{zone_num}'] = None
            
            logger.info("전체 튜닝 파라미터 읽기 완료")
            return tuning_data
            
        except Exception as e:
            logger.error(f"튜닝 데이터 읽기 중 오류 발생: {e}")
            return None
        

    def handle_trigger_detection(self, bit_offset):
        """트리거 감지 시 처리 (bit offset이 0일 때만)"""
        if bit_offset != 0:  # bit offset이 0이 아닌 경우 처리하지 않음
            return
        
        try:
            # tube_id와 job_id 읽기 (비트 오프셋 0에 해당하는 주소에서만 읽기)
            tube_id = self.read_tube_id(0)
            job_id = self.read_job_id(0)
            
            logger.info(f"Read data - Tube ID: {tube_id}, Job ID: {job_id}")
            self.data_received.emit(tube_id, job_id)

        except Exception as e:
            error_msg = f"Error reading trigger data: {str(e)}"
            logger.error(error_msg)
            self.error_occurred.emit(error_msg)

    def read_tube_id(self, bit_offset):
        """tube_id 읽기 (비트 오프셋에 따라 주소 계산)"""
        base_addr = 502  # 기본 주소
        addr_offset = bit_offset * 2  # 각 데이터 세트의 오프셋
        
        response = self.fins_client.read_word(
            memory_area=0xA0,
            word_addr=base_addr + addr_offset,
            word_count=1
        )
        return str(response[0])

    def read_job_id(self, bit_offset):
        """job_id 읽기 (비트 오프셋에 따라 주소 계산)"""
        base_addr = 503  # 기본 주소
        addr_offset = bit_offset * 2  # 각 데이터 세트의 오프셋
        
        response = self.fins_client.read_word(
            memory_area=0xA0,
            word_addr=base_addr + addr_offset,
            word_count=1
        )
        return response[0]