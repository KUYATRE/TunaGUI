# utils/plot_utils.py

from typing import List, Dict, Tuple

def extract_all_zones_all_series_limited(rows: List[List[str]], recipe_step: int) -> Dict[str, Tuple[List[int], List[float], List[float], List[float]]]:
    zone_count = detect_heater_zones(rows[0])
    if not rows or len(rows) < 2:
        return {}

    headers = [h.strip() for h in rows[0]]
    zone_data = {}

    start = max(1, recipe_step - 120)
    end = min(len(rows), recipe_step + 240)

    for i in range(1, zone_count + 1):
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

def detect_heater_zones(headers: List[str]) -> int:
    return sum(1 for h in headers if h.strip().startswith("ZONE") and h.strip().endswith("(SP)"))
