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

def get_file(path):
    with open(path, 'r', encoding='utf-8') as f:
        reader = csv.reader(f)
        rows = []

        for row in reader:
            rows.append(row)

    #print(rows)
    return rows
"""
base directory 탐색
"""
def get_base_dir():
    if getattr(sys, 'frozen', False):
        base_dir = os.path.dirname(sys.executable)
        print(f".exe executed : {base_dir}")
    else:
        base_dir = os.path.dirname(os.path.realpath(__file__))
        print(f".py executed : {base_dir}")
    return base_dir

"""
dataset folder 탐색 및 생성
"""
def ensure_dataset_dir():
    base_dir = get_base_dir()
    dataset_dir = os.path.join(base_dir, 'datasets')

    if not os.path.isdir(dataset_dir):
        os.makedirs(dataset_dir)
        print(f"Created dataset directory : {dataset_dir}")
    else:
        print(f"Dataset directory already exists : {dataset_dir}")

    return dataset_dir

"""
TuningLog 폴더 datasets 폴더 내에서 탐색 및 생성
"""
def ensure_tuninglog_dir():
    dataset_dir = ensure_dataset_dir()
    tuninglog_dir = os.path.join(dataset_dir, 'TuningLog')

    if not os.path.exists(tuninglog_dir):
        os.makedirs(tuninglog_dir)
        print(f"Created TuningLog directory: {tuninglog_dir}")
    else:
        print(f"TuningLog directory already exists: {tuninglog_dir}")

    return tuninglog_dir

"""
RegressionLog 폴더 datasets 폴더 내에서 탐색 및 생성
"""
def ensure_regressionlog_dir():
    dataset_dir = ensure_dataset_dir()
    regressionlog_dir = os.path.join(dataset_dir, 'RegressionLog')

    if not os.path.exists(regressionlog_dir):
        os.makedirs(regressionlog_dir)
        print(f"Created RegressionLog directory: {regressionlog_dir}")
    else:
        print(f"RegressionLog directory already exists: {regressionlog_dir}")

    return regressionlog_dir

"""
TuningLog 폴더 내에 T{숫자} 폴더 탐색 및 생성
"""
def ensure_tuning_subdir(log_filename: str):
    tuninglog_dir = ensure_tuninglog_dir()

    # T폴더명 추출 (파일명 가장 앞의 'T숫자' 형식)
    base_name = os.path.basename(log_filename)
    t_folder_name = base_name.split('_')[0]

    # 예외 처리: 'T숫자' 형식이 아닌 경우
    if not t_folder_name.startswith('T') or not t_folder_name[1:].isdigit():
        raise ValueError(f"There's no accurate tube id in log file name: {log_filename}")

    t_folder_path = os.path.join(tuninglog_dir, t_folder_name)
    os.makedirs(t_folder_path, exist_ok=True)

    return t_folder_path

"""
RegressionLog 폴더 내에 T{숫자} 폴더 탐색 및 생성
"""
def ensure_regression_subdir(log_filename: str):
    regressionlog_dir = ensure_regressionlog_dir()

    # T폴더명 추출 (파일명 가장 앞의 'T숫자' 형식)
    base_name = os.path.basename(log_filename)
    t_folder_name = base_name.split('_')[0]

    # 예외 처리: 'T숫자' 형식이 아닌 경우
    if not t_folder_name.startswith('T') or not t_folder_name[1:].isdigit():
        raise ValueError(f"There's no accurate tube id in log file name: {log_filename}")

    t_folder_path = os.path.join(regressionlog_dir, t_folder_name)
    os.makedirs(t_folder_path, exist_ok=True)

    return t_folder_path

"""
Tuning log 찍기
"""
def save_tuning_parameter_rows(log_filename: str, tube_id, job_id,
                               p1_list, init_p2_list, adj_p2_list,
                               filename="tuning_parameters.csv"):

    folder_path = ensure_tuning_subdir(log_filename)
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    file_path = os.path.join(folder_path, filename)

    file_exists = os.path.exists(file_path)
    job_id_exists = False

    # 1. 파일이 존재하면 중복된 Job ID 있는지 확인
    if file_exists:
        with open(file_path, mode='r', newline='', encoding='utf-8') as f:
            reader = csv.reader(f)
            header = next(reader, None)  # 헤더 스킵
            for row in reader:
                if len(row) >= 3 and row[2] == str(job_id):
                    job_id_exists = True
                    break

    if job_id_exists:
        print(f"Job ID '{job_id}'already exist. row creation denied")
        return

    # 2. 파일에 새로 행 작성 (append 또는 새 파일 생성)
    with open(file_path, mode='a' if file_exists else 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)

        if not file_exists:
            # 헤더 작성
            writer.writerow(["Time", "Tube ID", "JobNo"]
                            + [f"ini_p2_Zone{i+1}" for i in range(len(init_p2_list))]
                            + [f"p1_Zone{i+1}" for i in range(len(p1_list))]
                            + [f"p2_Zone{i+1}" for i in range(len(adj_p2_list))])

        # 새 행 작성
        writer.writerow([timestamp, tube_id, job_id] + init_p2_list + p1_list + adj_p2_list)

    print(f"CSV log saved: {file_path}")

