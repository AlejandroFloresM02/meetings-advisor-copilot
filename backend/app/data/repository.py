"""In-memory repository over the loaded CRM + meeting fixtures."""

from __future__ import annotations

from pathlib import Path

from app.data import loader
from app.domain.models import Account, Activity, Contact, MeetingRecord, Opportunity


class Repository:
    def __init__(self, accounts, contacts, opportunities, activities, meetings):
        self.accounts: dict[str, Account] = {a.id: a for a in accounts}
        self.contacts: dict[str, Contact] = {c.id: c for c in contacts}
        self.opportunities: list[Opportunity] = list(opportunities)
        self.activities: list[Activity] = list(activities)
        self.meetings: dict[str, list[MeetingRecord]] = dict(meetings)
        self._meeting_index: dict[str, MeetingRecord] = {
            m.id: m for ms in self.meetings.values() for m in ms
        }

    def get_account(self, account_id: str) -> Account | None:
        return self.accounts.get(account_id)

    def list_accounts(self) -> list[Account]:
        return list(self.accounts.values())

    def contacts_for_account(self, account_id: str) -> list[Contact]:
        return [c for c in self.contacts.values() if c.account_id == account_id]

    def get_contact(self, contact_id: str) -> Contact | None:
        return self.contacts.get(contact_id)

    def pipeline_for_account(self, account_id: str) -> list[Opportunity]:
        return [o for o in self.opportunities if o.account_id == account_id]

    def activities_for_account(self, account_id: str) -> list[Activity]:
        return [a for a in self.activities if a.account_id == account_id]

    def meetings_for_account(self, account_id: str) -> list[MeetingRecord]:
        return self.meetings.get(account_id, [])

    def get_meeting(self, meeting_id: str) -> MeetingRecord | None:
        return self._meeting_index.get(meeting_id)

    def find_account(self, query: str) -> Account | None:
        q = query.strip().lower()
        if q.upper() in self.accounts:
            return self.accounts[q.upper()]
        for a in self.accounts.values():
            if q in a.name.lower():
                return a
        return None

    def find_contact(self, query: str) -> Contact | None:
        q = query.strip().lower()
        if q.upper() in self.contacts:
            return self.contacts[q.upper()]
        for c in self.contacts.values():
            if q in c.name.lower():
                return c
        return None


def load_repository(xlsx_path: Path, meetings_dir: Path) -> Repository:
    accounts = loader.load_accounts(xlsx_path)
    name_to_id = {a.name: a.id for a in accounts}
    contacts = loader.load_contacts(xlsx_path)
    opportunities = loader.load_pipeline(xlsx_path, name_to_id)
    activities = loader.load_activities(xlsx_path, name_to_id)
    meetings = loader.load_meetings(meetings_dir)
    return Repository(accounts, contacts, opportunities, activities, meetings)
