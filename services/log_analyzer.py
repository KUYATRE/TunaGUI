"""
1. Process log 탐색, log 파일 경로 지정 필요
2. Heater zone 900도 구간, 1000도 구간(hgih temp) 온도 data 분석
3. on/off 제어 파라미터 추천 값 return
4. 컴파일러 없이 동작할 수 있도록 pyinstaller를 통해 exe 생성할 것

*** Dashboard로부터 전달 받은 tuning data 기반으로 분석에 사용할 로그 자동 탐색 후 불러오기 기능 개발
"""
import csv
import os
import sys
import logging
from datetime import datetime
from typing import List, Optional

# 로거 설정
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

# 콘솔 핸들러 설정
console_handler = logging.StreamHandler()
console_handler.setLevel(logging.DEBUG)

# 로그 포맷 설정
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
console_handler.setFormatter(formatter)


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
    """
    로그 파일명에서 Tube 번호를 추출하여 해당 디렉토리를 생성합니다.
    파일명 형식: T13_* 또는 Tube13_*
    """
    try:
        # 입력값 검증 추가
        if not log_filename:
            raise ValueError("파일명이 비어있습니다.")
            
        base_name = os.path.basename(log_filename)
        parts = base_name.split('_')[0]

        # T13 또는 Tube13 형식 모두 처리
        if parts.startswith('T'):
            tube_id = parts
        elif parts.startswith('Tube'):
            tube_num = parts[4:]  # 'Tube' 제거
            tube_id = f'T{tube_num}'
        else:
            raise ValueError(f"파일명에서 Tube 번호를 찾을 수 없습니다: {log_filename}")

        # 숫자 부분이 있는지 확인
        if not any(c.isdigit() for c in tube_id):
            raise ValueError(f"Tube 번호에 숫자가 없습니다: {log_filename}")

        logger.debug(f"추출된 Tube ID: {tube_id}")
        return ensure_dir(os.path.join(parent_dir, tube_id))

    except Exception as e:
        logger.error(f"디렉토리 생성 중 오류 발생: {str(e)}")
        raise ValueError(f"Invalid tube id in file name: {log_filename}")


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

def extract_t_data(tuning_data):
    """
    튜닝 데이터에서 T 번호별로 데이터를 분류하여 추출
    
    Args:
        tuning_data (dict): 전체 튜닝 데이터
        
    Returns:
        dict: T 번호별로 분류된 데이터 사전
        예시 형태: {
            'T1': {'Z1': {...}, 'Z2': {...}, ...},
            'T2': {'Z1': {...}, 'Z2': {...}, ...},
            ...
        }
    """
    classified_data = {}
    
    for key in tuning_data.keys():
        if '_' in key:
            # T1_Z1 형식의 키를 분리
            t_num, zone = key.split('_')
            
            # t_num이 존재하지 않으면 새로운 사전 생성
            if t_num not in classified_data:
                classified_data[t_num] = {}
                
            # zone 데이터 저장
            classified_data[t_num][zone] = tuning_data[key]
    
    return classified_data

def find_latest_csv_by_classified_data(directory_path, classified_data):
    """
    classified_data의 키(예: T1, T2 등)를 기반으로 해당 패턴을 포함하는 
    가장 최신 CSV 파일을 찾습니다.
    
    Args:
        directory_path (str): 검색할 디렉토리 경로
        classified_data (dict): T 번호별로 분류된 데이터 사전
        
    Returns:
        dict: 각 T 번호별 최신 CSV 파일 경로
        예시: {'T1': 'path/to/T1_file.csv', 'T13': 'path/to/T13_file.csv'}
    """
    import os
    from datetime import datetime
    
    result = {}
    
    try:
        # classified_data의 각 키(T1, T2 등)에 대해 검색
        for t_number in classified_data.keys():
            # 디렉토리 내의 모든 CSV 파일 중 해당 T 번호를 포함하는 파일 검색
            csv_files = [f for f in os.listdir(directory_path) 
                        if f.endswith('.csv') and t_number in f]
            
            if csv_files:
                # 파일들을 생성 시간 기준으로 정렬
                csv_files.sort(key=lambda x: os.path.getmtime(
                    os.path.join(directory_path, x)), reverse=True)
                
                # 가장 최신 파일 경로 저장
                latest_file = os.path.join(directory_path, csv_files[0])
                result[t_number] = latest_file
                
                file_time = datetime.fromtimestamp(os.path.getmtime(latest_file))
                logger.info(f"{t_number}의 최신 CSV 파일 찾음: {latest_file}")
                logger.debug(f"파일 생성 시간: {file_time}")
            else:
                logger.warning(f"{t_number}를 포함하는 CSV 파일을 찾을 수 없습니다.")
                
        return result
        
    except Exception as e:
        logger.error(f"CSV 파일 검색 중 오류 발생: {str(e)}")
        return {}

def read_csv_by_classified_data(directory_path, classified_data):
    """
    classified_data의 키를 기반으로 해당하는 최신 CSV 파일들을 읽습니다.
    
    Args:
        directory_path (str): 검색할 디렉토리 경로
        classified_data (dict): T 번호별로 분류된 데이터 사전
        
    Returns:
        tuple: (데이터, 파일명)
            - 데이터: CSV 파일 내용 ([rows...])
            - 파일명: 읽은 CSV 파일의 전체 경로
    """
    try:
        # 최신 파일들의 경로 찾기
        latest_files = find_latest_csv_by_classified_data(directory_path, classified_data)
        
        # 각 파일 읽기
        result_data = None
        result_filename = None
        
        for t_number, file_path in latest_files.items():
            data = get_file(file_path)
            result_data = data
            result_filename = os.path.basename(file_path)
            logger.info(f"{t_number} CSV 파일 읽기 완료: {len(data)} 행")
            
        return result_data, result_filename
        
    except Exception as e:
        logger.error(f"CSV 파일 읽기 중 오류 발생: {str(e)}")
        return None, None