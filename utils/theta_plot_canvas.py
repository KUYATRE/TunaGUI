import logging
import numpy as np
import pandas as pd
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

class ThetaPlotCanvas(FigureCanvas):
    def __init__(self, parent=None, width=12, height=4, dpi=100):
        self.fig = Figure(figsize=(width, height), dpi=dpi)
        self.ax1 = self.fig.add_subplot(121)
        self.ax2 = self.fig.add_subplot(122)
        super().__init__(self.fig)
        self.setParent(parent)

    def clear_plot(self):
        self.ax1.clear()
        self.ax2.clear()
        self.draw()

    def set_message(self, message: str):
        self.ax1.clear()
        self.ax2.clear()
        self.ax1.text(0.5, 0.5, message, ha='center', va='center', fontsize=12)
        self.draw()

    def plot_model_result(self, X: pd.DataFrame, y: pd.DataFrame, model, label: str = "Model"):
        if X.shape[1] != 1:
            logger.warning(f"[WARNING] Cannot plot: input dimension is {X.shape[1]} (only 1D supported)")
            return

        logger.debug(f"Plotting model result for label: {label}")

        try:
            x_vals = X.iloc[:, 0].values.reshape(-1, 1)
            y_vals = y.values.reshape(-1, 1)

            logger.debug(f"x_vals shape: {x_vals.shape}, y_vals shape: {y_vals.shape}")

            sorted_indices = np.argsort(x_vals[:, 0])
            x_sorted = x_vals[sorted_indices]
            y_sorted = y_vals[sorted_indices]

            y_pred = model.predict(x_sorted)

            if "STEP" in label.upper():
                ax = self.ax1
                ax.set_title("Step Time Regression")
            elif "SP" in label.upper():
                ax = self.ax2
                ax.set_title("Set Point Regression")
            else:
                ax = self.ax1  # default to ax1

            ax.plot(x_sorted, y_sorted, 'o', label=f'{label} (Train)')
            ax.plot(x_sorted, y_pred, '-', label=f'{label} (Predict)')
            ax.set_xlabel(X.columns[0])
            ax.set_ylabel(y.columns[0] if hasattr(y, 'columns') else 'Output')
            ax.legend()
            self.draw()

            logger.debug(f"Plotting complete for {label}")

        except Exception as e:
            logger.error(f"Error during plotting model result for {label}: {e}")

    def plot_theta_table(self, theta_df: pd.DataFrame):
        logger.debug("Plotting theta table")
        self.ax1.clear()
        self.ax2.clear()

        if theta_df.empty:
            logger.warning("Theta dataframe is empty")
            self.ax1.text(0.5, 0.5, "No theta data", ha='center', va='center')
        else:
            self.ax1.axis('off')
            col_labels = list(theta_df.columns)
            row_labels = list(theta_df.index)
            # 안전하게 변환 (숫자만 포맷팅)
            cell_text = [
                [f"{val:.3f}" if isinstance(val, (int, float, np.number)) else str(val) for val in row]
                for row in theta_df.values
            ]
            table = self.ax1.table(
                cellText=cell_text,
                rowLabels=row_labels,
                colLabels=col_labels,
                loc='center'
            )
            table.auto_set_font_size(False)
            table.set_fontsize(10)
            table.scale(1.2, 1.2)

        self.draw()
        logger.debug("Theta table plot complete")