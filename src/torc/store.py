"""SQLite persistence for the TORC P0 vertical slice."""

from __future__ import annotations

import json
import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Any

from .canonical import canonical_json, seal_record, utc_now
from .errors import LeaseConflictError, NotFoundError, SchemaVersionError
from .ids import new_id

_MIGRATION_1 = """
CREATE TABLE lineages (
    lineage_id TEXT PRIMARY KEY,
    created_at TEXT NOT NULL,
    status TEXT NOT NULL CHECK (status IN ('active', 'retired')),
    head_revision_id TEXT
);

CREATE TABLE revisions (
    revision_id TEXT PRIMARY KEY,
    lineage_id TEXT NOT NULL REFERENCES lineages(lineage_id),
    parent_revision_id TEXT REFERENCES revisions(revision_id),
    payload_json TEXT NOT NULL
);
CREATE INDEX revisions_lineage_idx ON revisions(lineage_id);

CREATE TABLE substrates (
    substrate_id TEXT PRIMARY KEY,
    payload_json TEXT NOT NULL
);

CREATE TABLE fit_decisions (
    fit_decision_id TEXT PRIMARY KEY,
    lineage_id TEXT NOT NULL REFERENCES lineages(lineage_id),
    source_revision_id TEXT NOT NULL REFERENCES revisions(revision_id),
    payload_json TEXT NOT NULL
);

CREATE TABLE projections (
    projection_id TEXT PRIMARY KEY,
    lineage_id TEXT NOT NULL REFERENCES lineages(lineage_id),
    source_revision_id TEXT NOT NULL REFERENCES revisions(revision_id),
    target_substrate_id TEXT NOT NULL REFERENCES substrates(substrate_id),
    payload_json TEXT NOT NULL
);

CREATE TABLE activations (
    activation_id TEXT PRIMARY KEY,
    lineage_id TEXT NOT NULL REFERENCES lineages(lineage_id),
    revision_id TEXT NOT NULL REFERENCES revisions(revision_id),
    substrate_id TEXT NOT NULL REFERENCES substrates(substrate_id),
    state TEXT NOT NULL CHECK (
        state IN ('pending', 'active', 'suspended', 'completed', 'failed', 'retired')
    ),
    started_at TEXT NOT NULL,
    ended_at TEXT
);
CREATE INDEX activations_lineage_idx ON activations(lineage_id);

CREATE TABLE leases (
    lease_id TEXT PRIMARY KEY,
    lineage_id TEXT NOT NULL REFERENCES lineages(lineage_id),
    head_revision_id TEXT NOT NULL REFERENCES revisions(revision_id),
    activation_id TEXT NOT NULL REFERENCES activations(activation_id),
    status TEXT NOT NULL CHECK (status IN ('active', 'closed')),
    issued_at TEXT NOT NULL,
    closed_at TEXT
);
CREATE UNIQUE INDEX one_active_lease_per_lineage
    ON leases(lineage_id) WHERE status = 'active';

CREATE TABLE handoffs (
    handoff_id TEXT PRIMARY KEY,
    lineage_id TEXT NOT NULL REFERENCES lineages(lineage_id),
    source_revision_id TEXT NOT NULL REFERENCES revisions(revision_id),
    source_activation_id TEXT NOT NULL REFERENCES activations(activation_id),
    source_lease_id TEXT NOT NULL REFERENCES leases(lease_id),
    target_substrate_id TEXT NOT NULL REFERENCES substrates(substrate_id),
    fit_decision_id TEXT NOT NULL REFERENCES fit_decisions(fit_decision_id),
    projection_id TEXT NOT NULL REFERENCES projections(projection_id),
    payload_json TEXT NOT NULL
);

CREATE TABLE handoff_results (
    handoff_result_id TEXT PRIMARY KEY,
    handoff_id TEXT NOT NULL UNIQUE REFERENCES handoffs(handoff_id),
    lineage_id TEXT NOT NULL REFERENCES lineages(lineage_id),
    target_activation_id TEXT NOT NULL REFERENCES activations(activation_id),
    disposition TEXT NOT NULL CHECK (disposition IN ('accepted', 'rejected')),
    payload_json TEXT NOT NULL
);

CREATE TABLE authority_transitions (
    transition_id TEXT PRIMARY KEY,
    lineage_id TEXT NOT NULL REFERENCES lineages(lineage_id),
    from_activation_id TEXT REFERENCES activations(activation_id),
    to_activation_id TEXT NOT NULL REFERENCES activations(activation_id),
    from_lease_id TEXT REFERENCES leases(lease_id),
    to_lease_id TEXT NOT NULL REFERENCES leases(lease_id),
    handoff_id TEXT REFERENCES handoffs(handoff_id),
    handoff_result_id TEXT REFERENCES handoff_results(handoff_result_id),
    resulting_revision_id TEXT NOT NULL REFERENCES revisions(revision_id),
    occurred_at TEXT NOT NULL
);

CREATE TABLE artifacts (
    artifact_id TEXT PRIMARY KEY,
    record_kind TEXT NOT NULL,
    record_id TEXT NOT NULL,
    relative_path TEXT NOT NULL UNIQUE,
    content_sha256 TEXT NOT NULL,
    created_at TEXT NOT NULL
);

CREATE TRIGGER revisions_no_update BEFORE UPDATE ON revisions
BEGIN SELECT RAISE(ABORT, 'immutable revisions cannot be updated'); END;
CREATE TRIGGER revisions_no_delete BEFORE DELETE ON revisions
BEGIN SELECT RAISE(ABORT, 'immutable revisions cannot be deleted'); END;
CREATE TRIGGER fit_decisions_no_update BEFORE UPDATE ON fit_decisions
BEGIN SELECT RAISE(ABORT, 'immutable fit decisions cannot be updated'); END;
CREATE TRIGGER fit_decisions_no_delete BEFORE DELETE ON fit_decisions
BEGIN SELECT RAISE(ABORT, 'immutable fit decisions cannot be deleted'); END;
CREATE TRIGGER projections_no_update BEFORE UPDATE ON projections
BEGIN SELECT RAISE(ABORT, 'immutable projections cannot be updated'); END;
CREATE TRIGGER projections_no_delete BEFORE DELETE ON projections
BEGIN SELECT RAISE(ABORT, 'immutable projections cannot be deleted'); END;
CREATE TRIGGER handoffs_no_update BEFORE UPDATE ON handoffs
BEGIN SELECT RAISE(ABORT, 'immutable handoff snapshots cannot be updated'); END;
CREATE TRIGGER handoffs_no_delete BEFORE DELETE ON handoffs
BEGIN SELECT RAISE(ABORT, 'immutable handoff snapshots cannot be deleted'); END;
CREATE TRIGGER handoff_results_no_update BEFORE UPDATE ON handoff_results
BEGIN SELECT RAISE(ABORT, 'immutable handoff results cannot be updated'); END;
CREATE TRIGGER handoff_results_no_delete BEFORE DELETE ON handoff_results
BEGIN SELECT RAISE(ABORT, 'immutable handoff results cannot be deleted'); END;
CREATE TRIGGER artifacts_no_update BEFORE UPDATE ON artifacts
BEGIN SELECT RAISE(ABORT, 'immutable artifact metadata cannot be updated'); END;
CREATE TRIGGER artifacts_no_delete BEFORE DELETE ON artifacts
BEGIN SELECT RAISE(ABORT, 'immutable artifact metadata cannot be deleted'); END;
"""

