from pathlib import Path
import pandas as pd
from PySide6.QtWidgets import QWidget, QVBoxLayout, QTableWidgetItem
from utils.theta_analyzer import ThetaAnalyzer
from utils.theta_plot_canvas import ThetaPlotCanvas
from utils.heater_regressor import HeaterRegressor
from services.data_processor import DataProcessor
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

        self.processor = DataProcessor('0')

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
        try:
            reg = HeaterRegressor()
            self.canvas.clear_plot()
            reg.run_and_plot(df, zone, canvas=self.canvas)
        except ValueError as ve:
            logger.warning(f"Regression skipped for zone {zone}: {ve}")
            self.canvas.clear_plot()
            self.canvas.set_message(f"Zone {zone}: Not enough data for regression")
        except Exception as e:
            logger.error(f"Unexpected error during regression for zone {zone}: {e}", exc_info=True)
            self.canvas.clear_plot()
            self.canvas.set_message(f"Zone {zone}: 분석 중 오류 발생.")

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

    def plot_theta_table(self, theta_df: pd.DataFrame):
        self.theta_table.setRowCount(len(theta_df))
        self.theta_table.setColumnCount(len(theta_df.columns))
        self.theta_table.setHorizontalHeaderLabels(theta_df.columns.tolist())

        for row in range(len(theta_df)):
            for col in range(len(theta_df.columns)):
                val = theta_df.iat[row, col]
                item = QTableWidgetItem(f"{val:.3f}" if isinstance(val, (int, float)) else str(val))
                self.theta_table.setItem(row, col, item)

    def run_all_zone_analysis(self, base_dir: str, selected_zone: int):
        logger.debug("=======run_all_zone_analysis: start=======")
        all_theta_rows = []

        for zone in range(1, 9):
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
            logger.debug(f"[ZONE {zone}] theta_df: {theta_df}")

            if not theta_df.empty:
                all_theta_rows.append(theta_df.iloc[-1])

            self.last_tube_id = df['RS_Tube ID'].iloc[0]
            logger.debug(f"Tube ID: {self.last_tube_id}")

        if all_theta_rows:
            final_theta_df = pd.DataFrame(all_theta_rows)
            self.plot_theta_table(final_theta_df)

        if not theta_df.empty:
            return theta_df, self.last_tube_id
        else:
            logger.warning("Theta dataframe is empty: return NONE")
            return None

