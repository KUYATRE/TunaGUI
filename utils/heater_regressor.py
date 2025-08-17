import pandas as pd
from utils.ml_model import run_regression
from utils.theta_plot_canvas import ThetaPlotCanvas


class HeaterRegressor:
    def __init__(self):
        self.X = None
        self.y = None
        self.model = None
        # self.X2 = None
        # self.y2 = None
        # self.model2 = None

    def run_and_plot(self, df: pd.DataFrame, zone: int, canvas: ThetaPlotCanvas):
        self.X, self.y, self.model = run_regression(df, zone)

        canvas.clear_plot()
        canvas.plot_model_result(self.X, self.y, self.model, label=f"ZONE{zone}_STEP")
        # canvas.plot_model_result(self.X2, self.y2, self.model2, label=f"ZONE{zone}_SP")