_MIGRATION_2 = """
CREATE TABLE thread_lineage_bindings (
    link_id TEXT PRIMARY KEY,
    thread_id TEXT NOT NULL UNIQUE,
    lineage_id TEXT NOT NULL REFERENCES lineages(lineage_id),
    relationship TEXT NOT NULL CHECK (relationship = 'thread_carried_by_lineage'),
    payload_json TEXT NOT NULL
);
CREATE INDEX thread_lineage_bindings_lineage_idx
    ON thread_lineage_bindings(lineage_id);

CREATE TABLE thread_checkpoint_decisions (
    decision_id TEXT PRIMARY KEY,
    thread_id TEXT NOT NULL REFERENCES thread_lineage_bindings(thread_id),
    lineage_id TEXT NOT NULL REFERENCES lineages(lineage_id),
    checkpoint_ref TEXT NOT NULL,
    checkpoint_sha256 TEXT NOT NULL,
    disposition TEXT NOT NULL CHECK (disposition IN ('accepted', 'rejected')),
    payload_json TEXT NOT NULL
);
CREATE INDEX thread_checkpoint_decisions_thread_idx
    ON thread_checkpoint_decisions(thread_id);
CREATE INDEX thread_checkpoint_decisions_lineage_idx
    ON thread_checkpoint_decisions(lineage_id);

CREATE TABLE thread_accepted_heads (
    thread_id TEXT PRIMARY KEY REFERENCES thread_lineage_bindings(thread_id),
    lineage_id TEXT NOT NULL REFERENCES lineages(lineage_id),
    decision_id TEXT REFERENCES thread_checkpoint_decisions(decision_id),
    checkpoint_ref TEXT,
    checkpoint_sha256 TEXT,
    updated_at TEXT,
    CHECK (
        (decision_id IS NULL AND checkpoint_ref IS NULL AND checkpoint_sha256 IS NULL)
        OR
        (decision_id IS NOT NULL AND checkpoint_ref IS NOT NULL AND checkpoint_sha256 IS NOT NULL)
    )
);

CREATE TRIGGER thread_lineage_bindings_no_update
BEFORE UPDATE ON thread_lineage_bindings
BEGIN SELECT RAISE(ABORT, 'immutable thread lineage bindings cannot be updated'); END;
CREATE TRIGGER thread_lineage_bindings_no_delete
BEFORE DELETE ON thread_lineage_bindings
BEGIN SELECT RAISE(ABORT, 'immutable thread lineage bindings cannot be deleted'); END;
CREATE TRIGGER thread_checkpoint_decisions_no_update
BEFORE UPDATE ON thread_checkpoint_decisions
BEGIN SELECT RAISE(ABORT, 'immutable checkpoint decisions cannot be updated'); END;
CREATE TRIGGER thread_checkpoint_decisions_no_delete
BEFORE DELETE ON thread_checkpoint_decisions
BEGIN SELECT RAISE(ABORT, 'immutable checkpoint decisions cannot be deleted'); END;
"""

