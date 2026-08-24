import os
import json
import pickle
import pandas as pd
import numpy as np
import xgboost as xgb
from datetime import datetime
from simulation.state.environment import PaymentEnvironment
from simulation.state.baseline_generator import LegitimateTrafficGenerator
from simulation.attacks.synthetic_identity import SyntheticIdentityAgent
from ml.features.entity_aggregates import engineer_all_entity_features
import google.generativeai as genai
from dotenv import load_dotenv
import time
from ml.train_baseline import split_chronological

load_dotenv()

def load_data():
    df = pd.read_csv("ml/data/simulated_baseline.csv")
    df['timestamp'] = pd.to_datetime(df['timestamp'])
    df = engineer_all_entity_features(df)
    df['hour_of_day'] = df['timestamp'].dt.hour
    df['day_of_week'] = df['timestamp'].dt.dayofweek
    df['is_fraud'] = (df['label'] == 'Fraud').astype(int)
    
    with open("ml/data/campaigns.json", "r") as f:
        campaigns = json.load(f)
        
    return df, campaigns

def evaluate_round(df, campaigns, model, features, round_num=1):
    # Filter to Synthetic Identity campaigns of this round
    syn_campaign_ids = [c["campaign_id"] for c in campaigns if c["attack_type"] == "Synthetic Identity" and c.get("round_id") == round_num]
    
    # Transactions in these campaigns that are fraud (bust-out)
    fraud_txns = df[(df['campaign_id'].isin(syn_campaign_ids)) & (df['is_fraud'] == 1)].copy()
    
    if len(fraud_txns) == 0:
        print("WARNING: No fraud transactions found in this round!")
        return 0.0, 0, len(syn_campaign_ids), 0.0, None, None
        
    X_fraud = fraud_txns[features].fillna(0)
    preds = model.predict_proba(X_fraud)[:, 1]
    fraud_txns['pred'] = preds
    
    # Assume a REVIEW/BLOCK threshold, e.g., 0.5
    threshold = 0.5
    
    # Detection is per-campaign: if ANY fraud transaction in the campaign is > threshold, it's caught
    fraud_txns['detected'] = fraud_txns['pred'] > threshold
    campaign_detection = fraud_txns.groupby('campaign_id')['detected'].max()
    
    detection_rate = campaign_detection.mean()
    detected_count = campaign_detection.sum()
    total_count = len(campaign_detection)
    
    detected_campaign_ids = campaign_detection[campaign_detection == True].index.tolist()
    detected_txns = fraud_txns[(fraud_txns['campaign_id'].isin(detected_campaign_ids)) & (fraud_txns['detected'] == True)]
    
    avg_bust_out_amt = fraud_txns['amount'].mean()
    
    # Calculate FPR (using legitimate transactions in df)
    legit_txns = df[df['is_fraud'] == 0].copy()
    if len(legit_txns) > 0:
        X_legit = legit_txns[features].fillna(0)
        legit_preds = model.predict_proba(X_legit)[:, 1]
        fpr = (legit_preds > threshold).mean()
        fp_count = (legit_preds > threshold).sum()
        total_legit = len(legit_txns)
    else:
        fpr = 0.0
        fp_count = 0
        total_legit = 0
        
    return detection_rate, detected_count, total_count, avg_bust_out_amt, fpr, fp_count, total_legit, detected_txns, X_fraud.loc[detected_txns.index]