def get_any_data_from_column(data_rows: list, column_name : str):
    if not data_rows:
        raise ValueError("data_rows are empty")

    header = data_rows[0]
    if column_name not in header:
        raise ValueError(f"Column '{column_name}' not found")

    col_idx = header.index(column_name)

    for row in data_rows[1:]:  # 첫 행은 헤더, 이후부터 데이터
        if len(row) > col_idx:
            return row[col_idx]

    return None

def detect_heater_zones(headers):
    """
    CSV 헤더에서 ZONE(SP) 열 이름을 기준으로 존재하는 ZONE 수를 반환
    예: ZONE1(SP) ~ ZONE6(SP) → return 6
    """
    headers = [h.strip() for h in headers]
    zones = [h for h in headers if h.startswith("ZONE") and h.endswith("(SP)")]
    return len(zones)

def temp_data_scraping(cmode, rows):
    """
    Normal temperature : Recipe 온도 유지 구간 기준으로 분석(BCl3 기준 step name = 'Drive in')
    High temperatuere : Recipe 온도 유지 구간 기준으로 분석(BCl3 기준 step name = 'Dry-Ox')
    1. 설비군 별 Recipe 구성에 따라 조건 변경 필요
    2. 동적 분석 가능 하도록 코드 수정 필요
    """
    zone_count = detect_heater_zones(rows[0])

    max_data_ptc_zones = [0] * zone_count

    for index in range(len(rows[0])):
        if rows[0][index] == 'ZONE1(SP)':
            data_pos_sp = index
            break

    if cmode == 'normal':
        for index in range(len(rows)):
            if rows[index][3] == 'Drive in' and (float(rows[index][data_pos_sp]) >= 900):
                recipe_step = index
                break
    elif cmode == 'high':
        for index in range(len(rows)):
            if (rows[index][3] == 'Dry-Ox') and (float(rows[index][data_pos_sp]) >= 1000):
                recipe_step = index
                break

    set_point_zones = []
    for index in range(zone_count):
        set_point_zones.append(float(rows[recipe_step][data_pos_sp + index]))

    reading_stop_pos = recipe_step + 60

    for row_idx in range(recipe_step, reading_stop_pos):
        for zone_idx in range(zone_count):
            col_idx = data_pos_sp + (zone_count*2) + zone_idx
            value = float(rows[row_idx][col_idx])
            if value > max_data_ptc_zones[zone_idx]:
                max_data_ptc_zones[zone_idx] = value

    data_ctc_zones = []
    for index in range(zone_count):
        data_ctc_zones.append(float(rows[recipe_step + 120][data_pos_sp + index + zone_count]))

    retention_ptc_zones = []
    for index1 in range(zone_count):
        add = 0
        for index2 in range(recipe_step + 120, recipe_step + 180):
            add += float(rows[index2][data_pos_sp + index1 + (zone_count*2)])

        retention_ptc_zones.append(add / 60)


    return data_ctc_zones, retention_ptc_zones, max_data_ptc_zones, set_point_zones, recipe_step