_MIGRATION_3 = """
CREATE TABLE thread_continuation_grants (
    grant_id TEXT PRIMARY KEY,
    thread_id TEXT NOT NULL REFERENCES thread_lineage_bindings(thread_id),
    lineage_id TEXT NOT NULL REFERENCES lineages(lineage_id),
    checkpoint_ref TEXT NOT NULL,
    checkpoint_sha256 TEXT NOT NULL,
    operation_name TEXT NOT NULL,
    proposal_sha256 TEXT NOT NULL,
    activation_id TEXT NOT NULL REFERENCES activations(activation_id),
    lease_id TEXT NOT NULL REFERENCES leases(lease_id),
    lineage_head_revision_id TEXT NOT NULL REFERENCES revisions(revision_id),
    payload_json TEXT NOT NULL
);
CREATE INDEX thread_continuation_grants_thread_idx
    ON thread_continuation_grants(thread_id);
CREATE INDEX thread_continuation_grants_lineage_idx
    ON thread_continuation_grants(lineage_id);

CREATE TRIGGER thread_continuation_grants_no_update
BEFORE UPDATE ON thread_continuation_grants
BEGIN SELECT RAISE(ABORT, 'immutable continuation grants cannot be updated'); END;
CREATE TRIGGER thread_continuation_grants_no_delete
BEFORE DELETE ON thread_continuation_grants
BEGIN SELECT RAISE(ABORT, 'immutable continuation grants cannot be deleted'); END;
"""

