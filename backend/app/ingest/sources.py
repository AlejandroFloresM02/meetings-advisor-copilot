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

# PPD REST API (publicplansdata.org/api/) — CalPERS is ppd_id 9 ("California
# PERF"). Two deterministic calls: QVariables for scalars, QDataSet for actual
# allocation. The fy range is wide; the extractor selects the latest populated
# year. (The old /download-data/ slug 404s — confirmed in the first live run.)
_PPD_SCALARS_URL = (
    "https://publicplansdata.org/api/?q=QVariables"
    "&variables=ppd_id,PlanName,fy,ActFundedRatio_GASB,"
    "InvestmentReturnAssumption_GASB,ActAssets_GASB,MktAssets_net"
    "&filterppdid=9&filterfystart=2018&filterfyend=2025&format=json"
)
_PPD_ALLOCATION_URL = (
    "https://publicplansdata.org/api/?q=QDataSet"
    "&dataset=pensioninvestmentperformance"
    "&filterppdid=9&filterfystart=2018&filterfyend=2025&format=json"
)


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
            url=_PPD_SCALARS_URL,
            domains=_PPD_DOMAINS,
        ),
        SourceDescriptor(
            client_id=client_id,
            fact_group="institution",
            extractor="publicplans",
            url=_PPD_ALLOCATION_URL,
            domains=_PPD_DOMAINS,
        ),
        SourceDescriptor(
            client_id=client_id,
            fact_group="institution",
            extractor="acfr",
            query="CalPERS Annual Comprehensive Financial Report funded ratio",
            domains=_FUND_DOMAINS,
        ),
        # Two real roster sub-pages (the /about/board hub is link-only and has no
        # seats — it makes the LLM confabulate; the groundedness guard + these
        # URLs were validated by the first live run). Both feed the `board`
        # extractor; the pipeline fans their seats together.
        SourceDescriptor(
            client_id=client_id,
            fact_group="seats",
            extractor="board",
            url="https://www.calpers.ca.gov/about/board/board-members",
            domains=_FUND_DOMAINS,
        ),
        SourceDescriptor(
            client_id=client_id,
            fact_group="seats",
            extractor="board",
            url="https://www.calpers.ca.gov/investments/about-investment-office/investment-office-senior-team",
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
