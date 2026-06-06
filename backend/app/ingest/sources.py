"""Client identity + the trusted-source registry / allowlist (spec §4, §5).

The registry encodes the allowlist as data: each SourceDescriptor maps a fact
group to an extractor and either a canonical URL (discover bypassed) or a
SearXNG query constrained to allowlisted domains.
"""

from __future__ import annotations

from app.ingest.models import SourceDescriptor

# Stable per-client identity (the institution's name/type/benchmark — not the
# variable facts, which are fetched). The fund's own site is the citation.
_IDENTITY: dict[str, dict] = {
    "CALPERS": {
        "id": "CALPERS",
        "name": "CalPERS",
        "type": "public_pension",
        "policy_benchmark": "CalPERS Policy Benchmark",
        "site": "https://www.calpers.ca.gov",
    },
}

_PPD_DOMAINS = ["publicplansdata.org"]
_FUND_DOMAINS = ["calpers.ca.gov"]
_NEWS_DOMAINS = ["pionline.com", "ai-cio.com", "calpers.ca.gov"]


def client_identity(client_id: str) -> dict:
    return dict(_IDENTITY[client_id])


def sources_for(client_id: str) -> list[SourceDescriptor]:
    if client_id not in _IDENTITY:
        raise KeyError(client_id)
    return [
        SourceDescriptor(
            client_id=client_id,
            fact_group="institution",
            extractor="publicplans",
            url="https://publicplansdata.org/public-plans-database/download-data/",
            domains=_PPD_DOMAINS,
        ),
        SourceDescriptor(
            client_id=client_id,
            fact_group="institution",
            extractor="acfr",
            query="CalPERS Annual Comprehensive Financial Report funded ratio",
            domains=_FUND_DOMAINS,
        ),
        SourceDescriptor(
            client_id=client_id,
            fact_group="seats",
            extractor="board",
            url="https://www.calpers.ca.gov/page/about/board",
            domains=_FUND_DOMAINS,
        ),
        SourceDescriptor(
            client_id=client_id,
            fact_group="actions",
            extractor="news",
            query="CalPERS manager hire termination search watch",
            domains=_NEWS_DOMAINS,
        ),
    ]
