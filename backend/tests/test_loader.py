from app.config import CRM_XLSX_PATH, MEETINGS_DIR
from app.data.repository import load_repository


def test_calderon_loads_with_links():
    repo = load_repository(CRM_XLSX_PATH, MEETINGS_DIR)
    acc = repo.get_account("ACC-1002")
    assert acc is not None
    assert "Calderon" in acc.name
    assert acc.status == "Prospect"
    assert acc.aum_with_cg_mm == 0.0
    # Pipeline & Activities link by Account Name -> Account ID
    assert len(repo.pipeline_for_account("ACC-1002")) == 2
    assert len(repo.contacts_for_account("ACC-1002")) == 3
    assert len(repo.activities_for_account("ACC-1002")) >= 1
    # The trailing totals row must be dropped
    assert all(a.id for a in repo.list_accounts())
    assert len(repo.list_accounts()) == 25


def test_find_helpers():
    repo = load_repository(CRM_XLSX_PATH, MEETINGS_DIR)
    assert repo.find_account("calderon").id == "ACC-1002"
