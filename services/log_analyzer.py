"""
1. Process log 탐색, log 파일 경로 지정 필요
2. Heater zone 900도 구간, 1000도 구간(hgih temp) 온도 data 분석
3. on/off 제어 파라미터 추천 값 return
4. 컴파일러 없이 동작할 수 있도록 pyinstaller를 통해 exe 생성할 것
"""
import csv
import os
import sys
from datetime import datetime
from typing import List, Optional

# -----------------------------------------
# 경로 유틸
# -----------------------------------------
def get_base_dir() -> str:
    if getattr(sys, 'frozen', False):
        base_dir = os.path.dirname(sys.executable)
        print(f".exe executed : {base_dir}")
    else:
        base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
        print(f".py executed : {base_dir}")
    return base_dir

def ensure_dir(path: str) -> str:
    os.makedirs(path, exist_ok=True)
    return path

def ensure_dataset_dir() -> str:
    return ensure_dir(os.path.join(get_base_dir(), 'datasets'))

def ensure_subdir(parent_dir: str, log_filename: str) -> str:
    base_name = os.path.basename(log_filename)
    tube_id = base_name.split('_')[0]
    if not tube_id.startswith('T') or not tube_id[1:].isdigit():
        raise ValueError(f"Invalid tube id in file name: {log_filename}")
    return ensure_dir(os.path.join(parent_dir, tube_id))

def ensure_tuninglog_dir(): return ensure_dir(os.path.join(ensure_dataset_dir(), 'TuningLog'))
def ensure_regressionlog_dir(): return ensure_dir(os.path.join(ensure_dataset_dir(), 'RegressionLog'))
def ensure_learndatalog_dir(): return ensure_dir(os.path.join(ensure_dataset_dir(), 'LearnDataLog'))

def ensure_tuning_subdir(log_filename): return ensure_subdir(ensure_tuninglog_dir(), log_filename)
def ensure_regression_subdir(log_filename): return ensure_subdir(ensure_regressionlog_dir(), log_filename)
def ensure_learndata_subdir(log_filename): return ensure_subdir(ensure_learndatalog_dir(), log_filename)

# -----------------------------------------
# CSV 데이터 로드 및 추출
# -----------------------------------------
def get_file(path: str) -> List[List[str]]:
    with open(path, 'r', encoding='utf-8') as f:
        return list(csv.reader(f))

def get_any_data_from_column(data_rows: List[List[str]], column_name: str) -> Optional[str]:
    if not data_rows:
        raise ValueError("data_rows are empty")
    header = data_rows[0]
    if column_name not in header:
        raise ValueError(f"Column '{column_name}' not found")
    col_idx = header.index(column_name)
    for row in data_rows[1:]:
        if len(row) > col_idx:
            return row[col_idx]
    return None

# -----------------------------------------
# 튜닝 결과 저장
# -----------------------------------------
def save_tuning_parameter_rows(log_filename: str, tube_id: str, job_id: str,
                               p1_list: List[int], init_p2_list: List[int], adj_p2_list: List[int],
                               filename="tuning_parameters.csv") -> None:
    folder_path = ensure_tuning_subdir(log_filename)
    file_path = os.path.join(folder_path, filename)
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    file_exists = os.path.exists(file_path)
    job_id_exists = False

    if file_exists:
        with open(file_path, 'r', encoding='utf-8') as f:
            reader = csv.reader(f)
            next(reader, None)
            for row in reader:
                if len(row) >= 3 and row[2] == str(job_id):
                    job_id_exists = True
                    break

    if job_id_exists:
        print(f"Job ID '{job_id}' already exists. Row creation denied.")
        return

    with open(file_path, 'a' if file_exists else 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        if not file_exists:
            writer.writerow(["Time", "Tube ID", "JobNo"] +
                            [f"ini_p2_Zone{i+1}" for i in range(len(init_p2_list))] +
                            [f"p1_Zone{i+1}" for i in range(len(p1_list))] +
                            [f"p2_Zone{i+1}" for i in range(len(adj_p2_list))])
        writer.writerow([timestamp, tube_id, job_id] + init_p2_list + p1_list + adj_p2_list)
    print(f"CSV log saved: {file_path}")
