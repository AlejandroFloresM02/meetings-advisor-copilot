"""Pydantic v2 models: CRM entities, meeting records, and API outputs."""

from __future__ import annotations

import datetime

from pydantic import BaseModel, Field


class Account(BaseModel):
    id: str
    name: str
    type: str
    region: str | None = None
    country_state: str | None = None
    aum_with_cg_mm: float = 0.0
    tier: str | None = None
    client_since: int | None = None
    primary_strategy: str | None = None
    relationship_manager: str | None = None
    consultant: str | None = None
    status: str | None = None


class Contact(BaseModel):
    id: str
    account_id: str
    name: str
    title: str | None = None
    role: str | None = None
    email: str | None = None
    phone: str | None = None
    last_contacted: datetime.date | None = None


class Opportunity(BaseModel):
    id: str
    account_id: str | None = None
    account_name: str
    opportunity: str | None = None
    strategy: str | None = None
    mandate_size_mm: float = 0.0
    stage: str | None = None
    probability: float = 0.0
    weighted_mm: float | None = None
    expected_close: datetime.date | None = None
    owner: str | None = None


class Activity(BaseModel):
    id: str
    account_id: str | None = None
    account_name: str
    date: datetime.date | None = None
    contact: str | None = None
    type: str | None = None
    subject: str | None = None
    owner: str | None = None
    next_step: str | None = None


class Decision(BaseModel):
    text: str
    by: str | None = None


class ActionItem(BaseModel):
    text: str
    owner: str | None = None
    status: str = "open"


class TranscriptTurn(BaseModel):
    speaker: str
    text: str


class MeetingRecord(BaseModel):
    id: str
    date: datetime.date
    type: str | None = None
    title: str
    participants: list[str] = Field(default_factory=list)
    summary: str = ""
    decisions: list[Decision] = Field(default_factory=list)
    action_items: list[ActionItem] = Field(default_factory=list)
    participant_interests: dict[str, list[str]] = Field(default_factory=dict)
    transcript_excerpt: list[TranscriptTurn] = Field(default_factory=list)
    source_activity: str | None = None
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
    explanation: str | None = None
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
    since_last_meeting: dict | None = None
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
