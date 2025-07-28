from sklearn.model_selection import train_test_split
from sklearn.linear_model import LinearRegression
from sklearn.metrics import mean_squared_error

import pandas as pd

# FILE_PATH = r'C:\Users\202202773-NB\PycharmProjects\TunaGUI_QT\datasets\MERGE_dummy_data.csv'
#
# df = pd.read_csv(FILE_PATH)
def regressor(df :pd.DataFrame, zone :int):
    if zone == 1:
        target_zone = 1
    elif zone == 8:
        target_zone = 7
    else:
        target_zone = zone
    rs_zone_cols = df.columns[df.columns.str.contains(f'RS_ZONE{target_zone}', case=False)]
    step_time_cols = df.columns[df.columns.str.contains('DRIN_Step Time', case=False)]
    zone_sp_cols = df.columns[df.columns.str.contains(fr'ZONE{target_zone}\(SP\)', case=False)]

    input_cols1 = rs_zone_cols.union(step_time_cols)
    input_cols2 = rs_zone_cols.union(zone_sp_cols)
    df_zone1 = df[input_cols1]
    df_zone2 = df[input_cols2]

    X1 = df_zone1.loc[:, df_zone1.columns.str.contains('DRIN', case=False)]
    y1 = df_zone1.loc[:, df_zone1.columns.str.contains('RS', case=False)]
    print(X1)
    print(y1)

    X1_train, X1_test, y1_train, y1_test = train_test_split(X1, y1, test_size=0.2, random_state=5)
    model1 = LinearRegression()
    model1.fit(X1_train, y1_train)

    y1_test_predict = model1.predict(X1_test)

    mse1 = mean_squared_error(y1_test, y1_test_predict)
    print("==MODEL1 PARAMETERS==\n")
    print("Intercept (theta_0):", model1.intercept_)
    print("Coefficients (theta_1~n):", model1.coef_)
    print(f"RMSE: {mse1**0.5}")

    X2 = df_zone2.loc[:, df_zone2.columns.str.contains('DRIN', case=False)]
    y2 = df_zone2.loc[:, df_zone2.columns.str.contains('RS', case=False)]
    print(X2)
    print(y2)

    X2_train, X2_test, y2_train, y2_test = train_test_split(X2, y2, test_size=0.2, random_state=5)
    model2 = LinearRegression()
    model2.fit(X2_train, y2_train)

    y2_test_predict = model2.predict(X2_test)

    mse2 = mean_squared_error(y2_test, y2_test_predict)
    print("==MODEL2 PARAMETERS==\n")
    print("Intercept (theta_0):", model1.intercept_)
    print("Coefficients (theta_1~n):", model1.coef_)
    print(f"RMSE: {mse2 ** 0.5}")

    return X1 ,y1, X2, y2, model1.intercept_, model1.coef_, model2.intercept_, model2.coef_