"""Local adapter for offering verified lineages and assigning them to Dias Boards."""

from __future__ import annotations

import argparse
import hashlib
import http.client
import json
import os
import re
from pathlib import Path
from typing import Any
from urllib.parse import quote

from .errors import InvalidInputError
from .holder import PUBLIC_LABEL, publish_holder, write_display_file
from .store import Store


def _home() -> Path:
    configured = os.environ.get("TORC_BOARD_HOME")
    return Path(configured).resolve() if configured else Path.home() / ".torc" / "board"


def _hash(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def workspace(project: str) -> dict:
    if not re.fullmatch(r"[A-Za-z0-9._:-]{1,64}", project):
        raise InvalidInputError("Choose a registered Dias project ID.")
    return {
        "state_dir": str(_home() / "workspaces" / _hash(project)),
        "lineage_id": "board-" + project,
        "project_id": project,
    }


def offer(state_dir: Path, lineage: str, label: str) -> dict:
    if not PUBLIC_LABEL.fullmatch(label):
        raise InvalidInputError("Choose a public name of 1–32 letters, digits, spaces or hyphens.")
    with Store(state_dir, must_exist=True) as store:
        report = publish_holder(store, lineage)
    key = _hash(os.path.normcase(str(report)))
    write_display_file(
        _home() / "offers" / (key + ".json"),
        {"schemaVersion": 1, "label": label, "holderFile": str(report)},
    )
    return {"source_id": key, "label": label}


def _request(port: int, route: str, body: dict | None = None) -> dict:
    if not 1 <= port <= 65535:
        raise InvalidInputError("Dias display port is invalid.")
    client = http.client.HTTPConnection("127.0.0.1", port, timeout=10)
    try:
        headers = {"Content-Type": "application/json", "x-dias-action-contract": "1"}
        client.request(
            "GET" if body is None else "PUT",
            "/api/v1/" + route,
            body=json.dumps(body) if body is not None else None,
            headers=headers,
        )
        response = client.getresponse()
        data = response.read(8 * 1024 * 1024 + 1)
        if response.status == 409:
            raise InvalidInputError("The Board assignment changed. Read it again before retrying.")
        if response.status != 200 or len(data) > 8 * 1024 * 1024:
            raise InvalidInputError(f"Dias could not confirm the request (HTTP {response.status}).")
        result = json.loads(data)
        if not isinstance(result, dict):
            raise InvalidInputError("Unexpected response from Dias.")
        return result
    except http.client.HTTPException as exc:
        raise InvalidInputError(
            "Dias interrupted the request. Read the Board before retrying."
        ) from exc
    finally:
        client.close()


def _one(rows: list[dict], name: str, key: str, kind: str) -> dict:
    exact = [row for row in rows if row[key] == name]
    matches = exact or [
        row
        for row in rows
        if name.casefold() in {str(row[key]).casefold(), str(row.get("label", "")).casefold()}
    ]
    if len(matches) != 1:
        raise InvalidInputError(f"Choose one {kind} from the Dias list. Matches: {len(matches)}.")
    return matches[0]


def _trail_board(port: int, trail: str, boards: list[dict]) -> str:
    feed = _request(port, "trails")
    if feed.get("source_status") != "current" or not isinstance(feed.get("model"), dict):
        raise InvalidInputError("Dias needs a current Work Trails report to resolve this trail.")
    matches = [
        row
        for row in feed["model"]["objectives"]
        if f"{row['namespace']}/{row['id']}".casefold() == trail.casefold()
    ]
    if not matches:
        matches = [
            row
            for row in feed["model"]["objectives"]
            if trail.casefold() in {row["id"].casefold(), (row.get("label") or "").casefold()}
        ]
    if not matches:
        raise InvalidInputError("No current Work Trail matches that name.")
    if len(matches) > 1:
        choices = ", ".join(f"{row['namespace']}/{row['id']}" for row in matches[:8])
        raise InvalidInputError(f"Choose a matching Work Trail: {choices}")
    row = matches[0]
    links = (row.get("content") or {}).get("links") or []
    ids = {
        link["to"]["store_id"]
        for link in links
        if link.get("relation") == "annotates_chip" and isinstance(link.get("to"), dict)
    }
    if not ids:
        objective = f"{row['namespace']}/{row['id']}"
        ids = {
            link["projectId"]
            for link in _request(port, "project-trail-links")["links"]
            if link["objective"] == objective
        }
    if not ids and any(b["projectId"] == row["namespace"] for b in boards):
        ids = {row["namespace"]}
    if len(ids) != 1 or not any(b["projectId"] in ids for b in boards):
        raise InvalidInputError("This trail has no single linked Board. Choose a Board by name.")
    return ids.pop()


def _here() -> str:
    root = Path.cwd().resolve()
    for folder in (root, *root.parents):
        ids = set()
        for filename in ("chips.json", "status.json"):
            source = folder / ".dias" / filename
            if source.is_file():
                data = json.loads(source.read_text(encoding="utf-8-sig"))
                if not isinstance(data, dict) or not isinstance(data.get("projectId"), str):
                    raise InvalidInputError("The workspace Board file has no valid project ID.")
                ids.add(data["projectId"])
        if len(ids) > 1:
            raise InvalidInputError("The workspace Board files disagree on the project ID.")
        if ids:
            return ids.pop()
        if (folder / ".git").exists():
            break
    raise InvalidInputError("This workspace has no Board ID. Choose a Board or a linked trail.")


def run_board(args: argparse.Namespace) -> dict[str, Any]:
    action = args.board_command
    if action == "workspace":
        return workspace(args.project)
    if action == "offer":
        return offer(args.state_dir, args.lineage, args.label)
    port = args.port if args.port is not None else int(os.environ.get("DIAS_DISPLAY_PORT", "4175"))
    catalog = _request(port, "torc-assignments")
    if catalog.get("schemaVersion") != 1:
        raise InvalidInputError("Dias returned an unknown assignment contract.")
    if action == "list":
        return catalog
    name = _here() if args.here else args.board
    if args.trail:
        name = _trail_board(port, args.trail, catalog["boards"])
    board = _one(catalog["boards"], name, "projectId", "Board")
    if args.here and board["projectId"] != name:
        raise InvalidInputError("The workspace Board ID is absent from Dias.")
    if action == "show":
        snapshot = _request(port, "chip-boards/" + quote(board["projectId"], safe=""))
        if snapshot.get("projectId") != board["projectId"]:
            raise InvalidInputError("Dias returned a different project Board.")
        source = next((s for s in catalog["sources"] if s["id"] == board["sourceId"]), {})
        return {**board, "sourceLabel": source.get("label"), "holder": snapshot.get("torcHolder")}
    target = (
        None if action == "remove" else _one(catalog["sources"], args.source, "id", "torc")["id"]
    )
    current = board["sourceId"]
    if action == "assign" and current is not None and current != target and not args.replace:
        raise InvalidInputError("The Board already follows another torc. Specify replacement.")
    result = _request(
        port,
        "torc-assignments",
        {
            "schemaVersion": 1,
            "projectId": board["projectId"],
            "expectedSourceId": current,
            "sourceId": target,
        },
    )
    saved = _one(result["boards"], board["projectId"], "projectId", "Board")
    if saved["sourceId"] != target:
        raise InvalidInputError("Dias did not confirm the requested assignment.")
    return saved


def add_board_parser(commands) -> None:
    parser = commands.add_parser("board", help="Manage the torc shown on a Dias project Board.")
    choices = parser.add_subparsers(dest="board_command", required=True)
    for name in ("list", "show", "assign", "remove", "offer", "workspace"):
        command = choices.add_parser(name)
        command.add_argument("--json", dest="as_json", action="store_true")
        if name == "workspace":
            command.add_argument("--project", required=True)
        elif name == "offer":
            command.add_argument("--state-dir", type=Path, required=True)
            command.add_argument("--lineage", required=True)
            command.add_argument("--label", required=True)
        else:
            command.add_argument("--port", type=int)
            if name != "list":
                target = command.add_mutually_exclusive_group(required=True)
                target.add_argument("--board")
                target.add_argument("--trail")
                target.add_argument(
                    "--here",
                    action="store_true",
                    help="Use the current workspace's authored Board ID.",
                )
            if name == "assign":
                command.add_argument("--source", default="workspace")
                command.add_argument("--replace", action="store_true")
