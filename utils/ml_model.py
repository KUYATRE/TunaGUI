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
    step_time_cols = df.columns[df.columns.str.contains('DRIN_Step Time', case=False)]
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
