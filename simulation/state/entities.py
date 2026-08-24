from pydantic import BaseModel, Field
from typing import Optional, Dict, Any, List
from uuid import UUID, uuid4
from datetime import datetime

class User(BaseModel):
    user_id: UUID = Field(default_factory=uuid4)
    profile_attrs: Dict[str, Any] = Field(default_factory=dict)
    created_at: datetime
    is_synthetic: bool = False

class Account(BaseModel):
    account_id: UUID = Field(default_factory=uuid4)
    user_id: UUID
    opened_at: datetime
    status: str = "Active"

class Card(BaseModel):
    card_id: UUID = Field(default_factory=uuid4)
    account_id: UUID
    issued_at: datetime
    status: str = "Active"

class Device(BaseModel):
    device_id: UUID = Field(default_factory=uuid4)
    user_id: UUID
    first_seen: datetime
    trust_score: float = 1.0

class IP(BaseModel):
    ip_id: str
    geo: str
    first_seen: datetime
    is_new_for_user: bool = True

class Merchant(BaseModel):
    merchant_id: UUID = Field(default_factory=uuid4)
    category: str
    trust_tier: int = 3

class Transaction(BaseModel):
    txn_id: UUID = Field(default_factory=uuid4)
    account_id: UUID
    card_id: UUID
    device_id: UUID
    ip_id: str
    merchant_id: UUID
    amount: float
    timestamp: datetime
    channel: str
    label: str = "Legit"  # Fraud / Legit
    campaign_id: Optional[UUID] = None
    round_id: Optional[int] = None

class Campaign(BaseModel):
    campaign_id: UUID = Field(default_factory=uuid4)
    attack_type: str
    phase: str
    objective: str
    status: str
    round_id: int
    history: List[Dict[str, Any]] = Field(default_factory=list)
