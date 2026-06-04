"""Read Capital_Group_CRM_mock.xlsx into domain models. Pipeline & Activities
carry only Account Name, so we resolve Account ID via a name->id map."""
from __future__ import annotations

import json
from datetime import date
from pathlib import Path
from typing import Optional

import pandas as pd

from app.domain.models import Account, Activity, Contact, MeetingRecord, Opportunity


def _s(v) -> Optional[str]:
    if v is None or (isinstance(v, float) and pd.isna(v)):
        return None
    s = str(v).strip()
    return s or None


def _f(v) -> float:
    try:
        if v is None or (isinstance(v, float) and pd.isna(v)):
            return 0.0
        return float(v)
    except (TypeError, ValueError):
        return 0.0


def _d(v) -> Optional[date]:
    ts = pd.to_datetime(v, errors="coerce")
    return None if pd.isna(ts) else ts.date()


def _year(v) -> Optional[int]:
    f = _f(v)
    return int(f) if f else None


def load_accounts(xlsx: Path) -> list[Account]:
    df = pd.read_excel(xlsx, sheet_name="Accounts")
    out = []
    for _, r in df.iterrows():
        aid = _s(r.get("Account ID"))
        if not aid:  # drop the trailing totals row
            continue
        out.append(Account(
            id=aid, name=_s(r.get("Account Name")) or aid, type=_s(r.get("Type")) or "",
            region=_s(r.get("Region")), country_state=_s(r.get("Country/State")),
            aum_with_cg_mm=_f(r.get("AUM with CG ($mm)")), tier=_s(r.get("Tier")),
            client_since=_year(r.get("Client Since")), primary_strategy=_s(r.get("Primary Strategy")),
            relationship_manager=_s(r.get("Relationship Mgr")), consultant=_s(r.get("Consultant")),
            status=_s(r.get("Status")),
        ))
    return out


def load_contacts(xlsx: Path) -> list[Contact]:
    df = pd.read_excel(xlsx, sheet_name="Contacts")
    out = []
    for _, r in df.iterrows():
        cid = _s(r.get("Contact ID"))
        if not cid:
            continue
        name = " ".join(x for x in [_s(r.get("First Name")), _s(r.get("Last Name"))] if x)
        out.append(Contact(
            id=cid, account_id=_s(r.get("Account ID")) or "", name=name or cid,
            title=_s(r.get("Title")), role=_s(r.get("Role")), email=_s(r.get("Email")),
            phone=_s(r.get("Phone")), last_contacted=_d(r.get("Last Contacted")),
        ))
    return out


def load_pipeline(xlsx: Path, name_to_id: dict[str, str]) -> list[Opportunity]:
    df = pd.read_excel(xlsx, sheet_name="Pipeline")
    out = []
    for _, r in df.iterrows():
        oid = _s(r.get("Opportunity ID"))
        if not oid:
            continue
        aname = _s(r.get("Account Name")) or ""
        out.append(Opportunity(
            id=oid, account_id=name_to_id.get(aname), account_name=aname,
            opportunity=_s(r.get("Opportunity")), strategy=_s(r.get("Strategy")),
            mandate_size_mm=_f(r.get("Mandate Size ($mm)")), stage=_s(r.get("Stage")),
            probability=_f(r.get("Probability")), weighted_mm=_f(r.get("Weighted ($mm)")),
            expected_close=_d(r.get("Expected Close")), owner=_s(r.get("Owner")),
        ))
    return out


def load_activities(xlsx: Path, name_to_id: dict[str, str]) -> list[Activity]:
    df = pd.read_excel(xlsx, sheet_name="Activities")
    out = []
    for _, r in df.iterrows():
        aid = _s(r.get("Activity ID"))
        if not aid:
            continue
        aname = _s(r.get("Account Name")) or ""
        out.append(Activity(
            id=aid, account_id=name_to_id.get(aname), account_name=aname,
            date=_d(r.get("Date")), contact=_s(r.get("Contact")), type=_s(r.get("Type")),
            subject=_s(r.get("Subject")), owner=_s(r.get("Owner")), next_step=_s(r.get("Next Step")),
        ))
    return out


def load_meetings(meetings_dir: Path) -> dict[str, list[MeetingRecord]]:
    out: dict[str, list[MeetingRecord]] = {}
    if not meetings_dir.exists():
        return out
    for fp in sorted(meetings_dir.glob("*.json")):
        data = json.loads(fp.read_text(encoding="utf-8"))
        acc_id = data.get("account_id") or fp.stem
        out[acc_id] = [MeetingRecord.model_validate(m) for m in data.get("meetings", [])]
    return out
