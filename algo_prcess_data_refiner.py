from pandas import Series

from algo_fins_comm import FinsUDPClient
from algo_logAnalyser import ensure_dataset_dir, ensure_learndata_subdir
from datetime import datetime
import os
import glob
import pandas as pd
import numpy as np


class DataProcessor:
    def __init__(self, filepath: str):
        self.filepath = filepath
        self.dataframe = None
        self.encoding = 'utf-8'

        self.read_available_bit_area = 0xA0
        self.read_available_word = 0
        self.read_available_bit = 3

        self.data_read_available = 0

        self.tube_id = 0
        self.job_id = 0
        self.log_file_dir = ensure_dataset_dir()
        self.base_dir = ensure_dataset_dir()

    def load_csv_to_dataframe(self):
        try:
            # job_id 기반으로 경로 내 CSV 파일 탐색
            search_pattern = f"*_{self.job_id}_*.csv"
            full_pattern = os.path.join(self.log_file_dir, search_pattern)
            matched_files = glob.glob(full_pattern)

            if not matched_files:
                raise FileNotFoundError(f"{self.job_id}를 포함하는 CSV 파일을 찾을 수 없습니다.")

            # 일치하는 파일 중 가장 최신 파일 선택
            matched_file = max(matched_files, key=os.path.getmtime)
            self.filepath = matched_file

            # 파일 로드
            self.dataframe = pd.read_csv(self.filepath, encoding=self.encoding)
            self.dataframe.columns = [col.strip() for col in self.dataframe.columns]
            print(f"파일 로드 성공: {self.filepath}")
            return self.dataframe

        except Exception as e:
            print(f"파일 로드 실패: {e}")
            return pd.DataFrame()

    def strip_process_dataframe(self):
        columns_to_keep = [
            'Step Name', 'Tube ID', 'JobNo',
            'ZONE1(SP)', 'ZONE2(SP)', 'ZONE3(SP)', 'ZONE4(SP)', 'ZONE5(SP)', 'ZONE6(SP)', 'ZONE7(SP)', 'ZONE8(SP)'
        ]
        self.dataframe = self.dataframe[columns_to_keep]
        self.dataframe = self.dataframe[self.dataframe['Step Name']=='Drive in']

        # Step Name, Tube ID, JobNo 제외한 숫자열만 평균 계산
        numeric_cols = [col for col in self.dataframe.columns if col not in ['Step Name', 'Tube ID', 'JobNo']]
        mean_series = self.dataframe[numeric_cols].mean(numeric_only=True)

        # Step Name, Tube ID, JobNo 한 행에서 추출
        step_name = self.dataframe.iloc[0]['Step Name'] if not self.dataframe.empty else ''
        tube_id = self.dataframe.iloc[0]['Tube ID'] if not self.dataframe.empty else ''
        job_id = self.dataframe.iloc[0]['JobNo'] if not self.dataframe.empty else ''
        step_time = len(self.dataframe)

        # 평균값 시리즈에 Step Name, Tube ID, JobNo 추가
        mean_row = mean_series.to_dict()
        mean_row['Step Name'] = step_name
        mean_row['Tube ID'] = tube_id
        mean_row['JobNo'] = job_id
        mean_row['Step Time'] = step_time

        # 열 순서를 맞추기 위해 다시 정렬
        final_columns = ['Step Name', 'Step Time', 'Tube ID', 'JobNo'] + numeric_cols
        mean_df = pd.DataFrame([mean_row])[final_columns]

        # CSV 파일 저장
        tube_fullname = f"T{tube_id}"
        sub_dir = ensure_learndata_subdir(tube_fullname)
        output_path = self.generate_output_path(tube_id, self.job_id, base_dir=sub_dir, process_data=1)
        mean_df.to_csv(output_path, index=False, encoding='utf-8-sig')
        print(f"CSV 저장 완료: {output_path}")

        return mean_df

    """
    면저항 데이터 수량 변경으로 아래 함수 수정 필요 -> Sub boat 1ea 당 9point 측정 컨셉
    """
    def strip_sheet_res_dataframe(self, tube_id, job_id, sheet_res_data):
        # 데이터 유효성 체크
        if sheet_res_data is None or len(sheet_res_data) != 99:
            print("Data length error: Word length is not 99!")
            return

            # 99개 → 11개의 SubBoat, 각 SubBoat 당 9개 워드
        zone_matrix = [sheet_res_data[i:i + 9] for i in range(0, 99, 9)]
        print("Sheet resistance data strip proceeding...")

        # SubBoat별 컬럼 생성
        df = pd.DataFrame({f'SubBoat{i + 1}': zone_matrix[i] for i in range(11)})
        print("SubBoat columns generated")

        # ZONE ↔ SubBoat 매핑
        rs_target_mapping = {
            'ZONE2': ['SubBoat1', 'SubBoat2'],
            'ZONE3': ['SubBoat3', 'SubBoat4'],
            'ZONE4': ['SubBoat5', 'SubBoat6'],
            'ZONE5': ['SubBoat7'],
            'ZONE6': ['SubBoat8', 'SubBoat9'],
            'ZONE7': ['SubBoat10', 'SubBoat11'],
        }

        # 평균 계산
        zone_avg = {}
        for zone, boats in rs_target_mapping.items():
            zone_avg[zone] = df[boats].mean(axis=1).mean()  # 전체 평균

        # 결과 딕셔너리 구성
        zone_avg['Tube ID'] = tube_id
        zone_avg['JobNo'] = job_id

        # 컬럼 순서 지정
        final_columns = ['Tube ID', 'JobNo'] + list(rs_target_mapping.keys())
        result_df = pd.DataFrame([zone_avg])[final_columns]

        # CSV로 저장
        output_path = self.generate_output_path(tube_id, job_id, base_dir=ensure_learndata_subdir(f"T{tube_id}"))
        result_df.to_csv(output_path, index=False, encoding='utf-8-sig')
        print(f"Mean CSV file save complete: {output_path}")

        return result_df

    def merge_two_csv(self, tube_id: str, job_id: str) -> pd.DataFrame:
        try:

            # 하위 폴더 경로
            tube_fullname = f"T{tube_id}"
            sub_dir = ensure_learndata_subdir(tube_fullname)

            # RSHEET 및 PROC 패턴 파일 찾기
            rsheet_pattern = os.path.join(sub_dir, f"T{tube_id}_{job_id}_RSHEET_*.csv")
            proc_pattern = os.path.join(sub_dir, f"T{tube_id}_{job_id}_PROC_*.csv")

            rsheet_files = glob.glob(rsheet_pattern)
            proc_files = glob.glob(proc_pattern)

            if not rsheet_files or not proc_files:
                print("Can't find RSHEET files or PROC files")
                return pd.DataFrame()

            # 최신 파일 선택
            csv_path1 = max(rsheet_files, key=os.path.getmtime)
            csv_path2 = max(proc_files, key=os.path.getmtime)

            # CSV 로딩
            df1 = pd.read_csv(csv_path1)
            df2 = pd.read_csv(csv_path2)

            # 인덱스 초기화
            df1.reset_index(drop=True, inplace=True)
            df2.reset_index(drop=True, inplace=True)

            # 열 이름 충돌 방지 (선택: 접두사 추가)
            df1 = df1.add_prefix("RS_")
            df2 = df2.add_prefix("DRIN_")

            # 중복 컬럼 제거: 예) Tube ID, JobNo가 양쪽에 다 있을 때 한쪽 제거
            for col in ['DRIN_Tube ID', 'DRIN_JobNo']:
                if col in df2.columns:
                    df2.drop(columns=[col], inplace=True)

            # 열 방향으로 병합
            merged_df = pd.concat([df1, df2], axis=1)

            return self.append_to_merge_csv(merged_df, tube_id, job_id)

        except Exception as e:
            print(f"병합 실패: {e}")
            return pd.DataFrame()

    def append_to_merge_csv(self, new_merged_df: pd.DataFrame, tube_id: str, job_id: str) -> pd.DataFrame:
        try:
            sub_dir = ensure_learndata_subdir(f"T{tube_id}")

            merge_pattern = os.path.join(sub_dir, f"T{tube_id}_MERGE_*.csv")
            existing_merge_files = glob.glob(merge_pattern)

            if existing_merge_files:
                latest_merge = max(existing_merge_files, key=os.path.getmtime)
                existing_df = pd.read_csv(latest_merge)

                combined_df = pd.concat([existing_df, new_merged_df], ignore_index=True)

                if "RS_Tube ID" in combined_df.columns and "RS_JobNo" in combined_df.columns:
                    combined_df.drop_duplicates(subset=["RS_Tube ID", "RS_JobNo"], keep='last', inplace=True)
                else:
                    print("No duplication found: new row added to learning data")

            else:
                combined_df = new_merged_df

            # 항상 새로운 파일명 생성
            output_path = self.generate_output_path(tube_id, job_id, base_dir=ensure_learndata_subdir(f"T{tube_id}"), process_data=2)
            combined_df.to_csv(output_path, index=False, encoding='utf-8-sig')
            print(f"MERGE file renewal completed → {output_path}")

            # 기존 MERGE 파일 삭제 (구버전 제거)
            for old_file in existing_merge_files:
                if old_file != output_path:
                    try:
                        os.remove(old_file)
                    except Exception as e:
                        print(f"Old merge file delete fail: {old_file} → {e}")

            return combined_df

        except Exception as e:
            print(f"MERGE append fail: {e}")
            return new_merged_df

    def find_latest_file(self, tube_id: str, job_no: str, pattern_type: str = "RSHEET") -> str:
        """
        base_dir에서 주어진 패턴의 가장 최신 CSV 파일 경로 반환
        pattern_type: RSHEET, PROC, MERGE 등
        """
        search_pattern = f"T{tube_id}_{job_no}_{pattern_type}_*.csv"
        full_pattern = os.path.join(self.base_dir, search_pattern)

        matched_files = glob.glob(full_pattern)

        if not matched_files:
            print(f"No file: {search_pattern}")
            return None

        # 파일 생성 시간 기준으로 정렬하여 최신 파일 선택
        latest_file = max(matched_files, key=os.path.getmtime)
        return latest_file

    def generate_output_path(self, tube_id: str, job_no: str, base_dir: str, process_data=0) -> str:
        tube_id = str(tube_id)
        job_no = str(job_no)

        now = datetime.now()
        timestamp = now.strftime("%Y%m%d_%H%M%S")  # 날짜_시간 형식

        # tube_id 별 하위 폴더 생성
        tube_dir = base_dir
        os.makedirs(tube_dir, exist_ok=True)

        # 파일명 구성
        if process_data == 0:
            filename = f"T{tube_id}_{job_no}_RSHEET_{timestamp}.csv"
        elif process_data == 1:
            filename = f"T{tube_id}_{job_no}_PROC_{timestamp}.csv"
        elif process_data == 2:
            filename = f"T{tube_id}_MERGE_{timestamp}.csv"
        else:
            filename = f"T{tube_id}_{job_no}_NULL_{timestamp}.csv"

        # tube_id 하위 폴더에 저장
        return os.path.join(tube_dir, filename)

    """
    FINS UDP DATA IN/OUT PROCESS
    """
    def data_receive(self, ip, plc_port, plc_node, pc_node, available_bit):
        fins = FinsUDPClient(plc_ip=ip, plc_port=plc_port, plc_node=plc_node, pc_node=pc_node)
        self.data_read_available = available_bit
        bit_startup = fins.read_word_bit(mem_area=0xA0, word_addr=0, bit_offset=2)

        if self.data_read_available:
            self.tube_id = fins.read_word(mem_area=0xA2, word_addr=0)
            self.job_id = fins.read_word(mem_area=0xA2, word_addr=1)
            if not bit_startup:
                sheet_res_data = fins.read_word(mem_area=0xA2, word_addr=2, word_count=99)
            else:
                startup = OnlyUseInStartUp()
                sheet_res_data = startup.generate_random_array(200,205, 99, float)

            return self.tube_id, self.job_id, sheet_res_data
        else:
            return None


