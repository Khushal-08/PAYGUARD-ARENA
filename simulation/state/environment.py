from typing import Dict, List, Optional
from uuid import UUID
from datetime import datetime
from simulation.state.entities import (
    User, Account, Card, Device, IP, Merchant, Transaction, Campaign
)

class PaymentEnvironment:
    def __init__(self, start_time: datetime):
        self.clock: datetime = start_time
        
        # State stores
        self.users: Dict[UUID, User] = {}
        self.accounts: Dict[UUID, Account] = {}
        self.cards: Dict[UUID, Card] = {}
        self.devices: Dict[UUID, Device] = {}
        self.ips: Dict[str, IP] = {}
        self.merchants: Dict[UUID, Merchant] = {}
        
        # Event log
        self.transactions: List[Transaction] = []
        self.campaigns: Dict[UUID, Campaign] = {}
        
        # Fast lookup for state mutations
        self.user_ips: Dict[UUID, set] = {}

    def advance_clock(self, new_time: datetime):
        if new_time > self.clock:
            self.clock = new_time

    def register_user(self, user: User):
        self.users[user.user_id] = user
        self.user_ips[user.user_id] = set()

    def register_account(self, account: Account):
        self.accounts[account.account_id] = account

    def register_card(self, card: Card):
        self.cards[card.card_id] = card

    def register_device(self, device: Device):
        self.devices[device.device_id] = device

    def register_ip(self, ip: IP):
        self.ips[ip.ip_id] = ip

    def register_merchant(self, merchant: Merchant):
        self.merchants[merchant.merchant_id] = merchant

    def register_campaign(self, campaign: Campaign):
        self.campaigns[campaign.campaign_id] = campaign

    def process_transaction(self, txn: Transaction):
        """
        Processes a transaction and updates the world state accordingly.
        """
        # Ensure causal time
        if txn.timestamp > self.clock:
            self.clock = txn.timestamp
            
        # Update IP state
        user_id = self.accounts[txn.account_id].user_id
        if txn.ip_id not in self.user_ips[user_id]:
            self.user_ips[user_id].add(txn.ip_id)
            # The transaction itself might log that this IP is new for this user
            
        # Simple trust score adjustment (example logic)
        device = self.devices[txn.device_id]
        if txn.label == "Legit":
            device.trust_score = min(5.0, device.trust_score + 0.1)
        elif txn.label == "Fraud":
            device.trust_score = max(0.0, device.trust_score - 1.0)
            
        self.transactions.append(txn)
