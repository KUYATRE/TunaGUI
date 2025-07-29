from pathlib import Path
import pandas as pd
from services.data_processor import DataProcessor
from services.trigger_monitor import TriggerMonitor
from utils.ml_model import run_dual_regression
from PySide6.QtWidgets import QWidget, QVBoxLayout, QTableWidgetItem
from utils.theta_analyzer import ThetaAnalyzer
from utils.theta_plot_canvas import ThetaPlotCanvas
from utils.heater_regressor import HeaterRegressor
import logging

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

if not logger.hasHandlers():
    handler = logging.StreamHandler()
    formatter = logging.Formatter('[%(levelname)s] %(asctime)s - %(message)s')
    handler.setFormatter(formatter)
    logger.addHandler(handler)

class DashboardController:
    def __init__(self, table_widget, theta_table, theta_analyzer, parent: QWidget = None):
        self.table_widget = table_widget
        self.theta_table = theta_table
        self.theta_analyzer = theta_analyzer
        self.canvas = ThetaPlotCanvas(parent=parent)
        self.trigger_monitor = None

        self.last_tube_id = None
        self.last_job_id = None

        self.analyzer = ThetaAnalyzer()

    def display_dataframe(self, df: pd.DataFrame):
        self.table_widget.setRowCount(len(df))
        self.table_widget.setColumnCount(len(df.columns))
        self.table_widget.setHorizontalHeaderLabels(df.columns.tolist())

        for row in range(len(df)):
            for col in range(len(df.columns)):
                item = QTableWidgetItem(str(df.iat[row, col]))
                self.table_widget.setItem(row, col, item)

    def run_regression_and_plot(self, df: pd.DataFrame, zone: int):
        reg = HeaterRegressor()
        self.canvas.clear_plot()
        reg.run_and_plot(df, zone, canvas=self.canvas)

    def load_latest_merge_csv(self, base_dir: str, zone_number: int):
        base_path = Path(base_dir)
        merge_files = sorted(base_path.rglob("*MERGE*.csv"), key=lambda f: f.stat().st_mtime, reverse=True)
        if not merge_files:
            logger.warning("No MERGE CSV file found")
            return None, None

        latest_file = merge_files[0]
        df = pd.read_csv(latest_file)
        logger.info(f"[Load] {latest_file.name} loaded")
        logger.debug(f"Columns in loaded DataFrame: {df.columns.tolist()}")

        return df, zone_number

    def start_trigger_monitoring(self, fins_client):
        self.trigger_monitor = TriggerMonitor(
            fins_client=fins_client,
        )
        self.trigger_monitor.start()

    def update_plot(self, df, zone):
        X1, y1, model1, X2, y2, model2 = run_dual_regression(df, zone)
        self.canvas.plot_model_result(X1, y1, model1, label="Model1: StepTime")
        self.canvas.plot_model_result(X2, y2, model2, label="Model2: SP")

    def plot_theta_table(self, theta_df: pd.DataFrame):
        self.theta_table.setRowCount(len(theta_df))
        self.theta_table.setColumnCount(len(theta_df.columns))
        self.theta_table.setHorizontalHeaderLabels(theta_df.columns.tolist())

        for row in range(len(theta_df)):
            for col in range(len(theta_df.columns)):
                val = theta_df.iat[row, col]
                item = QTableWidgetItem(f"{val:.3f}" if isinstance(val, (int, float)) else str(val))
                self.theta_table.setItem(row, col, item)

    def load_and_analyze(self, filepath: str, zone: int):
        df = DataProcessor.load_merged_csv(path=filepath)
        self.analyzer.analyze_from_dataframe(df, zone)

    def plot_zone_model(self, df, zone):
        reg = HeaterRegressor()
        reg.run_and_plot(df, zone, canvas=self.canvas)

    def run_all_zone_analysis(self, base_dir: str, selected_zone: int):
        logger.info("Running full zone analysis from trigger")
        all_theta_rows = []

        for zone in range(2, 8):
            df, _ = self.load_latest_merge_csv(base_dir, zone)
            if df is None:
                continue

            if zone == selected_zone:
                self.display_dataframe(df)
                try:
                    self.run_regression_and_plot(df, zone)
                except Exception as e:
                    logger.exception(f"[ZONE {zone}] Regression plot error")

            self.analyzer.analyze_from_dataframe(df, zone)
            theta_df = self.analyzer.summarize_all()
            if not theta_df.empty:
                all_theta_rows.append(theta_df.iloc[-1])

        if all_theta_rows:
            final_theta_df = pd.DataFrame(all_theta_rows)
            self.plot_theta_table(final_theta_df)
