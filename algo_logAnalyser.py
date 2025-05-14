"""
1. Process log 탐색, log 파일 경로 지정 필요
2. Heater zone 900도 구간, 1000도 구간(hgih temp) 온도 data 분석
3. on/off 제어 파라미터 추천 값 return
4. 컴파일러 없이 동작할 수 있도록 pyinstaller를 통해 exe 생성할 것
"""
import csv

def get_file(path):
    with open(path, 'r', encoding='utf-8') as f:
        reader = csv.reader(f)
        rows = []

        for row in reader:
            rows.append(row)

    #print(rows)
    return rows

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
    Normal temperature : Recipe 온도 유지 구가나 기준으로 분석(BCl3 기준 step name = 'Drive in')
    High temperatuere : Recipe 온도 유지 구가나 기준으로 분석(BCl3 기준 step name = 'Dry-Ox')
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
