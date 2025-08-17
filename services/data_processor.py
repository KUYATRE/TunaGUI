import os
import glob
import pandas as pd
import numpy as np
from datetime import datetime
from typing import Optional
from services.log_analyzer import ensure_dataset_dir, ensure_learndata_subdir, ensure_regression_subdir
from services.fins_comm import FinsUDPClient
from utils.fins_data_receiver import FinsDataReceiver
import logging

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)
if not logger.hasHandlers():
    handler = logging.StreamHandler()
    formatter = logging.Formatter('[%(levelname)s] %(asctime)s - %(message)s')
    handler.setFormatter(formatter)
    logger.addHandler(handler)

class DataProcessor:
    def __init__(self, job_id: str):
        self.job_id = job_id
        self.tube_id = 0
        self.log_file_dir = ensure_dataset_dir()
        self.base_dir = ensure_dataset_dir()
        self.dataframe: Optional[pd.DataFrame] = None
        logger.debug(f"DataProcessor initialized with job_id={job_id}")

    def load_csv(self) -> pd.DataFrame:
        pattern = os.path.join(self.log_file_dir, f"*_{self.job_id}_*.csv")
        matched = glob.glob(pattern)
        logger.debug(f"CSV load pattern: {pattern}, matched files: {matched}")
        if not matched:
            logger.error(f"Job ID {self.job_id} 해당 파일 없음")
            raise FileNotFoundError(f"Job ID {self.job_id} 해당 파일 없음")
        filepath = max(matched, key=os.path.getmtime)
        logger.info(f"CSV 파일 로드됨: {filepath}")
        self.dataframe = pd.read_csv(filepath, encoding='utf-8')
        self.dataframe.columns = [c.strip() for c in self.dataframe.columns]
        return self.dataframe

    def extract_drivein_mean(self) -> pd.DataFrame:
        logger.debug(f"=======_extract_drivein_mean: Start=======")

        df = self.load_csv()

        if df is None:
            raise ValueError("DataFrame is empty")

        df = df[df['Step Name'] == 'Drive in']
        logger.debug(f"Drive in filtered row length: {len(df)}")

        if df.empty:
            raise ValueError("Drive in step deosn't exist")

        # 열 필터링: ZONE1~ZONE8 (SP) 추출
        import re
        zone_sp_pattern = re.compile(r"ZONE[1-8]\(SP\)")
        numeric_cols = [col for col in df.columns if
                        zone_sp_pattern.fullmatch(col) and pd.api.types.is_numeric_dtype(df[col])]
        logger.debug(f"Selected ZONE(SP) columns: {numeric_cols}")

        # 평균 계산
        mean_vals = df[numeric_cols].mean(numeric_only=True).to_dict()

        row_info = {
            'Step Name': df.iloc[0].get('Step Name', 'Drive in'),
            'Tube ID': df.iloc[0].get('Tube ID', 0),
            'JobNo': df.iloc[0].get('JobNo', 'UNKNOWN'),
            'Time': len(df)
        }
        mean_vals.update(row_info)

        final_cols = ['Step Name', 'Time', 'Tube ID', 'JobNo'] + numeric_cols
        out_df = pd.DataFrame([mean_vals])[final_cols]
        self.tube_id = row_info['Tube ID']

        path = self._output_path(self.tube_id, self.job_id, mode=1)
        out_df.to_csv(path, index=False, encoding='utf-8-sig')
        logger.info(f"PROC 평균값 저장됨: {path}")
        return out_df

    def data_receive_plc(self, fins_client: FinsUDPClient):
        logger.debug("PLC로부터 면저항 데이터 수신 요청")
        res_data_receiver = FinsDataReceiver(fins_client.plc_ip, fins_client.plc_port, fins_client.plc_node, fins_client.pc_node)
        tube_id, job_id, sheet_res_data = res_data_receiver.receive_all()
        logger.info("PLC 데이터 수신 완료")
        logger.debug(sheet_res_data)
        return tube_id, job_id, sheet_res_data

    def save_sheet_resistance(self, sheet_data: list) -> pd.DataFrame:
        logger.debug("=======_save_sheet_resistance: Start=======")
        if len(sheet_data) != 99:
            logger.error("Rsheet data length error (Not 99)")
            raise ValueError("Rsheet data length error (Not 99)")

        # 99개 데이터를 9개씩 끊어서 11개의 SubBoat로 구성
        matrix = [sheet_data[i:i + 9] for i in range(0, 99, 9)]
        df = pd.DataFrame({f'SubBoat{i + 1}': matrix[i] for i in range(11)})
        logger.debug(f"SubBoat Rsheet dataframe: \n{df}")

        # 각 SubBoat 평균 계산
        mean_series = df.mean(numeric_only=True)
        logger.debug(f"SubBoat Rsheet mean series1: \n{mean_series}")
        mean_series['Tube ID'] = self.tube_id
        mean_series['JobNo'] = self.job_id
        logger.debug(f"SubBoat Rsheet mean series2: \n{mean_series}")

        out_df = pd.DataFrame([mean_series])[['Tube ID', 'JobNo'] + [f'SubBoat{i + 1}' for i in range(11)]]
        logger.debug(f"SubBoat Rsheet dataframe: {out_df}")
        path = self._output_path(self.tube_id, self.job_id, mode=0)
        out_df.to_csv(path, index=False, encoding='utf-8-sig')
        logger.info(f"Rsheet mean data saved: {path}")
        return out_df

    def merge_files(self) -> pd.DataFrame:
        tube = f"T{self.tube_id}"
        subdir = ensure_learndata_subdir(tube)
        rsheet = max(glob.glob(os.path.join(subdir, f"{tube}_{self.job_id}_RSHEET_*.csv")), default=None, key=os.path.getmtime)
        proc = max(glob.glob(os.path.join(subdir, f"{tube}_{self.job_id}_PROC_*.csv")), default=None, key=os.path.getmtime)
        if not rsheet or not proc:
            logger.error("RSHEET 또는 PROC 파일 없음")
            raise FileNotFoundError("RSHEET 또는 PROC 파일 없음")

        df1 = pd.read_csv(rsheet).add_prefix("RS_")
        df2 = pd.read_csv(proc).add_prefix("DRIN_")
        df2.drop(columns=[c for c in ['DRIN_Tube ID', 'DRIN_JobNo'] if c in df2.columns], inplace=True)
        merged = pd.concat([df1, df2], axis=1)

        logger.info(f"RSHEET: {rsheet}, PROC: {proc} 파일 병합 완료")
        return self._append_merge(merged)

    def load_merged_csv(path: Optional[str] = None, tube_id: Optional[str] = None) -> pd.DataFrame:
        if path:
            logger.info(f"MERGE CSV 직접 경로 로드: {path}")
            return pd.read_csv(path, encoding='utf-8')

        if tube_id is None:
            raise ValueError("tube_id 또는 path 둘 중 하나는 반드시 제공해야 합니다.")

        base_dir = ensure_dataset_dir()
        subdir = os.path.join(base_dir, tube_id)
        pattern = os.path.join(subdir, f"{tube_id}_MERGE_*.csv")
        files = sorted(
            [f for f in glob.glob(pattern)],
            key=os.path.getmtime,
            reverse=True
        )
        if not files:
            logger.error(f"MERGE 파일을 찾을 수 없음: {pattern}")
            raise FileNotFoundError(f"MERGE 파일을 찾을 수 없음: {pattern}")

        logger.info(f"MERGE 파일 로드됨: {files[0]}")
        return pd.read_csv(files[0], encoding='utf-8')

    def save_regression_data(self, tube_id, df: pd.DataFrame) -> None:
        logger.debug("=======_save_regression_data: Start=======")
        path = self._output_path(tube_id, 0, mode=3)
        logger.debug(f"Regression file path: {path}")

        if df is None:
            logger.error("Theta dataframe is none: Save file rejected.")
            return

        if df.empty:
            logger.warning("Theta dataframe is empty: Save file rejected.")
            return

        df.to_csv(path, index=False, encoding='utf-8-sig')

    def _append_merge(self, new_df: pd.DataFrame) -> pd.DataFrame:
        tube = f"T{self.tube_id}"
        subdir = ensure_learndata_subdir(tube)
        pattern = os.path.join(subdir, f"{tube}_MERGE_*.csv")
        logger.debug(f"{tube}_MERGE_*.csv 파일 검색됨.")
        logger.debug(f"파일 경로: {pattern}")
        old_files = glob.glob(pattern)
        logger.debug(f"{old_files} = glob.glob({pattern})")

        if old_files:
            latest = max(old_files, key=os.path.getmtime)
            old_df = pd.read_csv(latest)

            # 병합
            combined = pd.concat([old_df, new_df])
            combined = combined.drop_duplicates(subset=["RS_Tube ID", "RS_JobNo"], keep='last')

            # 기존 MERGE 파일 위에 덮어쓰기
            path = latest
            logger.debug(f"기존 MERGE 파일 병합 및 덮어쓰기: {latest}")
        else:
            combined = new_df
            path = self._output_path(self.tube_id, self.job_id, mode=2)
            logger.debug(f"신규 MERGE 파일 생성: {path}")

        combined.to_csv(path, index=False, encoding='utf-8-sig')
        logger.info(f"MERGE 파일 저장됨: {path}")

        # 새로운 파일 외에는 모두 삭제
        for f in old_files:
            if f != path:
                os.remove(f)
                logger.debug(f"기존 MERGE 파일 삭제됨: {f}")

        return combined

    def _output_path(self, tube_id, job_id, mode=0):
        base = ensure_learndata_subdir(f"T{tube_id}")
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        suffix = ["RSHEET", "PROC", "MERGE", "THETA", "NULL"][mode]
        if mode != 2 and mode != 3:
            path = os.path.join(base, f"T{tube_id}_{job_id}_{suffix}_{timestamp}.csv")
        elif mode == 2:
            path = os.path.join(base, f"T{tube_id}_{suffix}_{timestamp}.csv")
        else:
            base = ensure_regression_subdir(f"T{tube_id}")
            path = os.path.join(base, f"T{tube_id}_{suffix}_{timestamp}.csv")

        logger.debug(f"Output 경로 생성됨: {path}")
        return path


