"""Standalone read-only HTML projection of an accepted project snapshot."""

from __future__ import annotations

import json
from html import escape
from typing import Any


def _text(value: Any) -> str:
    if isinstance(value, str):
        return escape(value)
    return escape(json.dumps(value, ensure_ascii=False, sort_keys=True))


def _items(title: str, records: list[dict[str, Any]], summary_key: str) -> str:
    items = "".join(
        f"<li><strong>{_text(record.get(summary_key, ''))}</strong>"
        f" <small>{_text(record.get('status', ''))}</small></li>"
        for record in records
    )
    empty = "<li>None recorded</li>"
    return f"<section><h2>{escape(title)}</h2><ul>{items or empty}</ul></section>"


def _claim_item(item: dict[str, Any]) -> str:
    source_ids = ", ".join(
        reference["source_id"] for reference in item.get("evidence", [])
    )
    return (
        "<li>"
        f"<strong>{_text(item['subject'])}.{_text(item['predicate'])}</strong>"
        f" = {_text(item['value'])} <small>{_text(item['status'])}</small>"
        f"<div>evidence: {_text(source_ids or 'none')}</div>"
        "</li>"
    )


def render_snapshot_html(snapshot: dict[str, Any], receipt: dict[str, Any]) -> str:
    repositories = "".join(
        f"<li><code>{_text(item['repository'])}</code> at "
        f"<code>{_text(item['commit'])}</code></li>"
        for item in snapshot.get("scope", {}).get("repositories", [])
    )
    projects = "".join(
        f"<li><strong>{_text(item['name'])}</strong>: {_text(item['status'])}</li>"
        for item in snapshot.get("projects", [])
    )
    claims = "".join(_claim_item(item) for item in snapshot.get("claims", []))
    checks = "".join(
        f"<li>{_text(item['name'])}: {_text(item['status'])} — {_text(item['detail'])}</li>"
        for item in receipt.get("checks", [])
    )
    empty = "<li>None recorded</li>"
    bundle_id = snapshot.get("evidence_bundle", {}).get("bundle_id")
    body = "".join(
        [
            f"<header><h1>{_text(snapshot.get('scope', {}).get('name', 'Project Snapshot'))}</h1>",
            f"<p>Snapshot: {_text(snapshot.get('generated_at'))}</p>",
            f"<p>Acceptance: {_text(receipt.get('status'))}</p></header>",
            f"<section><h2>Source repositories</h2><ul>{repositories}</ul></section>",
            f"<section><h2>Projects</h2><ul>{projects or empty}</ul></section>",
            "<section><h2>Verified claims and interpretations</h2>"
            f"<ul>{claims or empty}</ul></section>",
            _items("Blockers", snapshot.get("blockers", []), "summary"),
            _items("Pending decisions", snapshot.get("pending_decisions", []), "summary"),
            _items("Recent activity", snapshot.get("recent_activity", []), "summary"),
            _items("Conflicts", snapshot.get("conflicts", []), "summary"),
            _items("Unknowns", snapshot.get("unknowns", []), "summary"),
            "<section><h2>Evidence provenance</h2><p>Bundle: "
            f"<code>{_text(bundle_id)}</code></p></section>",
            f"<section><h2>Acceptance checks</h2><ul>{checks}</ul></section>",
        ]
    )
    return (
        '<!doctype html><html lang="en"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width,initial-scale=1">'
        "<title>Project Snapshot</title><style>"
        "body{font:16px system-ui;max-width:72rem;margin:auto;padding:2rem;"
        "color:#172033;background:#f7f8fb}"
        "header,section{background:white;border:1px solid #dce1ea;"
        "border-radius:.6rem;padding:1rem;margin:1rem 0}"
        "code{overflow-wrap:anywhere}small{color:#526079}li{margin:.4rem 0}"
        "</style></head><body>"
        f"{body}</body></html>"
    )
