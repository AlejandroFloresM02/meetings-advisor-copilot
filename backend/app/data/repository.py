"""In-memory repository over committed snapshots (spec §4)."""

from __future__ import annotations

from pathlib import Path

from app.data.snapshot import Snapshot, load_all_snapshots
from app.domain.models import Institution


class Repository:
    def __init__(self, snapshots: dict[str, Snapshot]):
        self.snapshots = dict(snapshots)

    def get(self, client_id: str) -> Snapshot | None:
        return self.snapshots.get(client_id)

    def all(self) -> list[Snapshot]:
        return list(self.snapshots.values())

    def institutions(self) -> list[Institution]:
        return [s.institution for s in self.snapshots.values()]


def load_repository(directory: Path) -> Repository:
    return Repository(load_all_snapshots(directory))
