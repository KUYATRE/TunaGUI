import pandas as pd
import logging
from utils.ml_model import run_dual_regression

logger = logging.getLogger(__name__)

class ThetaAnalyzer:
    def __init__(self):
        self.reset_table()

    def reset_table(self):
        self.theta_table = pd.DataFrame(columns=["Zone", "intercept1", "coefficient1", "intercept2", "coefficient2"])

    def add_result(self, zone_number, X1, model1, X2, model2):
        logger.debug(f"Adding regression result for ZONE{zone_number}")

        def extract(model, X):
            intercept = model.intercept_[0] if hasattr(model.intercept_, '__iter__') else model.intercept_
            coefs = model.coef_[0] if hasattr(model.coef_, '__iter__') else model.coef_
            coef_dict = dict(zip(X.columns, coefs))
            return intercept, coef_dict

        intercept1, coefs1 = extract(model1, X1)
        intercept2, coefs2 = extract(model2, X2)

        row = {
            "Zone": f"ZONE{zone_number}",
            "intercept1": intercept1,
            "coefficient1": list(coefs1.values())[0] if coefs1 else None,
            "intercept2": intercept2,
            "coefficient2": list(coefs2.values())[0] if coefs2 else None,
        }

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
            X1, y1, model1, X2, y2, model2 = run_dual_regression(df, zone)
            self.add_result(zone, X1, model1, X2, model2)
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
