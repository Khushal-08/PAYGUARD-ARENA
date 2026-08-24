import shap
import pandas as pd
import xgboost as xgb
import pickle

class SHAPExplainer:
    def __init__(self, model_path: str):
        with open(model_path, 'rb') as f:
            self.model = pickle.load(f)
        
        # XGBoost models can be passed directly to TreeExplainer
        self.explainer = shap.TreeExplainer(self.model)
        
    def explain_instances(self, df: pd.DataFrame, feature_cols: list):
        """
        Calculates SHAP values for a given dataframe.
        Returns a dataframe of SHAP values matching the input index.
        """
        X = df[feature_cols]
        shap_values = self.explainer.shap_values(X)
        
        return pd.DataFrame(
            shap_values, 
            columns=[f"shap_{col}" for col in feature_cols],
            index=X.index
        )
        
    def get_global_importance(self, df: pd.DataFrame, feature_cols: list):
        """
        Returns average absolute SHAP values (global feature importance).
        """
        X = df[feature_cols]
        shap_values = self.explainer.shap_values(X)
        
        mean_abs_shap = pd.Series(np.abs(shap_values).mean(axis=0), index=feature_cols)
        return mean_abs_shap.sort_values(ascending=False)
