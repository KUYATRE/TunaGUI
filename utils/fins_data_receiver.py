from services.fins_comm import FinsUDPClient
import numpy as np
import pandas as pd


class FinsDataReceiver:
    def __init__(self, ip: str, plc_port: int, plc_node: int, pc_node: int):
        self.fins = FinsUDPClient(plc_ip=ip, plc_port=plc_port, plc_node=plc_node, pc_node=pc_node)
        self.tube_id = None
        self.job_id = None
        self.sheet_res_data = None

    def is_data_available(self, mem_area=0xA0, word_addr=0, bit_offset=3) -> bool:
        return self.fins.read_word_bit(mem_area=mem_area, word_addr=word_addr, bit_offset=bit_offset)

    def is_startup_mode(self, mem_area=0xA0, word_addr=0, bit_offset=2) -> bool:
        return self.fins.read_word_bit(mem_area=mem_area, word_addr=word_addr, bit_offset=bit_offset)

    def read_identifiers(self, mem_area=0xA2):
        self.tube_id = self.fins.read_word(mem_area=mem_area, word_addr=0)
        self.job_id = self.fins.read_word(mem_area=mem_area, word_addr=1)
        return self.tube_id, self.job_id

    def read_sheet_resistance(self, mem_area=0xA2, word_addr=2, word_count=99):
        return self.fins.read_word(mem_area=mem_area, word_addr=word_addr, word_count=word_count)

    def receive_all(self) -> tuple[int, int, list[int]]:
        if not self.is_data_available():
            print("데이터 수신 불가: ReadAvailable 비트 OFF")
            return None

        startup_mode = self.is_startup_mode()
        self.tube_id, self.job_id = self.read_identifiers()

        if startup_mode:
            print("시운전 모드: 더미 데이터 생성")
            generator = DummyDataGenerator()
            self.sheet_res_data = generator.generate_random_array(200, 205, 99, float)
        else:
            self.sheet_res_data = self.read_sheet_resistance()

        return self.tube_id, self.job_id, self.sheet_res_data


class DummyDataGenerator:
    def generate_random_array(self, start: float, end: float, size: int, dtype=float) -> np.ndarray:
        print("[DummyDataGenerator] 난수 배열 생성")
        if dtype == int:
            return np.random.randint(start, end + 1, size=size)
        return np.random.uniform(start, end, size=size)

    def generate_dummy_from_base(self, base_row: pd.Series, count: int = 10, start_jobno: int = None) -> pd.DataFrame:
        dummy_rows = []
        base_jobno = base_row.get('RS_JobNo', 0)
        start_jobno = start_jobno or (int(base_jobno) + 1)

        for i in range(count):
            new_row = base_row.copy(deep=True)
            new_row['RS_JobNo'] = start_jobno + i

            for col in base_row.index:
                val = base_row[col]

                if col in ['RS_Tube ID', 'RS_JobNo', 'DRIN_Step Name']:
                    continue

                elif col == 'DRIN_Step Time' and pd.api.types.is_numeric_dtype(type(val)):
                    delta = int(val * 0.05)
                    offset = i / 5
                    delta = max(delta, 1)
                    new_val = np.random.randint(val - delta + offset, val + delta + offset + 1)
                    new_row[col] = int(new_val)

                elif pd.api.types.is_numeric_dtype(type(val)):
                    delta = int(val * 0.005)
                    offset = i / 10
                    delta = max(delta, 1)
                    new_val = np.random.randint(val - delta + offset, val + delta + offset + 1)
                    new_row[col] = int(new_val)

            dummy_rows.append(new_row.copy(deep=True))

        return pd.DataFrame(dummy_rows)


if __name__ == "__main__":
    receiver = FinsDataReceiver(ip="172.22.80.1", plc_port=9600, plc_node=1, pc_node=3)
    result = receiver.receive_all()
    if result:
        tube_id, job_id, data = result
        print("받은 데이터:", tube_id, job_id, data[:5], "...")