"""
Only for startup
"""
class OnlyUseInStartUp:

    def generate_random_array(self, start: float, end: float, size: int, dtype=float) -> np.ndarray:
        print("시운전 기능: 면저항 데이터 난수 출력")
        if dtype == int:
            return np.random.randint(start, end+1, size=size)
        else:
            return np.random.uniform(start, end, size=size)

    @staticmethod
    def generate_dummy_from_base(base_row: pd.Series, num_rows: int = 10, start_jobno: int = None) -> pd.DataFrame:
        dummy_rows = []

        base_jobno = base_row['RS_JobNo']
        print(f"기준 JobNo: {base_jobno}")
        if start_jobno is None:
            start_jobno = int(base_jobno) + 1

        for i in range(num_rows):
            # 반드시 deep copy로 새로운 인스턴스 생성
            new_row = base_row.copy(deep=True)

            # JobNo 자동 증가
            new_jobno = start_jobno + i
            new_row['RS_JobNo'] = new_jobno

            print(f"--- Row {i + 1} ---")
            print(f"생성된 JobNo: {new_jobno}")

            for col in base_row.index:
                val = base_row[col]

                if col in ['RS_Tube ID', 'RS_JobNo', 'DRIN_Step Name']:
                    continue

                elif col == 'DRIN_Step Time' and pd.api.types.is_numeric_dtype(type(val)):
                    delta = int(val * 0.05)
                    offset = i / 5
                    if delta == 0: delta = 1  # 최소 1 보장
                    new_val = np.random.randint(val - delta + offset, val + delta + offset + 1)
                    new_row[col] = int(new_val)
                    print(f"Step Time 변경: {val} → {new_val}")

                elif pd.api.types.is_numeric_dtype(type(val)):
                    delta = int(val * 0.005)
                    offset = i/10
                    if delta == 0: delta = 1
                    new_val = np.random.randint(val - delta + offset, val + delta + offset + 1)
                    new_row[col] = int(new_val)

            # 새로운 row는 완전히 복사하여 리스트에 저장 (덮어쓰기 방지)
            dummy_rows.append(new_row.copy(deep=True))

        return pd.DataFrame(dummy_rows)



if __name__ == "__main__":
    startup = OnlyUseInStartUp()
    dataframe = pd.read_csv(r"C:\Users\202202773-NB\PycharmProjects\TunaGUI_QT\datasets\13\T13_MERGE_20250717_082549.csv")
    dummy_df = startup.generate_dummy_from_base(base_row=dataframe.iloc[0], num_rows=500)
    dummy_df.to_csv("datasets/MERGE_dummy_data.csv", index=False)


