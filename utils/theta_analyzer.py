import pandas as pd
import logging
from utils.ml_model import run_regression

logger = logging.getLogger(__name__)

class ThetaAnalyzer:
    def __init__(self):
        self.reset_table()
        self.tube_id = 0

    def reset_table(self):
        self.theta_table = pd.DataFrame(columns=["Zone", "Intercept", "coefficient1", "coefficient2", "coefficient3", "coefficient4", "coefficient5", "RMSE"])

    def add_result(self, zone_number, model, rmse):
        logger.debug(f"Adding regression result for ZONE{zone_number}")

        def extract(model):
            intercept = model.intercept_[0] if hasattr(model.intercept_, '__iter__') else model.intercept_
            coefs = model.coef_[0] if hasattr(model.coef_, '__iter__') else model.coef_
            return intercept, coefs

        intercept, coef_values = extract(model)
        row = {
            "Zone": f"ZONE{zone_number}",
            "Intercept": intercept
        }
        for i in range(min(5, len(coef_values))):
            row[f"coefficient{i+1}"] = coef_values[i]

        row["RMSE"] = rmse

        self.theta_table = pd.concat([self.theta_table, pd.DataFrame([row])], ignore_index=True)

    def summarize_all(self):
        logger.debug("Summarizing all theta results")
        if self.theta_table.empty:
            logger.warning("Theta dataframe is empty")
        else:
            logger.debug(f"Theta dataframe shape: {self.theta_table.shape}")
        return self.theta_table

    def analyze_from_dataframe(self, df: pd.DataFrame, zone: int):
        try:
            logger.debug(f"Analyzing zone {zone} from dataframe with shape: {df.shape}")
            X, y, model, rmse = run_regression(df, zone)
            self.add_result(zone, model, rmse)
        except Exception as e:
            logger.exception(f"Exception during analyzing zone {zone}: {e}")


# === 사용 예시 ===
if __name__ == "__main__":
    from services.log_analyzer import load_merged_csv

    df = load_merged_csv("datasets/MERGE_dummy_data.csv")
    analyzer = ThetaAnalyzer()
    analyzer.reset_table()
    for zone in range(2, 8):
        analyzer.analyze_from_dataframe(df, zone=zone)
    print(analyzer.summarize_all())
