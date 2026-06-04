from app.config import CRM_XLSX_PATH, MEETINGS_DIR
from app.data.repository import load_repository
from scripts.generate_meetings import build_meeting_record


def test_build_meeting_record_validates_participants():
    repo = load_repository(CRM_XLSX_PATH, MEETINGS_DIR)
    acc = repo.get_account("ACC-1002")
    contacts = repo.contacts_for_account("ACC-1002")
    act = repo.activities_for_account("ACC-1002")[0]
    raw = {
        "summary": "Discussed the mandate.",
        "decisions": [{"text": "Proceed", "by": "Patricia Schmidt"}],
        "action_items": [{"text": "Send fees", "owner": "Diane Okafor", "status": "open"}],
        "participant_interests": {contacts[0].name: ["fees"]},
        "transcript_excerpt": [{"speaker": "X", "text": "hi"}],
        "participants": [contacts[0].name, "Nonexistent Person"],  # invalid name dropped
    }
    rec = build_meeting_record(act, acc, contacts, raw, index=1)
    assert rec.id.startswith("MTG-1002-")
    assert rec.date == act.date
    assert contacts[0].id in rec.participants            # name resolved to ID
    assert all(p in {c.id for c in contacts} for p in rec.participants)  # invalid dropped
    assert contacts[0].id in rec.participant_interests   # interests re-keyed to ID
    assert rec.synthetic is True
