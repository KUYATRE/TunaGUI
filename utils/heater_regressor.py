import pandas as pd
from utils.ml_model import run_dual_regression
from utils.theta_plot_canvas import ThetaPlotCanvas


class HeaterRegressor:
    def __init__(self):
        self.X1 = None
        self.y1 = None
        self.model1 = None
        self.X2 = None
        self.y2 = None
        self.model2 = None

    def run_and_plot(self, df: pd.DataFrame, zone: int, canvas: ThetaPlotCanvas):
        self.X1, self.y1, self.model1, self.X2, self.y2, self.model2 = run_dual_regression(df, zone)

        canvas.clear_plot()
        canvas.plot_model_result(self.X1, self.y1, self.model1, label=f"ZONE{zone}_STEP")
        canvas.plot_model_result(self.X2, self.y2, self.model2, label=f"ZONE{zone}_SP")
