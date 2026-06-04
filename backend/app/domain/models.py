"""Pydantic v2 models: CRM entities, meeting records, and API outputs."""
from __future__ import annotations

from datetime import date as Date
from typing import Optional

from pydantic import BaseModel, Field


class Account(BaseModel):
    id: str
    name: str
    type: str
    region: Optional[str] = None
    country_state: Optional[str] = None
    aum_with_cg_mm: float = 0.0
    tier: Optional[str] = None
    client_since: Optional[int] = None
    primary_strategy: Optional[str] = None
    relationship_manager: Optional[str] = None
    consultant: Optional[str] = None
    status: Optional[str] = None


class Contact(BaseModel):
    id: str
    account_id: str
    name: str
    title: Optional[str] = None
    role: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    last_contacted: Optional[Date] = None


class Opportunity(BaseModel):
    id: str
    account_id: Optional[str] = None
    account_name: str
    opportunity: Optional[str] = None
    strategy: Optional[str] = None
    mandate_size_mm: float = 0.0
    stage: Optional[str] = None
    probability: float = 0.0
    weighted_mm: Optional[float] = None
    expected_close: Optional[Date] = None
    owner: Optional[str] = None


class Activity(BaseModel):
    id: str
    account_id: Optional[str] = None
    account_name: str
    date: Optional[Date] = None
    contact: Optional[str] = None
    type: Optional[str] = None
    subject: Optional[str] = None
    owner: Optional[str] = None
    next_step: Optional[str] = None


class Decision(BaseModel):
    text: str
    by: Optional[str] = None


class ActionItem(BaseModel):
    text: str
    owner: Optional[str] = None
    status: str = "open"


class TranscriptTurn(BaseModel):
    speaker: str
    text: str


class MeetingRecord(BaseModel):
    id: str
    date: Date
    type: Optional[str] = None
    title: str
    participants: list[str] = Field(default_factory=list)
    summary: str = ""
    decisions: list[Decision] = Field(default_factory=list)
    action_items: list[ActionItem] = Field(default_factory=list)
    participant_interests: dict[str, list[str]] = Field(default_factory=dict)
    transcript_excerpt: list[TranscriptTurn] = Field(default_factory=list)
    source_activity: Optional[str] = None
    synthetic: bool = True


class RiskComponent(BaseModel):
    key: str
    title: str
    score: float
    severity: str
    evidence: str
    sources: list[str] = Field(default_factory=list)


class RiskResult(BaseModel):
    overall: float
    severity: str
    components: list[RiskComponent]


class RiskFlag(BaseModel):
    id: str
    title: str
    severity: str
    score: float
    evidence: str
    explanation: Optional[str] = None
    sources: list[str] = Field(default_factory=list)


class TalkingPoint(BaseModel):
    text: str
    sources: list[str] = Field(default_factory=list)


class AccountBrief(BaseModel):
    account: dict
    meeting: dict
    headline: str
    risk_flags: list[RiskFlag] = Field(default_factory=list)
    talking_points: list[TalkingPoint] = Field(default_factory=list)
    since_last_meeting: Optional[dict] = None
    suggested_next_steps: list[str] = Field(default_factory=list)
    meta: dict = Field(default_factory=dict)


class ParticipantCard(BaseModel):
    contact: dict
    relationship: dict
    interests: list[str] = Field(default_factory=list)
    prior_decisions: list[dict] = Field(default_factory=list)
    meeting_relevance: str = ""
    talking_point: str = ""
    sources: list[str] = Field(default_factory=list)
