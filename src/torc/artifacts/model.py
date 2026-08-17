"""Language-native v1alpha1 artifact contracts and producer boundary."""

from __future__ import annotations

from typing import Any, NotRequired, Protocol, TypedDict


class Collector(TypedDict):
    name: str
    version: str


class RepositoryRef(TypedDict):
    repository: str
    commit: str
    branch: NotRequired[str | None]


class EvidenceScope(TypedDict):
    repositories: list[RepositoryRef]


class EvidenceSelector(TypedDict):
    type: str
    start: NotRequired[int]
    end: NotRequired[int]


class EvidenceSource(TypedDict):
    source_id: str
    type: str
    repository: str
    commit: str
    path: str
    selector: EvidenceSelector
    content_sha256: str
    collected_at: str
    content: str


class RecentCommit(TypedDict):
    commit: str
    subject: str
    authored_at: str


class GitState(TypedDict):
    repository: str
    commit: str
    branch: str | None
    clean: bool
    modified_paths: list[str]
    untracked_paths: list[str]
    recent_commits: list[RecentCommit]


class EvidenceBundle(TypedDict):
    schema: str
    bundle_id: str
    collected_at: str
    collector: Collector
    scope: EvidenceScope
    sources: list[EvidenceSource]
    git_state: list[GitState]
    warnings: list[str]


class SnapshotScope(TypedDict):
    name: str
    repositories: list[RepositoryRef]


class Generator(TypedDict):
    implementation: str
    version: str
    provider: NotRequired[str]
    model: NotRequired[str]


class EvidenceReference(TypedDict):
    source_id: str


class Claim(TypedDict):
    claim_id: str
    subject: str
    predicate: str
    value: Any
    status: str
    evidence: list[EvidenceReference]
    observed_at: str


class ProjectSnapshot(TypedDict):
    schema: str
    artifact_id: str
    kind: str
    generated_at: str
    scope: SnapshotScope
    generator: Generator
    evidence_bundle: dict[str, str]
    projects: list[dict[str, Any]]
    claims: list[Claim]
    blockers: list[dict[str, Any]]
    pending_decisions: list[dict[str, Any]]
    recent_activity: list[dict[str, Any]]
    conflicts: list[dict[str, Any]]
    unknowns: list[dict[str, Any]]
    metadata: dict[str, Any]


class AcceptanceCheck(TypedDict):
    name: str
    status: str
    detail: str


class AcceptanceReceipt(TypedDict):
    schema: str
    receipt_id: str
    artifact_id: str
    evidence_bundle_id: str
    validated_at: str
    validator: Collector
    status: str
    checks: list[AcceptanceCheck]
    warnings: list[str]
    errors: list[str]


class ProjectSnapshotProducer(Protocol):
    """Provider-neutral candidate boundary: evidence in, immutable projection out."""

    def produce(self, evidence_bundle: EvidenceBundle) -> ProjectSnapshot: ...
