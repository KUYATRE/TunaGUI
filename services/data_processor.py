import os
import glob
import pandas as pd
import numpy as np
from datetime import datetime
from typing import Optional
from services.log_analyzer import ensure_dataset_dir, ensure_learndata_subdir
from services.fins_comm import FinsUDPClient
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
        df = self.load_csv()

        if df is None:
            raise ValueError("DataFrame이 비어있음")

        df = df[df['Step Name'] == 'Drive in']
        logger.debug(f"Drive in 필터 후 row 수: {len(df)}")

        if df.empty:
            raise ValueError("Drive in 단계가 존재하지 않음")

        # 열 필터링: ZONE2~ZONE7 (SP) 만 추출
        import re
        zone_sp_pattern = re.compile(r"ZONE[2-7]\(SP\)")
        numeric_cols = [col for col in df.columns if
                        zone_sp_pattern.fullmatch(col) and pd.api.types.is_numeric_dtype(df[col])]
        logger.debug(f"선택된 ZONE(SP) 열: {numeric_cols}")

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
        sheet_res_data = fins_client.read_word(
            mem_area=0xA2,
            word_addr=0,
            word_count=99
        )
        logger.info("PLC 데이터 수신 완료")
        logger.debug(sheet_res_data)
        return sheet_res_data

    def save_sheet_resistance(self, sheet_data: list) -> pd.DataFrame:
        logger.debug("면저항 데이터 저장 시작")
        if len(sheet_data) != 99:
            logger.error("면저항 데이터 길이 오류 (99 아님)")
            raise ValueError("면저항 데이터 길이 오류 (99 아님)")

        matrix = [sheet_data[i:i + 9] for i in range(0, 99, 9)]
        df = pd.DataFrame({f'SubBoat{i + 1}': matrix[i] for i in range(11)})

        mapping = {
            'ZONE2': ['SubBoat1', 'SubBoat2'],
            'ZONE3': ['SubBoat3', 'SubBoat4'],
            'ZONE4': ['SubBoat5', 'SubBoat6'],
            'ZONE5': ['SubBoat7'],
            'ZONE6': ['SubBoat8', 'SubBoat9'],
            'ZONE7': ['SubBoat10', 'SubBoat11']
        }

        zone_avg = {zone: df[subs].mean().mean() for zone, subs in mapping.items()}
        zone_avg.update({'Tube ID': self.tube_id, 'JobNo': self.job_id})

        out_df = pd.DataFrame([zone_avg])[['Tube ID', 'JobNo'] + list(mapping.keys())]
        path = self._output_path(self.tube_id, self.job_id, mode=0)
        out_df.to_csv(path, index=False, encoding='utf-8-sig')
        logger.info(f"RSHEET 평균값 저장됨: {path}")
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

    def _append_merge(self, new_df: pd.DataFrame) -> pd.DataFrame:
        tube = f"T{self.tube_id}"
        subdir = ensure_learndata_subdir(tube)
        pattern = os.path.join(subdir, f"{tube}_MERGE_*.csv")
        old_files = glob.glob(pattern)

        if old_files:
            latest = max(old_files, key=os.path.getmtime)
            old_df = pd.read_csv(latest)
            combined = pd.concat([old_df, new_df]).drop_duplicates(subset=["RS_Tube ID", "RS_JobNo"], keep='last')
            logger.debug(f"기존 MERGE 파일 병합: {latest}")
        else:
            combined = new_df
            logger.debug(f"신규 MERGE 파일 생성")

        path = self._output_path(self.tube_id, self.job_id, mode=2)
        combined.to_csv(path, index=False, encoding='utf-8-sig')
        logger.info(f"MERGE 파일 저장됨: {path}")

        for f in old_files:
            if f != path:
                os.remove(f)
                logger.debug(f"기존 MERGE 파일 삭제됨: {f}")
        return combined

    def _output_path(self, tube_id, job_id, mode=0):
        base = ensure_learndata_subdir(f"T{tube_id}")
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        suffix = ["RSHEET", "PROC", "MERGE", "NULL"][mode]
        path = os.path.join(base, f"T{tube_id}_{job_id}_{suffix}_{timestamp}.csv")
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
