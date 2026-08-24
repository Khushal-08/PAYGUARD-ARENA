import random
import numpy as np
from datetime import datetime, timedelta
from uuid import uuid4
from simulation.state.entities import User, Account, Card, Device, IP, Transaction, Campaign
from simulation.state.environment import PaymentEnvironment

CATEGORIES = [
    {"label": "fake fraud alert", "desc": "Pretends to be a bank flagging suspicious activity"},
    {"label": "account block threat", "desc": "Threatens to close account unless verified"},
    {"label": "delivery/payment confirmation", "desc": "Claims a package or payment needs immediate attention"},
    {"label": "family emergency", "desc": "Urgent request from a 'family member' in trouble"},
    {"label": "tech support scam", "desc": "Fake technical support demanding payment for fixes"},
    {"label": "reward/refund claim", "desc": "Promises a refund or reward if user acts quickly"}
]

class SocialEngineeringAgent:
    def __init__(self, env: PaymentEnvironment, round_id: int = 1):
        self.env = env
        self.round_id = round_id

    def _get_victim_profile(self, user: User, account: Account) -> dict:
        """Extracts recent spending habits of the victim to inform the social engineering scenario."""
        user_txns = [t for t in self.env.transactions if t.account_id == account.account_id]
        
        if not user_txns:
            return {
                "age_days": (datetime.now() - user.created_at).days,
                "avg_spend": 50.0,
                "max_spend": 100.0,
                "top_merchants": ["Unknown"],
                "active_hours": "Unknown"
            }
            
        amounts = [t.amount for t in user_txns]
        merchants = [self.env.merchants[t.merchant_id].category for t in user_txns if t.merchant_id in self.env.merchants]
        hours = [t.timestamp.hour for t in user_txns]
        
        from collections import Counter
        top_merchants = [m[0] for m in Counter(merchants).most_common(2)] if merchants else ["Unknown"]
        
        peak_hour = Counter(hours).most_common(1)[0][0] if hours else 12
        active_hours = f"{peak_hour}:00 - {(peak_hour+4)%24}:00"
        
        return {
            "age_days": (user_txns[-1].timestamp - user.created_at).days,
            "avg_spend": float(np.mean(amounts)),
            "max_spend": float(np.max(amounts)),
            "top_merchants": top_merchants,
            "active_hours": active_hours
        }

    def execute_campaign(self, start_time: datetime, user: User, account: Account, card: Card) -> Campaign:
        campaign = Campaign(
            attack_type="GenAI Social Engineering",
            phase="victim_profiling",
            objective="Persuade victim to authorize out-of-pattern payment",
            status="Active",
            round_id=self.round_id,
            history=[]
        )
        self.env.register_campaign(campaign)
        
        def log_action(phase: str, action: str, params: dict, t: datetime):
            campaign.phase = phase
            campaign.history.append({
                "timestamp": t.isoformat(),
                "phase": phase,
                "action": action,
                "parameters": params
            })

        current_time = start_time
        
        # Phase 1: Victim Profiling
        profile = self._get_victim_profile(user, account)
        log_action("victim_profiling", "extract_profile", profile, current_time)
        current_time += timedelta(minutes=random.randint(5, 30))
        
        # Phase 2: Scenario Generation (Data-Driven Heuristics)
        log_action("scenario_generation", "query_heuristics", {"target": "generate_persuasive_scenario"}, current_time)
        
        # Select category, maybe weighted by spending habits (if they spend high, maybe reward/refund works better)
        category_choice = random.choice(CATEGORIES)
        urgency_angle = category_choice["label"]
        
        target_merchant_category = profile['top_merchants'][0] if profile['top_merchants'] else "Retail"
        
        # Calculate persuasiveness_score heuristics
        # If target_merchant_category is known and matches attack, persuasiveness is higher
        base_score = random.randint(4, 7)
        if target_merchant_category != "Unknown":
            base_score += 2
        if urgency_angle in ["fake fraud alert", "account block threat"]:
            base_score += 1 # Generally more effective
            
        p_score = min(10, max(1, base_score))
        
        # Target amount (e.g. 2x - 5x average spend, but capped to avoid obvious anomalies if not max spend)
        target_amt = float(profile['avg_spend'] * random.uniform(2.0, 5.0))
        
        scenario = {
            "target_merchant_category": target_merchant_category,
            "timing_rationale": f"Targets victim typical active window ({profile['active_hours']})",
            "urgency_angle": urgency_angle,
            "persuasiveness_score": p_score,
            "target_amount": round(target_amt, 2)
        }
        
        log_action("scenario_generation", "scenario_created", scenario, current_time)
        current_time += timedelta(minutes=random.randint(10, 60))
        
        # Phase 3: Simulated Victim Decision
        success_probability = p_score / 10.0
        victim_authorizes = random.random() < success_probability
        
        log_action("victim_decision", "simulate_decision", 
                  {"success_probability": success_probability, "authorized": victim_authorizes}, current_time)
        
        if not victim_authorizes:
            campaign.status = "Failed"
            log_action("completed", "campaign_end", {"result": "victim_rejected_scam"}, current_time)
            return campaign
            
        current_time += timedelta(minutes=random.randint(1, 15))
        
        # Phase 4: Authorization and Transaction
        log_action("authorization", "payment_authorized", {"amount": target_amt}, current_time)
        
        attacker_device = Device(user_id=user.user_id, first_seen=current_time, trust_score=0.1)
        self.env.register_device(attacker_device)
        attacker_ip = IP(ip_id=f"10.{random.randint(1,255)}.{random.randint(1,255)}.{random.randint(1,255)}", 
                         geo="US", first_seen=current_time)
        self.env.register_ip(attacker_ip)
        
        merchants_list = list(self.env.merchants.values())
        merchant = random.choice(merchants_list) if merchants_list else None
        
        if merchant:
            txn = Transaction(
                account_id=account.account_id, card_id=card.card_id, device_id=attacker_device.device_id, ip_id=attacker_ip.ip_id,
                merchant_id=merchant.merchant_id, amount=target_amt, timestamp=current_time, channel="Online",
                label="Fraud", campaign_id=campaign.campaign_id, round_id=self.round_id
            )
            self.env.process_transaction(txn)
            
        campaign.status = "Completed"
        log_action("completed", "campaign_end", {"result": "payment_successful", "amount": target_amt}, current_time)
        
        return campaign