_MIGRATION_4 = """
CREATE TABLE thread_close_intents (
    close_intent_id TEXT PRIMARY KEY,
    thread_id TEXT NOT NULL REFERENCES thread_lineage_bindings(thread_id),
    lineage_id TEXT NOT NULL REFERENCES lineages(lineage_id),
    expected_manifest_id TEXT NOT NULL,
    activation_id TEXT NOT NULL REFERENCES activations(activation_id),
    lease_id TEXT NOT NULL REFERENCES leases(lease_id),
    lineage_head_revision_id TEXT NOT NULL REFERENCES revisions(revision_id),
    issued_at TEXT NOT NULL,
    expires_at TEXT NOT NULL,
    payload_json TEXT NOT NULL
);
CREATE INDEX thread_close_intents_thread_idx
    ON thread_close_intents(thread_id, issued_at, close_intent_id);

CREATE TABLE thread_close_results (
    close_result_id TEXT PRIMARY KEY,
    close_intent_id TEXT NOT NULL UNIQUE REFERENCES thread_close_intents(close_intent_id),
    thread_id TEXT NOT NULL REFERENCES thread_lineage_bindings(thread_id),
    lineage_id TEXT NOT NULL REFERENCES lineages(lineage_id),
    manifest_ref TEXT NOT NULL,
    manifest_sha256 TEXT NOT NULL,
    owner_receipt_ref TEXT NOT NULL,
    owner_receipt_sha256 TEXT NOT NULL,
    completed_at TEXT NOT NULL,
    payload_json TEXT NOT NULL
);
CREATE INDEX thread_close_results_thread_idx
    ON thread_close_results(thread_id, completed_at, close_result_id);

CREATE TRIGGER thread_close_intents_no_update
BEFORE UPDATE ON thread_close_intents
BEGIN SELECT RAISE(ABORT, 'immutable close intents cannot be updated'); END;
CREATE TRIGGER thread_close_intents_no_delete
BEFORE DELETE ON thread_close_intents
BEGIN SELECT RAISE(ABORT, 'immutable close intents cannot be deleted'); END;
CREATE TRIGGER thread_close_results_no_update
BEFORE UPDATE ON thread_close_results
BEGIN SELECT RAISE(ABORT, 'immutable close results cannot be updated'); END;
CREATE TRIGGER thread_close_results_no_delete
BEFORE DELETE ON thread_close_results
BEGIN SELECT RAISE(ABORT, 'immutable close results cannot be deleted'); END;
"""

_LATEST_SCHEMA_VERSION = 4


