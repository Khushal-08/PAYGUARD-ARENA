import os
import json
import pickle
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional, Dict, Any
import shap

# --- Simulation Imports ---
from simulation.state.environment import PaymentEnvironment
from simulation.state.baseline_generator import LegitimateTrafficGenerator
from simulation.attacks.synthetic_identity import SyntheticIdentityAgent
from simulation.attacks.account_takeover import AccountTakeoverAgent

app = FastAPI(title="PayGuard Arena API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "https://payguard-arena-kxjk44094-kadamkhushal6-3619s-projects.vercel.app",
        "http://localhost:3000"
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Load Model
MODEL_PATH = os.path.join(os.path.dirname(__file__), "..", "ml", "models", "xgboost_baseline_round_1.pkl")
model = None
explainer = None
if os.path.exists(MODEL_PATH):
    with open(MODEL_PATH, "rb") as f:
        model = pickle.load(f)
        explainer = shap.TreeExplainer(model)

# Load cached data for demo
CACHE_PATH = os.path.join(os.path.dirname(__file__), "..", "ml", "data", "demo_cache.json")

def get_demo_cache():
    try:
        with open(CACHE_PATH, "r") as f:
            return json.load(f)
    except FileNotFoundError:
        return {"error": "demo_cache.json not found"}

class CampaignRequest(BaseModel):
    attack_type: str
    victim_profile: Optional[Dict[str, Any]] = None

class TransactionRequest(BaseModel):
    transaction: Dict[str, Any]

class AdaptAttackRequest(BaseModel):
    campaign_id: str
    defense_signal: Dict[str, Any]

class AdaptDefenseRequest(BaseModel):
    retrain_trigger: bool

@app.post("/simulate/campaign")
async def simulate_campaign(req: CampaignRequest):
    env = PaymentEnvironment(start_time=datetime.utcnow())
    
    if req.attack_type.lower() == "account_takeover":
        # Need a dummy baseline for an ATO
        gen = LegitimateTrafficGenerator(env=env, num_users=1, num_merchants=5)
        gen.bootstrap_world()
        gen.generate_timeline(duration_days=10)
        
        user = list(env.users.values())[0]
        account = next((a for a in env.accounts.values() if a.user_id == user.user_id), None)
        card = next((c for c in env.cards.values() if c.account_id == account.account_id), None)
        
        agent = AccountTakeoverAgent(env=env, round_id=1)
        campaign = agent.execute_campaign(start_time=datetime.utcnow(), user=user, account=account, card=card)
    else:
        # Default to Synthetic Identity
        agent = SyntheticIdentityAgent(env=env, round_id=1)
        campaign = agent.execute_campaign(start_time=datetime.utcnow())
        
    def default_serializer(obj):
        if isinstance(obj, datetime):
            return obj.isoformat()
        from uuid import UUID
        if isinstance(obj, UUID):
            return str(obj)
        return str(obj)
        
    campaign_dict = json.loads(json.dumps(campaign.model_dump(), default=default_serializer))
    
    return {
        "campaign_id": str(campaign.campaign_id),
        "status": "completed",
        "attack_type": req.attack_type,
        "campaign": campaign_dict
    }

@app.post("/defend/score")
async def defend_score(req: TransactionRequest):
    if not model or not explainer:
        raise HTTPException(status_code=500, detail="XGBoost model not loaded")
    
    txn = req.transaction
    
    # Feature list matching the model training
    features = [
        'amount', 'hour_of_day', 'day_of_week', 
        'account_time_since_last_txn', 'is_new_account', 'account_txns_24h', 
        'account_txns_7d', 'device_txns_7d', 'is_familiar_merchant'
    ]
    
    row = {}
    for f in features:
        val = txn.get(f)
        if val is None or val == "":
            # CRITICAL: Handle missing recency same as entity_aggregates.py
            if f == 'account_time_since_last_txn':
                row[f] = np.nan
            elif f == 'is_new_account':
                # If recency was missing, infer this is a new account
                row[f] = 1.0 if txn.get('account_time_since_last_txn') in (None, "") else 0.0
            else:
                row[f] = 0.0
        else:
            row[f] = float(val)
            
    df = pd.DataFrame([row])
    
    # Predict
    prob = float(model.predict_proba(df)[0, 1])
    
    # Basic decision logic
    decision = "APPROVE"
    if prob > 0.8:
        decision = "BLOCK"
    elif prob > 0.5:
        decision = "REVIEW"
        
    # SHAP logic
    shap_values = explainer.shap_values(df)
    
    if isinstance(shap_values, list):
        sv = shap_values[1][0]
    else:
        sv = shap_values[0]
        
    importances = list(zip(features, sv))
    importances.sort(key=lambda x: abs(x[1]), reverse=True)
    
    shap_top_features = [[feat, float(val)] for feat, val in importances[:3]]
    
    return {
        "risk_score": prob, 
        "decision": decision, 
        "shap_top_features": shap_top_features
    }

@app.post("/adapt/attack")
async def adapt_attack(req: AdaptAttackRequest):
    return {"new_campaign_id": f"{req.campaign_id}_mutated"}

@app.post("/adapt/defense")
async def adapt_defense(req: AdaptDefenseRequest):
    return {"new_model_version_id": "xgboost_baseline_round_2"}

@app.get("/arena/round/{n}")
async def get_arena_round(n: int):
    cache = get_demo_cache()
    if "error" in cache:
        raise HTTPException(status_code=404, detail="Cache file not found")
    return cache

@app.get("/metrics/summary")
async def get_metrics_summary():
    base_dir = os.path.join(os.path.dirname(__file__), "..")
    
    # 1. Baseline ladder
    baseline_ladder = []
    baseline_error = None
    baseline_json_path = os.path.join(base_dir, "ml", "data", "baseline_results.json")
    try:
        with open(baseline_json_path, 'r') as f:
            baseline_ladder = json.load(f)
    except Exception as e:
        baseline_error = f"Failed to load baseline_results.json: {str(e)}"

    # 2. FPR comparison & 3. Adaptive loop summary
    fpr_comparison = None
    fpr_error = None
    adaptive_loop = None
    adaptive_error = None
    
    cache = get_demo_cache()
    if "error" in cache:
        fpr_error = "demo_cache.json not found or failed to load"
        adaptive_error = "demo_cache.json not found or failed to load"
    else:
        # Validate FPR fields
        try:
            fpr_comparison = {
                "round_0": {
                    "fpr": cache["round_0_model_fpr"],
                    "fp_count": cache["round_0_model_fp_count"],
                    "total_legit": cache["round_0_model_total_legit"]
                },
                "round_1": {
                    "fpr": cache["round_1_model_fpr"],
                    "fp_count": cache["round_1_model_fp_count"],
                    "total_legit": cache["round_1_model_total_legit"]
                }
            }
        except KeyError as e:
            fpr_error = f"Missing field in demo_cache.json for FPR comparison: {str(e)}"
            
        # Validate Adaptive fields
        try:
            adaptive_loop = {
                "round_1": {
                    "detection_rate": cache["round_1_detection_rate"],
                    "avg_bust_out": cache["round_1_avg_amt"]
                },
                "round_2": {
                    "detection_rate": cache["round_2_detection_rate"],
                    "avg_bust_out": cache["round_2_avg_amt"]
                },
                "round_3": {
                    "detection_rate": cache["round_3_detection_rate"],
                    "avg_bust_out": cache["round_3_avg_amt"]
                }
            }
        except KeyError as e:
            adaptive_error = f"Missing field in demo_cache.json for Adaptive Loop: {str(e)}"

    # 4. Time-consistency check results
    time_consistency = []
    time_consistency_error = None
    tc_json_path = os.path.join(base_dir, "ml", "data", "time_consistency_results.json")
    
    try:
        if os.path.exists(tc_json_path):
            with open(tc_json_path, 'r') as f:
                tc_data = json.load(f)
                for item in tc_data:
                    time_consistency.append({
                        "feature": item.get("feature"),
                        "passed": item.get("is_time_consistent"),
                        "reason": item.get("reason")
                    })
                        
        if not time_consistency and not os.path.exists(tc_json_path):
            time_consistency_error = "time_consistency_results.json not found."
    except Exception as e:
         time_consistency_error = f"Failed to parse time consistency JSONs: {str(e)}"
                    
    payload = {
        "baseline_ladder": baseline_ladder,
        "fpr_comparison": fpr_comparison,
        "adaptive_loop": adaptive_loop,
        "time_consistency": time_consistency
    }
    
    # Inject error fields if any
    if baseline_error: payload["baseline_error"] = baseline_error
    if fpr_error: payload["fpr_error"] = fpr_error
    if adaptive_error: payload["adaptive_error"] = adaptive_error
    if time_consistency_error: payload["time_consistency_error"] = time_consistency_error
    
    return payload