def p_calculation(sp, rtn_ptc, ptc, ctc):
    """
    1. CTC < (SP - P2) : control 출력
    2. CTC >= (SP - P2) && PTC < (SP - P1) : control 출력
    3. CTC >= (SP - P2) && PTC >= (SP - P1) : MV limit  = 0
    4. 온도 유지 구간 PTC 최대 값과 SP의 차의 1/2 만큼을 P1 값으로 설정
    5. 온도 유지 구간 CTC = (SP - P2) 되도록 초기 P2 설정
    6. 온도 유지 구간 PTC 평균 값과 SP의 차 만큼을 P2 값으로 설정
    예시) p1 = 10, SP = 800, PTC = 790 유지 시 MV = 0 => p2 값을 감소 시켜 control 출력 내보내도록 조정 필요
    결론) 온도 유지 구간에 대하여 5번 항목 과 같이 초기 p2 값 지정 후 PTC 유지 온도 도달치 확인 하여 p2 조정
    """
    zone_count = len(sp)

    adjust_p1 = []
    for index in range(zone_count):
        if ptc[index] > sp[index] + 2:
            adjust_p1.append(int((ptc[index] - sp[index])/2))
            # print(f"{index + 1} Zone은 P1 조정이 필요합니다.")
        elif sp[index] <= ptc[index] <= sp[index] + 2:
            adjust_p1.append(0)
            # print(f"{index + 1} Zone은 P1 조정이 필요 없습니다.")
        else:
            adjust_p1.append(int((ptc[index] - sp[index])/2))
            # print(f"{index + 1} Zone의 Heater 출력 혹은 PTC 상태를 확인하십시오.")

    initial_p2 = []
    for index in range(zone_count):
        if ctc[index] > sp[index]:
            initial_p2.append(int(sp[index] - ctc[index]))
        elif ctc[index] <= sp[index]:
            initial_p2.append(int(sp[index] - ctc[index]))

    adjust_p2 = []
    for index in range(zone_count):
        if rtn_ptc[index] < sp[index]:
            adjust_p2.append(int(rtn_ptc[index] - sp[index]))
            # print(f"{index + 1} Zone은 P2 조정이 필요합니다.")
        elif rtn_ptc[index] == sp[index]:
            adjust_p2.append(0)
        else:
            adjust_p2.append(int(rtn_ptc[index] - sp[index]))
            # print(f"{index + 1} Zone은 P2 조정이 필요합니다.")

    return adjust_p1, initial_p2, adjust_p2

def consol_controller(temp_cmode, etype, rows):
    ctc_temp_data, rtn_ptc_temp_data, ptc_temp_data, zone_sp, recipe_step = temp_data_scraping(
        temp_cmode, rows)

    p1, initial_p2, p2 = p_calculation(zone_sp, rtn_ptc_temp_data,
                                                            ptc_temp_data, ctc_temp_data)

    formatted_rtn_ptc = [f"{data:.1f}" for data in rtn_ptc_temp_data]

    if etype == 'BCl3':
        etype_full = 'BCl3'
    elif etype == 'Annealing':
        etype_full = 'Annealing'
    elif etype == 'POCl3':
        etype_full = 'POCl3'
    elif etype == 'Oxidation':
        etype_full = 'Oxidation'
    else:
        etype_full = 'None'

    print(f"설비군 : {etype_full}")
    print(f"온도 컨트롤 모드 : {temp_cmode}")
    print(f"유지 구간 Temp set point : {zone_sp}")
    print(f"유지 구간 진입 120초 후 CTC 값 : {ctc_temp_data}")
    print(f"유지 구간 진입 120~180초 구간 PTC 평균 값 : {formatted_rtn_ptc}")
    print(f"유지 구간 진입 0~60초 구간 PTC 최대 값 : {ptc_temp_data}\n")
    print(f"우측 값대로 초기 P2 값이 입력되어 있는지 확인하십시오 : {initial_p2}")
    print(f"우측 값 만큼 현재 P1 값에 더하십시오 : {p1}")
    print(f"우측 값 만큼 현재 P2 값에 더하십시오 : {p2}")
    print("\n\n")

    return p1, initial_p2, p2, recipe_step

def extract_all_zones_all_series_limited(rows, recipe_step):
    """
    ZONE1~ZONE8의 SP/Spike/Profile 데이터 중
    recipe_step -120 ~ recipe_step +240 구간만 추출
    """
    zone_count = detect_heater_zones(rows[0])

    if not rows or len(rows) < 2:
        return {}

    headers = [h.strip() for h in rows[0]]
    zone_data = {}

    # 범위 계산
    start = max(1, recipe_step - 120)  # 최소 1 (헤더 제외)
    end = min(len(rows), recipe_step + 240)

    for i in range(1, zone_count+1):
        zone = f"ZONE{i}"
        try:
            sp_idx = headers.index(f"{zone}(SP)")
            spike_idx = headers.index(f"{zone}(Spike)")
            profile_idx = headers.index(f"{zone}(Profile)")

            x = list(range(start, end))
            sp = [float(rows[r][sp_idx]) if rows[r][sp_idx] else None for r in range(start, end)]
            spike = [float(rows[r][spike_idx]) if rows[r][spike_idx] else None for r in range(start, end)]
            profile = [float(rows[r][profile_idx]) if rows[r][profile_idx] else None for r in range(start, end)]

            zone_data[zone] = (x, sp, spike, profile)
        except ValueError:
            zone_data[zone] = ([], [], [], [])

    return zone_data
