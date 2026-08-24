import random
import numpy as np
from datetime import datetime, timedelta
from uuid import uuid4
from simulation.state.entities import User, Account, Card, Device, IP, Merchant, Transaction
from simulation.state.environment import PaymentEnvironment

class LegitimateTrafficGenerator:
    def __init__(self, env: PaymentEnvironment, num_users: int = 4000, num_merchants: int = 500):
        self.env = env
        self.num_users = num_users
        self.num_merchants = num_merchants
        self.user_base_scales = {}

    def _get_next_event_delay(self, current_time: datetime, user_id) -> timedelta:
        """
        Draws the next inter-arrival time using thinning (acceptance-rejection) 
        to properly model an inhomogeneous Poisson process.
        """
        base_scale = self.user_base_scales[user_id]
        t = current_time
        
        while True:
            # Jump forward by the maximum possible rate
            delay_hours = np.random.exponential(scale=base_scale)
            t += timedelta(hours=delay_hours)
            
            # Acceptance probability based on hour of day to create sharp daily cycles
            hour = t.hour
            if 10 <= hour <= 20:
                prob = 1.0        # Peak retail hours
            elif 7 <= hour < 10 or 21 <= hour <= 23:
                prob = 0.5        # Shoulder hours
            else:
                prob = 0.15       # Deep off-peak (midnight to 6am) - suppresses volume significantly
                
            if random.random() < prob:
                return t - current_time

    def bootstrap_world(self, duration_days: int = 90):
        """Creates the initial population of users, merchants, etc."""
        categories = ["retail", "grocery", "travel", "digital", "dining"]
        for _ in range(self.num_merchants):
            m = Merchant(
                category=random.choice(categories),
                trust_tier=random.randint(1, 5)
            )
            self.env.register_merchant(m)
            
        for _ in range(self.num_users):
            # 50% of users exist at start (Day 0), 50% organically onboard over 90 days
            if random.random() < 0.5:
                created_at = self.env.clock
            else:
                created_at = self.env.clock + timedelta(days=random.uniform(0, duration_days))
                
            u = User(created_at=created_at)
            self.env.register_user(u)
            
            # Heavy-tailed base arrival rate per user (lognormal)
            self.user_base_scales[u.user_id] = max(1.0, np.random.lognormal(mean=3.4, sigma=1.0))
            
            a = Account(user_id=u.user_id, opened_at=created_at)
            self.env.register_account(a)
            
            c = Card(account_id=a.account_id, issued_at=created_at)
            self.env.register_card(c)
            
            d = Device(user_id=u.user_id, first_seen=created_at)
            self.env.register_device(d)
            
            ip = IP(ip_id=f"{random.randint(1,255)}.{random.randint(1,255)}.{random.randint(1,255)}.1", 
                    geo="US", first_seen=created_at)
            self.env.register_ip(ip)

    def generate_timeline(self, duration_days: int = 90):
        """Simulates transactions via a Poisson process per user."""
        end_time = self.env.clock + timedelta(days=duration_days)
        events = []
        merchants_list = list(self.env.merchants.values())
        
        for user_id, user in self.env.users.items():
            account = next(a for a in self.env.accounts.values() if a.user_id == user_id)
            card = next(c for c in self.env.cards.values() if c.account_id == account.account_id)
            device = next(d for d in self.env.devices.values() if d.user_id == user_id)
            ips_set = self.env.user_ips.get(user_id, set())
            ip_str = next(iter(ips_set), f"{random.randint(1,255)}.0.0.1")
            
            delay = self._get_next_event_delay(user.created_at, user_id)
            events.append({"time": user.created_at + delay, "user": user_id, 
                           "account": account, "card": card, "device": device, "ip": ip_str})
            
        events.sort(key=lambda x: x["time"])
        
        while events:
            current_event = events.pop(0)
            t = current_event["time"]
            
            if t > end_time:
                break
                
            self.env.advance_clock(t)
            
            merchant = random.choice(merchants_list)
            amount = round(np.random.lognormal(mean=3.5, sigma=1.0), 2)
            
            txn = Transaction(
                account_id=current_event["account"].account_id,
                card_id=current_event["card"].card_id,
                device_id=current_event["device"].device_id,
                ip_id=current_event["ip"],
                merchant_id=merchant.merchant_id,
                amount=amount,
                timestamp=t,
                channel="Online",
                label="Legit"
            )
            
            self.env.process_transaction(txn)
            
            delay = self._get_next_event_delay(t, current_event["user"])
            current_event["time"] = t + delay
            
            inserted = False
            for i, ev in enumerate(events):
                if ev["time"] > current_event["time"]:
                    events.insert(i, current_event)
                    inserted = True
                    break
            if not inserted:
                events.append(current_event)
