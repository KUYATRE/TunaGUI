# utils/heater_analysis.py

from typing import List, Tuple

def temp_data_scraping(cmode: str, rows: List[List[str]]) -> Tuple[List[float], List[float], List[float], List[float], int]:
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

    set_point_zones = [float(rows[recipe_step][data_pos_sp + i]) for i in range(zone_count)]
    reading_stop_pos = recipe_step + 60

    for row_idx in range(recipe_step, reading_stop_pos):
        for zone_idx in range(zone_count):
            col_idx = data_pos_sp + (zone_count * 2) + zone_idx
            value = float(rows[row_idx][col_idx])
            max_data_ptc_zones[zone_idx] = max(max_data_ptc_zones[zone_idx], value)

    data_ctc_zones = [float(rows[recipe_step + 120][data_pos_sp + i + zone_count]) for i in range(zone_count)]

    retention_ptc_zones = []
    for i in range(zone_count):
        add = sum(float(rows[j][data_pos_sp + i + (zone_count * 2)]) for j in range(recipe_step + 120, recipe_step + 180))
        retention_ptc_zones.append(add / 60)

    return data_ctc_zones, retention_ptc_zones, max_data_ptc_zones, set_point_zones, recipe_step

def p_calculation(sp: List[float], rtn_ptc: List[float], ptc: List[float], ctc: List[float]) -> Tuple[List[int], List[int], List[int]]:
    zone_count = len(sp)

    adjust_p1 = []
    for i in range(zone_count):
        delta = ptc[i] - sp[i]
        adjust_p1.append(int(delta / 2))

    initial_p2 = [int(sp[i] - ctc[i]) for i in range(zone_count)]
    adjust_p2 = [int(rtn_ptc[i] - sp[i]) for i in range(zone_count)]

    return adjust_p1, initial_p2, adjust_p2

def consol_controller(temp_cmode: str, etype: str, rows: List[List[str]]) -> Tuple[List[int], List[int], List[int], int]:
    ctc_temp_data, rtn_ptc_temp_data, ptc_temp_data, zone_sp, recipe_step = temp_data_scraping(temp_cmode, rows)
    p1, initial_p2, p2 = p_calculation(zone_sp, rtn_ptc_temp_data, ptc_temp_data, ctc_temp_data)

    print("\n[Heater Control Analysis Result]")
    print(f"설비군: {etype}")
    print(f"제어 모드: {temp_cmode}")
    print(f"SP: {zone_sp}")
    print(f"CTC: {ctc_temp_data}")
    print(f"PTC max(0~60s): {ptc_temp_data}")
    print(f"PTC avg(120~180s): {[f"{v:.1f}" for v in rtn_ptc_temp_data]}")
    print(f"초기 P2: {initial_p2}")
    print(f"조정 P1: {p1}")
    print(f"조정 P2: {p2}\n")

    return p1, initial_p2, p2, recipe_step

def detect_heater_zones(headers: List[str]) -> int:
    return sum(1 for h in headers if h.strip().startswith("ZONE") and h.strip().endswith("(SP)"))