class DummyDataGenerator:
    def generate(self, base_row: pd.Series, count=10, start_jobno=None) -> pd.DataFrame:
        logger.info(f"더미 데이터 {count}개 생성 시작")
        rows = []
        base_jobno = int(base_row['RS_JobNo'])
        for i in range(count):
            row = base_row.copy()
            row['RS_JobNo'] = start_jobno + i if start_jobno else base_jobno + i + 1
            for col in base_row.index:
                val = base_row[col]
                if col in ['RS_Tube ID', 'RS_JobNo', 'DRIN_Step Name']:
                    continue
                elif col == 'DRIN_Step Time' and pd.api.types.is_numeric_dtype(type(val)):
                    offset = i / 5
                    delta = max(1, int(val * 0.05))
                    row[col] = np.random.randint(val - delta + offset, val + delta + offset + 1)
                elif pd.api.types.is_numeric_dtype(type(val)):
                    offset = i / 10
                    delta = max(1, int(val * 0.005))
                    row[col] = np.random.randint(val - delta + offset, val + delta + offset + 1)
            rows.append(row.copy())
        logger.info("더미 데이터 생성 완료")
        return pd.DataFrame(rows)


if __name__ == "__main__":
    df = pd.read_csv("datasets/LearnDataLog/T13/T13_MERGE_20250717_082549.csv")
    dummy = DummyDataGenerator()
    df_dummy = dummy.generate(df.iloc[0], count=100)
    df_dummy.to_csv("datasets/MERGE_dummy_data.csv", index=False)
    logger.info("더미 데이터 CSV로 저장됨")
