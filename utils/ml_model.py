# ml_model.py
import pandas as pd
from sklearn.model_selection import train_test_split
from sklearn.linear_model import LinearRegression
from sklearn.metrics import mean_squared_error
from typing import Tuple
import numpy as np
import logging

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

handler = logging.StreamHandler()
formatter = logging.Formatter('[%(levelname)s] %(asctime)s - %(message)s')
handler.setFormatter(formatter)
logger.addHandler(handler)

def run_dual_regression(
    df: pd.DataFrame,
    zone: int
) -> Tuple[pd.DataFrame, pd.DataFrame, LinearRegression, pd.DataFrame, pd.DataFrame, LinearRegression]:
    """
    특정 ZONE에 대해 두 가지 입력 조합으로 회귀 분석 실행.

    Returns:
        X1, y1, model1: 첫 번째 조합 (Step Time 포함)
        X2, y2, model2: 두 번째 조합 (Set Point 포함)
    """
    logger.debug(f"Running regression for zone: {zone}")

    if zone == 1:
        target_zone = 2
    elif zone == 8:
        target_zone = 7
    else:
        target_zone = zone

    rs_zone_cols = df.columns[df.columns.str.contains(f'RS_ZONE{target_zone}', case=False)]
    step_time_cols = df.columns[df.columns.str.contains('DRIN_Time', case=False)]
    zone_sp_cols = df.columns[df.columns.str.contains(fr'ZONE{target_zone}\(SP\)', case=False)]

    logger.debug(f"RS_ZONE columns: {rs_zone_cols.tolist()}")
    logger.debug(f"Step Time columns: {step_time_cols.tolist()}")
    logger.debug(f"Set Point columns: {zone_sp_cols.tolist()}")

    input_cols1 = rs_zone_cols.union(step_time_cols)
    input_cols2 = rs_zone_cols.union(zone_sp_cols)

    X1 = df[input_cols1].loc[:, df[input_cols1].columns.str.contains('DRIN', case=False)]
    y1 = df[input_cols1].loc[:, df[input_cols1].columns.str.contains('RS', case=False)]
    X2 = df[input_cols2].loc[:, df[input_cols2].columns.str.contains('DRIN', case=False)]
    y2 = df[input_cols2].loc[:, df[input_cols2].columns.str.contains('RS', case=False)]

    logger.debug(f"X1 shape: {X1.shape}, y1 shape: {y1.shape}")
    logger.debug(f"X2 shape: {X2.shape}, y2 shape: {y2.shape}")

    if X1.empty or y1.empty or len(X1) < 10:
        raise ValueError(f"Not enough data to perform regression for model1 in zone {zone} (X1: {len(X1)}, y1: {len(y1)})")
    if X2.empty or y2.empty or len(X2) < 10:
        raise ValueError(f"Not enough data to perform regression for model2 in zone {zone} (X2: {len(X2)}, y2: {len(y2)})")

    X1_train, X1_test, y1_train, y1_test = train_test_split(X1, y1, test_size=0.2, random_state=5)
    model1 = LinearRegression().fit(X1_train, y1_train)
    X1_test_df = pd.DataFrame(X1_test, columns=X1.columns)
    y1_pred = model1.predict(X1_test_df)
    logger.info("[MODEL1] Intercept: %s", model1.intercept_)
    logger.info("[MODEL1] Coefficients: %s", model1.coef_)
    logger.info("[MODEL1] RMSE: %.4f", np.sqrt(mean_squared_error(y1_test, y1_pred)))

    X2_train, X2_test, y2_train, y2_test = train_test_split(X2, y2, test_size=0.2, random_state=5)
    model2 = LinearRegression().fit(X2_train, y2_train)
    X2_test_df = pd.DataFrame(X2_test, columns=X2.columns)
    y2_pred = model2.predict(X2_test_df)
    logger.info("[MODEL2] Intercept: %s", model2.intercept_)
    logger.info("[MODEL2] Coefficients: %s", model2.coef_)
    logger.info("[MODEL2] RMSE: %.4f", np.sqrt(mean_squared_error(y2_test, y2_pred)))

    return X1, y1, model1, X2, y2, model2

def run_regression(
    df: pd.DataFrame,
    zone: int
) -> Tuple[pd.DataFrame, pd.DataFrame, LinearRegression, mean_squared_error]:
    logger.debug(f"=======run_regression: Start=======")

    mapping = {
        'ZONE1': ['RS_SubBoat1', 'RS_SubBoat2'],
        'ZONE2': ['RS_SubBoat1', 'RS_SubBoat2', 'RS_SubBoat3', 'RS_SubBoat4'],
        'ZONE3': ['RS_SubBoat1', 'RS_SubBoat2', 'RS_SubBoat3', 'RS_SubBoat4', 'RS_SubBoat5'],
        'ZONE4': ['RS_SubBoat3', 'RS_SubBoat4', 'RS_SubBoat5', 'RS_SubBoat6', 'RS_SubBoat7'],
        'ZONE5': ['RS_SubBoat5', 'RS_SubBoat6', 'RS_SubBoat7', 'RS_SubBoat8', 'RS_SubBoat9'],
        'ZONE6': ['RS_SubBoat7', 'RS_SubBoat8', 'RS_SubBoat9', 'RS_SubBoat10', 'RS_SubBoat11'],
        'ZONE7': ['RS_SubBoat8', 'RS_SubBoat9', 'RS_SubBoat10', 'RS_SubBoat11'],
        'ZONE8': ['RS_SubBoat10', 'RS_SubBoat11'],
    }

    key = f"ZONE{zone}"
    logger.debug(f"ZONE{zone} selected")

    if key not in mapping:
        raise ValueError(f"ZONE {zone} not found in mapping")

    selected_cols: List[str] = mapping[key]
    rs_subboat_cols = [col for col in selected_cols if col in df.columns]
    drin_sp_cols = df.columns[df.columns.str.contains(f'DRIN_{key}', case=False)]

    X = df[rs_subboat_cols]
    y = df[drin_sp_cols]
    logger.debug(f"SubBoat Rsheet dataframe: {X.shape}")
    logger.debug(f"SubBoat Rsheet columns: {rs_subboat_cols}")
    logger.debug(f"Heater zone dataframe: {y.shape}")
    logger.debug(f"Heater zone columns: {drin_sp_cols}")

    if X.empty or y.empty or len(X) < 10:
        raise ValueError(
            f"Not enough data to perform regression for model1 in zone {zone} (X1: {len(X)}, y1: {len(y)})")

    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=5)
    model = LinearRegression().fit(X_train, y_train)
    y_pred = model.predict(X_test)
    mse = mean_squared_error(y_test, y_pred)
    rmse = mse ** 0.5

    logger.info(f"[MODEL{zone}] Intercept: %s", model.intercept_)
    logger.info(f"[MODEL{zone}] Coefficients: %s", model.coef_)
    logger.info(f"[MODEL{zone}] RMSE: %.4f", rmse)

    return X, y, model, rmse