from sklearn.model_selection import train_test_split
from sklearn.linear_model import LinearRegression
from sklearn.metrics import mean_squared_error

import pandas as pd

# FILE_PATH = r'C:\Users\202202773-NB\PycharmProjects\TunaGUI_QT\datasets\MERGE_dummy_data.csv'
#
# df = pd.read_csv(FILE_PATH)
def regressor(df :pd.DataFrame, zone :int):
    rs_zone_cols = df.columns[df.columns.str.contains(f'RS_ZONE{zone}', case=False)]
    step_time_cols = df.columns[df.columns.str.contains('DRIN_Step Time', case=False)]
    zone_sp_cols = df.columns[df.columns.str.contains(fr'ZONE{zone}\(SP\)', case=False)]

    input_cols = rs_zone_cols.union(step_time_cols).union(zone_sp_cols)
    df_zone = df[input_cols]

    X = df_zone.loc[:, df_zone.columns.str.contains('DRIN', case=False)]
    y = df_zone.loc[:, df_zone.columns.str.contains('RS', case=False)]
    print(X)
    print(y)

    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=5)
    model = LinearRegression()
    model.fit(X_train, y_train)

    y_test_predict = model.predict(X_test)

    mse = mean_squared_error(y_test, y_test_predict)

    print("Intercept (theta_0):", model.intercept_)
    print("Coefficients (theta_1~n):", model.coef_)
    print(f"RMSE: {mse**0.5}")

    return model.intercept_, model.coef_