def main():
    print("Loading data and model...")
    df, campaigns = load_data()
    
    model_path = "ml/models/xgboost_baseline_round_0.pkl"
    with open(model_path, "rb") as f:
        model = pickle.load(f)
        
    # The features used by Config 3 (excluding device_age_days)
    raw_features = ['amount', 'hour_of_day', 'day_of_week']
    agg_features = [
        'account_time_since_last_txn', 'is_new_account', 'account_txns_24h', 'account_txns_7d',
        'device_txns_7d', 'is_familiar_merchant'
    ]
    features = raw_features + agg_features
    
    # 1. Score Round 1 (On Test Split ONLY to be perfectly fair)
    print("\n--- Scoring Round 1 (Known Attack) on Test Set ---")
    df_train, df_val, df_test = split_chronological(df)
    r1_detection_rate, r1_caught, r1_total, r1_avg_amt, r1_fpr, r1_fp_count, r1_total_legit, detected_txns, X_detected = evaluate_round(df_test, campaigns, model, features, round_num=1)
    print(f"Round 1 Detection Rate: {r1_detection_rate:.2%} ({r1_caught}/{r1_total} campaigns)")
    print(f"Round 1 Avg Bust-out Amount: ${r1_avg_amt:.2f}")
    print(f"Round 0 Model FPR (Legit txns): {r1_fpr:.4%} ({r1_fp_count}/{r1_total_legit} false positives)")
    
    # 2. Extract SHAP (using feature importances on the detected rows as proxy, or true SHAP if possible)
    # Using XGBoost's pred_contribs to get SHAP values for the detected transactions
    print("\nExtracting SHAP top-feature values from DETECTED campaigns...")
    dmatrix = xgb.DMatrix(X_detected)
    shap_values = model.get_booster().predict(dmatrix, pred_contribs=True)
    
    # Average absolute SHAP value per feature
    mean_abs_shap = np.abs(shap_values[:, :-1]).mean(axis=0) # last column is bias
    shap_dict = dict(zip(features, mean_abs_shap))
    sorted_shap = sorted(shap_dict.items(), key=lambda x: x[1], reverse=True)
    
    for feat, val in sorted_shap[:3]:
        print(f"  {feat}: {val:.4f}")
        
    # 3. LLM Reasoning Step
    print("\n--- LLM Reasoning Step ---")
    llm_prompt = f"""
    You are the adaptive attacker. Your Round 1 Synthetic Identity campaigns had a {r1_detection_rate:.2%} detection rate.
    The defense caught you primarily using these top SHAP features (higher value means higher importance in detection):
    1. {sorted_shap[0][0]}: {sorted_shap[0][1]:.4f}
    2. {sorted_shap[1][0]}: {sorted_shap[1][1]:.4f}
    3. {sorted_shap[2][0]}: {sorted_shap[2][1]:.4f}
    
    Propose a concrete strategy mutation for Round 2 to evade detection.
    Specifically, provide 6 new parameters for the Synthetic Identity Agent:
    - seeding_count_loc (default 12, number of seeding txns)
    - seeding_delay_loc (default 36, hours)
    - drift_avg_amt_loc (default 250, dollars)
    - drift_delay_loc (default 8, hours)
    - fraud_avg_amt_loc (default 1500, dollars - note: cannot drop below 3x normal spending)
    - timing_strategy (string: "blend_peak", "off_peak", or "random")
    
    Also provide a 2-3 sentence explanation of your reasoning on why this specific SHAP signal implies that tweak.
    
    Return ONLY a raw valid JSON object with keys:
    - "seeding_count_loc" (number)
    - "seeding_delay_loc" (number)
    - "drift_avg_amt_loc" (number)
    - "drift_delay_loc" (number)
    - "fraud_avg_amt_loc" (number)
    - "timing_strategy" (string)
    - "reasoning" (string)
    Do not wrap the JSON in markdown blocks.
    """
    
    api_key = os.getenv("GEMINI_API_KEY")
    if api_key:
        print("Calling real Gemini API...")
        genai.configure(api_key=api_key)
        # Using gemini-3.6-flash as required by API
        model_name = "gemini-3.6-flash"
        llm = genai.GenerativeModel(model_name)
        
        # In Gemini, we can enforce JSON response with generation_config
        try:
            start_time = time.time()
            response = llm.generate_content(
                llm_prompt,
                generation_config=genai.types.GenerationConfig(
                    response_mime_type="application/json",
                    temperature=0.7,
                )
            )
            api_latency = time.time() - start_time
            print(f"API Call Latency: {api_latency:.2f} seconds")
            
            llm_output = response.text.strip()
            parsed_response = json.loads(llm_output)
            reasoning = parsed_response.get("reasoning", "No reasoning provided.")
            mutated_params = {
                'seeding_count_loc': parsed_response.get('seeding_count_loc', 24),
                'seeding_delay_loc': parsed_response.get('seeding_delay_loc', 72),
                'drift_avg_amt_loc': parsed_response.get('drift_avg_amt_loc', 75),
                'drift_delay_loc': parsed_response.get('drift_delay_loc', 24),
                'fraud_avg_amt_loc': parsed_response.get('fraud_avg_amt_loc', 150),
                'timing_strategy': parsed_response.get('timing_strategy', 'blend_peak')
            }
        except Exception as e:
            print(f"Failed to parse LLM response: {e}")
            try:
                print(f"Raw response: {response.text}")
            except:
                pass
            # Fallback if parsing fails
            reasoning = "Failed to parse response."
            mutated_params = {'seeding_count_loc': 24, 'seeding_delay_loc': 72, 'drift_avg_amt_loc': 75, 'drift_delay_loc': 24, 'fraud_avg_amt_loc': 150, 'timing_strategy': 'blend_peak'}
    else:
        print("[TEMPORARY_MOCK] GEMINI_API_KEY not found in .env. Using mock reasoning.")
        reasoning = f"The defense relies heavily on {sorted_shap[0][0]} and {sorted_shap[1][0]}. To evade this, we must build a much longer, denser legitimate history (increasing seeding count to 24), while simultaneously decreasing our cash-out amounts closer to the floor. Finally, to evade {sorted_shap[2][0]}, we will switch our timing strategy to 'blend_peak' to hide fraud within normal daytime volume."
        mutated_params = {
            'seeding_count_loc': 24,
            'seeding_delay_loc': 72,
            'drift_avg_amt_loc': 75,
            'drift_delay_loc': 24,
            'fraud_avg_amt_loc': 150,
            'timing_strategy': 'blend_peak'
        }
        
    print(f"\n[LLM THOUGHT PROCESS]\n{reasoning}")
    print(f"\nMutated Params for Round 2: {mutated_params}")
    
    # 4. Generate Round 2
    print("\n--- Generating Round 2 Campaigns (Adaptive Attack) ---")
    
    start_time = datetime(2026, 4, 1, 0, 0, 0)
    env = PaymentEnvironment(start_time=start_time)
    generator = LegitimateTrafficGenerator(env=env, num_users=1, num_merchants=500)
    generator.bootstrap_world()
    
    attack_agent = SyntheticIdentityAgent(env=env, round_id=2, strategy_params=mutated_params)
    
    r2_campaigns = []
    for _ in range(400):
        campaign = attack_agent.execute_campaign(start_time=start_time)
        r2_campaigns.append(campaign)
        
    # Process them into a dataframe
    r2_df = pd.DataFrame([txn.model_dump() for txn in env.transactions])
    r2_df['campaign_id'] = r2_df['campaign_id'].astype(str)
    r2_df['timestamp'] = pd.to_datetime(r2_df['timestamp'])
    r2_df = engineer_all_entity_features(r2_df)
    r2_df['hour_of_day'] = r2_df['timestamp'].dt.hour
    r2_df['day_of_week'] = r2_df['timestamp'].dt.dayofweek
    r2_df['is_fraud'] = (r2_df['label'] == 'Fraud').astype(int)
    
    # 5. Score Round 2
    print("\n--- Scoring Round 2 (Adaptive Attack) ---")
    # 5. Score Round 2 (evaluate on all 400 for comparison, but we will split for Round 3)
    print("\n--- Scoring Round 2 (Adaptive Attack) ---")
    r2_campaigns_json = [json.loads(c.model_dump_json()) for c in r2_campaigns]
    r2_detection_rate, r2_caught, r2_total, r2_avg_amt, r2_fpr, r2_fp_count, r2_total_legit, _, _ = evaluate_round(r2_df, r2_campaigns_json, model, features, round_num=2)
    
    print(f"Round 1 Detection Rate: {r1_detection_rate:.2%} ({r1_caught}/{r1_total} campaigns)")
    print(f"Round 2 Detection Rate (Mutated): {r2_detection_rate:.2%} ({r2_caught}/{r2_total} campaigns)")
    print(f"Round 1 Avg Bust-out Amount: ${r1_avg_amt:.2f}")
    print(f"Round 2 Avg Bust-out Amount: ${r2_avg_amt:.2f}")

    # 6. Retrain Defense (Round 3) with Contamination Control
    print("\n--- Retraining Defense (Round 3) ---")
    from sklearn.model_selection import train_test_split
    
    # Train/Test split: 80% train, 20% test for Round 2 campaigns
    r2_train_camps, r2_test_camps = train_test_split(r2_campaigns_json, test_size=0.2, random_state=42)
    r2_train_ids = [c['campaign_id'] for c in r2_train_camps]
    r2_test_ids = [c['campaign_id'] for c in r2_test_camps]
    
    # We train on Round 1 baseline data (Train Split ONLY) + Round 2 train data
    df_train, df_val, df_test = split_chronological(df)
    
    r2_train_df = r2_df[~r2_df['campaign_id'].isin(r2_test_ids)]
    
    # We need to construct a proper validation set from r2_df as well to prevent early stopping bias
    # But for simplicity, we'll just use df_val as the validation set.
    combined_train_df = pd.concat([df_train, r2_train_df], ignore_index=True)
    
    X_train = combined_train_df[features].fillna(0)
    y_train = combined_train_df['is_fraud']
    
    X_val = df_val[features].fillna(0)
    y_val = df_val['is_fraud']
    
    scale_weight = (len(y_train) - y_train.sum()) / max(1, y_train.sum())
    
    round_1_model = xgb.XGBClassifier(
        n_estimators=100, 
        max_depth=4, 
        learning_rate=0.1, 
        scale_pos_weight=scale_weight,
        random_state=42,
        eval_metric='logloss',
        early_stopping_rounds=10
    )
    round_1_model.fit(X_train, y_train, eval_set=[(X_val, y_val)], verbose=False)
    
    model_r1_path = "ml/models/xgboost_baseline_round_1.pkl"
    with open(model_r1_path, "wb") as f:
        pickle.dump(round_1_model, f)
        
    print("\n--- Scoring Round 2 Against Retrained Defense (Round 3) ---")
    # Score ONLY on the 20% held-out test campaigns to prevent leakage
    r3_detection_rate, r3_caught, r3_total, r3_avg_amt, r3_fpr, r3_fp_count, r3_total_legit, _, _ = evaluate_round(r2_df, r2_test_camps, round_1_model, features, round_num=2)
    
    print(f"Round 3 Detection Rate (Recovered, Test-Set Only): {r3_detection_rate:.2%} ({r3_caught}/{r3_total} campaigns)")
    print(f"Round 1 Model FPR (on Round 2 legit txns): {r3_fpr:.4%} ({r3_fp_count}/{r3_total_legit} false positives)")
    
    print("\n--- Critical Check: Round 1 Model on ORIGINAL Round 1 Data ---")
    # We evaluate round_1_model on the df_test split (which contains Original Round 1 test data)
    orig_r1_detection_rate, orig_r1_caught, orig_r1_total, orig_r1_avg, orig_r1_fpr, orig_fp_count, orig_total_legit, _, _ = evaluate_round(df_test, campaigns, round_1_model, features, round_num=1)
    print(f"Round 1 Model Detection of ORIGINAL Round 1: {orig_r1_detection_rate:.2%} ({orig_r1_caught}/{orig_r1_total} campaigns)")
    print(f"Round 1 Model FPR on ORIGINAL Legit Test Set: {orig_r1_fpr:.4%} ({orig_fp_count}/{orig_total_legit} false positives)")
    
    # 7. Cache results for demo
    demo_cache = {
        "round_1_detection_rate": r1_detection_rate,
        "round_1_caught": int(r1_caught),
        "round_1_total": int(r1_total),
        "round_1_avg_amt": float(r1_avg_amt),
        "round_0_model_fpr": float(r1_fpr),
        "round_0_model_fp_count": int(r1_fp_count),
        "round_0_model_total_legit": int(r1_total_legit),
        "shap_explanation": [(str(k), float(v)) for k, v in sorted_shap[:3]],
        "llm_reasoning": reasoning,
        "mutated_params": mutated_params,
        "round_2_detection_rate": r2_detection_rate,
        "round_2_caught": int(r2_caught),
        "round_2_total": int(r2_total),
        "round_2_avg_amt": float(r2_avg_amt),
        "round_3_detection_rate": r3_detection_rate,
        "round_3_caught": int(r3_caught),
        "round_3_total": int(r3_total),
        "round_3_avg_amt": float(r3_avg_amt),
        "round_1_model_fpr": float(orig_r1_fpr), # Save the critical check FPR on original data for direct comparison
        "round_1_model_fp_count": int(orig_fp_count),
        "round_1_model_total_legit": int(orig_total_legit)
    }
    
    with open("ml/data/demo_cache.json", "w") as f:
        json.dump(demo_cache, f, indent=2)
        
    print("\nSaved entire round cycle to ml/data/demo_cache.json for live demo playback.")

if __name__ == "__main__":
    main()