class Store:
    """Owns a single local TORC SQLite database."""

    def __init__(
        self,
        state_dir: Path | str,
        *,
        read_only: bool = False,
        must_exist: bool = False,
    ):
        self.state_dir = Path(state_dir).resolve()
        self.db_path = self.state_dir / "torc.sqlite3"
        self.read_only = read_only
        if (read_only or must_exist) and not self.db_path.is_file():
            raise NotFoundError(f"TORC database not found: {self.db_path}")
        if read_only:
            self.connection = sqlite3.connect(
                f"{self.db_path.as_uri()}?mode=ro", uri=True
            )
        else:
            self.state_dir.mkdir(parents=True, exist_ok=True)
            self.connection = sqlite3.connect(self.db_path)
        self.connection.row_factory = sqlite3.Row
        self.connection.execute("PRAGMA foreign_keys = ON")
        if read_only:
            self.connection.execute("PRAGMA query_only = ON")
            version = int(
                self.connection.execute("PRAGMA user_version").fetchone()[0]
            )
            if version != _LATEST_SCHEMA_VERSION:
                self.connection.close()
                raise SchemaVersionError(
                    f"unsupported TORC database schema version: {version} "
                    f"(expected {_LATEST_SCHEMA_VERSION}; read-only commands never migrate)"
                )
        else:
            self.migrate()

    def close(self) -> None:
        self.connection.close()

    def __enter__(self) -> Store:
        return self

    def __exit__(self, *_args: object) -> None:
        self.close()

    def migrate(self) -> None:
        version = int(self.connection.execute("PRAGMA user_version").fetchone()[0])
        if version > _LATEST_SCHEMA_VERSION:
            raise SchemaVersionError(
                f"unsupported TORC database schema version: {version}"
            )
        if version == 0:
            self._apply_migration(_MIGRATION_1, target_version=1)
            version = 1
        if version == 1:
            self._apply_migration(_MIGRATION_2, target_version=2)
            version = 2
        if version == 2:
            self._apply_migration(_MIGRATION_3, target_version=3)
            version = 3
        if version == 3:
            self._apply_migration(_MIGRATION_4, target_version=4)

    def _apply_migration(self, script: str, *, target_version: int) -> None:
        try:
            self.connection.executescript(
                "BEGIN IMMEDIATE;\n"
                f"{script}\n"
                f"PRAGMA user_version = {int(target_version)};\n"
                "COMMIT;"
            )
        except BaseException:
            self.connection.rollback()
            raise

    @contextmanager
    def transaction(self, *, immediate: bool = False) -> Iterator[sqlite3.Connection]:
        if self.connection.in_transaction:
            yield self.connection
            return
        if immediate:
            self.connection.execute("BEGIN IMMEDIATE")
        try:
            yield self.connection
        except BaseException:
            self.connection.rollback()
            raise
        else:
            self.connection.commit()

    @contextmanager
    def read_transaction(self) -> Iterator[sqlite3.Connection]:
        """Hold one consistent SQLite snapshot and always leave it unchanged."""

        if self.connection.in_transaction:
            yield self.connection
            return
        self.connection.execute("BEGIN")
        try:
            yield self.connection
        finally:
            self.connection.rollback()

    @staticmethod
    def _decode(row: sqlite3.Row | None, label: str) -> dict[str, Any]:
        if row is None:
            raise NotFoundError(f"{label} not found")
        return json.loads(row["payload_json"])

    def create_lineage(
        self,
        lineage_id: str,
        canonical_state: dict[str, Any],
        *,
        revision_id: str | None = None,
        created_at: str | None = None,
    ) -> dict[str, Any]:
        revision_id = revision_id or new_id("revision")
        created_at = created_at or utc_now()
        record = seal_record(
            {
                "schema_version": 1,
                "lineage_id": lineage_id,
                "revision_id": revision_id,
                "parent_revision_ids": [],
                "created_at": created_at,
                "event_type": "lineage_created",
                "actor": {
                    "kind": "operator",
                    "activation_id": None,
                    "substrate_id": None,
                },
                "canonical_state": canonical_state,
                "evidence_refs": ["evidence-operator-decision"],
            },
            previous_revision_sha256=None,
        )
        with self.transaction():
            self.connection.execute(
                "INSERT INTO lineages VALUES (?, ?, 'active', ?)",
                (lineage_id, created_at, revision_id),
            )
            self._insert_revision(record)
        return record

    def _insert_revision(self, record: dict[str, Any]) -> None:
        parents = record["parent_revision_ids"]
        self.connection.execute(
            "INSERT INTO revisions VALUES (?, ?, ?, ?)",
            (
                record["revision_id"],
                record["lineage_id"],
                parents[0] if parents else None,
                canonical_json(record),
            ),
        )

    def append_revision(
        self,
        lineage_id: str,
        canonical_state: dict[str, Any],
        *,
        event_type: str,
        activation_id: str,
        evidence_refs: list[str] | None = None,
        revision_id: str | None = None,
        created_at: str | None = None,
    ) -> dict[str, Any]:
        authority = self.current_authority(lineage_id)
        if authority["activation_id"] != activation_id:
            raise LeaseConflictError("activation does not hold the authoritative lease")
        parent = self.get_revision(authority["lineage_head_revision_id"])
        activation = self.get_activation(activation_id)
        record = seal_record(
            {
                "schema_version": 1,
                "lineage_id": lineage_id,
                "revision_id": revision_id or new_id("revision"),
                "parent_revision_ids": [parent["revision_id"]],
                "created_at": created_at or utc_now(),
                "event_type": event_type,
                "actor": {
                    "kind": "activation",
                    "activation_id": activation_id,
                    "substrate_id": activation["substrate_id"],
                },
                "canonical_state": canonical_state,
                "evidence_refs": evidence_refs or [],
            },
            previous_revision_sha256=parent["integrity"]["canonical_payload_sha256"],
        )
        with self.transaction():
            current = self.current_authority(lineage_id)
            if current["activation_id"] != activation_id:
                raise LeaseConflictError("authority changed before revision append")
            self._insert_revision(record)
            self.connection.execute(
                "UPDATE lineages SET head_revision_id = ? WHERE lineage_id = ?",
                (record["revision_id"], lineage_id),
            )
            self.connection.execute(
                "UPDATE leases SET head_revision_id = ? WHERE lease_id = ?",
                (record["revision_id"], current["lease_id"]),
            )
            self.connection.execute(
                "UPDATE activations SET revision_id = ? WHERE activation_id = ?",
                (record["revision_id"], activation_id),
            )
        return record

    def get_lineage(self, lineage_id: str) -> dict[str, Any]:
        row = self.connection.execute(
            "SELECT * FROM lineages WHERE lineage_id = ?", (lineage_id,)
        ).fetchone()
        if row is None:
            raise NotFoundError(f"lineage not found: {lineage_id}")
        return dict(row)

    def get_revision(self, revision_id: str) -> dict[str, Any]:
        row = self.connection.execute(
            "SELECT payload_json FROM revisions WHERE revision_id = ?", (revision_id,)
        ).fetchone()
        return self._decode(row, f"revision {revision_id}")

    def lineage_revisions(self, lineage_id: str) -> list[dict[str, Any]]:
        rows = self.connection.execute(
            "SELECT payload_json FROM revisions WHERE lineage_id = ? ORDER BY rowid",
            (lineage_id,),
        ).fetchall()
        return [json.loads(row["payload_json"]) for row in rows]

    def register_substrate(self, descriptor: dict[str, Any]) -> dict[str, Any]:
        with self.transaction():
            self.connection.execute(
                "INSERT INTO substrates VALUES (?, ?)",
                (descriptor["substrate_id"], canonical_json(descriptor)),
            )
        return descriptor

    def get_substrate(self, substrate_id: str) -> dict[str, Any]:
        row = self.connection.execute(
            "SELECT payload_json FROM substrates WHERE substrate_id = ?", (substrate_id,)
        ).fetchone()
        return self._decode(row, f"substrate {substrate_id}")

    def list_substrates(self) -> list[dict[str, Any]]:
        rows = self.connection.execute(
            "SELECT payload_json FROM substrates ORDER BY substrate_id"
        ).fetchall()
        return [json.loads(row["payload_json"]) for row in rows]

    def create_activation(
        self,
        lineage_id: str,
        revision_id: str,
        substrate_id: str,
        *,
        activation_id: str | None = None,
        state: str = "pending",
        started_at: str | None = None,
    ) -> dict[str, Any]:
        activation = {
            "activation_id": activation_id or new_id("activation"),
            "lineage_id": lineage_id,
            "revision_id": revision_id,
            "substrate_id": substrate_id,
            "state": state,
            "started_at": started_at or utc_now(),
            "ended_at": None,
        }
        with self.transaction():
            self.connection.execute(
                "INSERT INTO activations VALUES (?, ?, ?, ?, ?, ?, ?)",
                tuple(activation.values()),
            )
        return activation

    def get_activation(self, activation_id: str) -> dict[str, Any]:
        row = self.connection.execute(
            "SELECT * FROM activations WHERE activation_id = ?", (activation_id,)
        ).fetchone()
        if row is None:
            raise NotFoundError(f"activation not found: {activation_id}")
        return dict(row)

    def list_activations(self, lineage_id: str) -> list[dict[str, Any]]:
        rows = self.connection.execute(
            "SELECT * FROM activations WHERE lineage_id = ? ORDER BY started_at, activation_id",
            (lineage_id,),
        ).fetchall()
        return [dict(row) for row in rows]

    def acquire_lease(
        self,
        lineage_id: str,
        activation_id: str,
        *,
        lease_id: str | None = None,
        issued_at: str | None = None,
    ) -> dict[str, Any]:
        lease_id = lease_id or new_id("lease")
        issued_at = issued_at or utc_now()
        with self.transaction():
            lineage = self.get_lineage(lineage_id)
            activation = self.get_activation(activation_id)
            if activation["lineage_id"] != lineage_id:
                raise LeaseConflictError("activation belongs to a different lineage")
            try:
                self.connection.execute(
                    "INSERT INTO leases VALUES (?, ?, ?, ?, 'active', ?, NULL)",
                    (
                        lease_id,
                        lineage_id,
                        lineage["head_revision_id"],
                        activation_id,
                        issued_at,
                    ),
                )
            except sqlite3.IntegrityError as exc:
                raise LeaseConflictError(
                    f"lineage already has an active authoritative lease: {lineage_id}"
                ) from exc
            self.connection.execute(
                "UPDATE activations SET state = 'active' WHERE activation_id = ?",
                (activation_id,),
            )
            self.connection.execute(
                """INSERT INTO authority_transitions
                   VALUES (?, ?, NULL, ?, NULL, ?, NULL, NULL, ?, ?)""",
                (
                    new_id("transition"),
                    lineage_id,
                    activation_id,
                    lease_id,
                    lineage["head_revision_id"],
                    issued_at,
                ),
            )
        return self.get_lease(lease_id)

    def get_lease(self, lease_id: str) -> dict[str, Any]:
        row = self.connection.execute(
            "SELECT * FROM leases WHERE lease_id = ?", (lease_id,)
        ).fetchone()
        if row is None:
            raise NotFoundError(f"lease not found: {lease_id}")
        return dict(row)

    def current_authority(self, lineage_id: str) -> dict[str, Any]:
        row = self.connection.execute(
            """SELECT l.head_revision_id AS lineage_head_revision_id,
                      a.activation_id, a.substrate_id, x.lease_id
               FROM lineages l
               JOIN leases x ON x.lineage_id = l.lineage_id AND x.status = 'active'
               JOIN activations a ON a.activation_id = x.activation_id
               WHERE l.lineage_id = ?""",
            (lineage_id,),
        ).fetchone()
        if row is None:
            raise LeaseConflictError(f"lineage has no active authority: {lineage_id}")
        return dict(row)

    def insert_hashed_record(
        self,
        table: str,
        identifier: str,
        record: dict[str, Any],
    ) -> None:
        if table == "fit_decisions":
            columns = "fit_decision_id, lineage_id, source_revision_id, payload_json"
            values = (
                identifier,
                record["lineage_id"],
                record["source_revision_id"],
                canonical_json(record),
            )
        elif table == "projections":
            columns = (
                "projection_id, lineage_id, source_revision_id, "
                "target_substrate_id, payload_json"
            )
            values = (
                identifier,
                record["lineage_id"],
                record["source_revision_id"],
                record["target_substrate_id"],
                canonical_json(record),
            )
        else:
            raise ValueError(f"unsupported immutable record table: {table}")
        placeholders = ", ".join("?" for _ in values)
        with self.transaction():
            self.connection.execute(
                f"INSERT INTO {table} ({columns}) VALUES ({placeholders})", values
            )

    def get_hashed_record(
        self, table: str, id_column: str, identifier: str
    ) -> dict[str, Any]:
        allowed = {
            ("fit_decisions", "fit_decision_id"),
            ("projections", "projection_id"),
            ("handoffs", "handoff_id"),
            ("handoff_results", "handoff_result_id"),
        }
        if (table, id_column) not in allowed:
            raise ValueError("unsupported immutable record lookup")
        row = self.connection.execute(
            f"SELECT payload_json FROM {table} WHERE {id_column} = ?", (identifier,)
        ).fetchone()
        return self._decode(row, f"{table} record {identifier}")

    def list_hashed_records(self, table: str, lineage_id: str) -> list[dict[str, Any]]:
        if table not in {"fit_decisions", "projections", "handoffs", "handoff_results"}:
            raise ValueError("unsupported immutable record list")
        rows = self.connection.execute(
            f"SELECT payload_json FROM {table} WHERE lineage_id = ? ORDER BY rowid",
            (lineage_id,),
        ).fetchall()
        return [json.loads(row["payload_json"]) for row in rows]
