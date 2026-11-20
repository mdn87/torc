"""Run the local human-review practice desk from a TORC checkout."""

import argparse
import csv
import getpass
import io
import json
import secrets
import sqlite3
import sys
import webbrowser
from contextlib import closing, contextmanager
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from uuid import uuid4

from torc.canonical import canonical_json, payload_sha256, utc_now

HERE = Path(__file__).resolve().parent
DEFAULT_DB = HERE.parents[1] / ".torc" / "continuation-review" / "practice.sqlite3"
ASSETS = {
    "/": ("index.html", "text/html; charset=utf-8"),
    "/review.css": ("review.css", "text/css; charset=utf-8"),
    "/review.js": ("review.js", "text/javascript; charset=utf-8"),
}


class Conflict(ValueError):
    """A save would change the wrong version, reviewer, or locked batch."""


def card_binding(batch_id, rubric_hash, card):
    evidence = {key: value for key, value in card.items() if key != "binding"}
    return payload_sha256({"batch": batch_id, "rubric": rubric_hash, "card": evidence})


def displayed_result(variant, comparison):
    result = {key: variant[key] for key in ("behavior", "output", "change", "evidence")}
    if comparison is None:
        return result
    if comparison["format"] == "csv":
        rows = list(csv.reader(io.StringIO(result["output"], newline=""), strict=True))
    elif comparison["format"] == "schedule":
        header, *expected = comparison["expected"]
        rows = [[*header, "Returned pickup"]]
        for row, actual in zip(expected, result["output"].splitlines(), strict=True):
            rows.append([*row, " ".join(actual.split())])
    else:
        raise ValueError("Unknown practice comparison format.")
    return {**result, "display_rows": rows}


def freeze_practice(source):
    batch_id = str(uuid4())
    rubric_hash = payload_sha256(source["rubric"])
    cards = []
    for item in source["cards"]:
        card = {key: item[key] for key in (
            "id", "title", "request", "interruption", "success", "input_label", "input",
            "output_label",
        )}
        comparison = item.get("comparison")
        if comparison is not None:
            card["comparison"] = comparison
        first, second = (displayed_result(variant, comparison) for variant in item["variants"])
        if secrets.randbelow(2):
            first, second = second, first
        card["results"] = {"A": first, "B": second}
        card["artifact_sha256"] = {key: payload_sha256(v) for key, v in card["results"].items()}
        card["binding"] = card_binding(batch_id, rubric_hash, card)
        cards.append(card)
    return {"mode": "practice", "batch_id": batch_id, "rubric": source["rubric"],
            "rubric_sha256": rubric_hash, "cards": cards}


def blank_answers():
    return {"A": {}, "B": {}, "preference": "", "reason": ""}


def validate_answers(answers, rubric, submit):
    if not isinstance(answers, dict) or answers.keys() != blank_answers().keys():
        raise ValueError("The answer fields do not match this rubric.")
    criteria = {criterion["id"] for criterion in rubric["criteria"]}
    for side in ("A", "B"):
        ratings = answers[side]
        if not isinstance(ratings, dict) or ratings.keys() - criteria:
            raise ValueError("Unknown rating field.")
        if any(value not in rubric["ratings"] for value in ratings.values()):
            raise ValueError("Choose a listed rating.")
        if submit and ratings.keys() != criteria:
            raise ValueError(f"Answer all three questions for Result {side}.")
    preference, reason = answers["preference"], answers["reason"]
    if preference not in ["", *rubric["preferences"]]:
        raise ValueError("Choose a listed preference.")
    if not isinstance(reason, str) or len(reason) > 2000:
        raise ValueError("Keep the reason within 2,000 characters.")
    if submit and not preference:
        raise ValueError("Choose an overall preference.")
    needs_reason = preference in rubric["reason_preferences"] or any(
        value in rubric["reason_ratings"] for side in ("A", "B") for value in answers[side].values()
    )
    if submit and needs_reason and not reason.strip():
        raise ValueError("Add a short reason for this choice.")


class ReviewStore:
    def __init__(self, path, reviewer, source, *, previous_sources=()):
        if source["mode"] != "practice" or not reviewer.strip():
            raise ValueError("Choose a reviewer name and a practice batch.")
        self.path = path
        self.reviewer = reviewer.strip()
        self.current_interruptions = {card["id"]: card["interruption"] for card in source["cards"]}
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.transaction(write=True) as db:
            schema = db.execute("PRAGMA user_version").fetchone()[0]
            if schema == 0:
                if db.execute("SELECT 1 FROM sqlite_master LIMIT 1").fetchone():
                    raise Conflict("Choose a new file or an existing practice review database.")
                db.execute("""CREATE TABLE batch (
                    reviewer TEXT NOT NULL, source_sha256 TEXT NOT NULL, snapshot TEXT NOT NULL,
                    locked_at TEXT)""")
                db.execute("""CREATE TABLE revisions (
                    card_id TEXT NOT NULL, revision INTEGER NOT NULL, binding TEXT NOT NULL,
                    reviewer TEXT NOT NULL, saved_at TEXT NOT NULL, status TEXT NOT NULL,
                    answers TEXT NOT NULL, PRIMARY KEY (card_id, revision))""")
                snapshot = freeze_practice(source)
                db.execute("INSERT INTO batch VALUES (?, ?, ?, NULL)",
                           (self.reviewer, payload_sha256(source), canonical_json(snapshot)))
                db.execute("PRAGMA user_version = 1")
            elif schema != 1:
                raise Conflict("This practice review database uses a different schema.")
            row = db.execute("SELECT * FROM batch").fetchone()
            if row["reviewer"] != self.reviewer:
                raise Conflict("Reopen with the original reviewer name or choose a new --db file.")
            if row["source_sha256"] not in (payload_sha256(source), *previous_sources):
                raise Conflict("Practice evidence or rubric changed. Restore its version "
                               "to resume, or choose a new --db file.")
            self.snapshot = json.loads(row["snapshot"])
        rubric_hash = payload_sha256(self.snapshot["rubric"])
        if rubric_hash != self.snapshot["rubric_sha256"] or any(
            card_binding(self.snapshot["batch_id"], rubric_hash, card) != card["binding"]
            for card in self.snapshot["cards"]
        ):
            raise Conflict("The stored practice evidence has changed. Restore its saved copy.")
        self.cards = {card["id"]: card for card in self.snapshot["cards"]}

    @contextmanager
    def transaction(self, *, write=False):
        with closing(sqlite3.connect(self.path)) as db, db:
            db.row_factory = sqlite3.Row
            db.execute("BEGIN IMMEDIATE" if write else "BEGIN")
            yield db

    @staticmethod
    def latest(db, card_id):
        row = db.execute("""SELECT * FROM revisions WHERE card_id = ?
                            ORDER BY revision DESC LIMIT 1""", (card_id,)).fetchone()
        if row is None:
            return {"revision": 0, "status": "open", "answers": blank_answers(), "saved_at": None}
        return {"revision": row["revision"], "status": row["status"],
                "answers": json.loads(row["answers"]), "saved_at": row["saved_at"]}

    def view(self, *, history=False):
        with self.transaction() as db:
            locked_at = db.execute("SELECT locked_at FROM batch").fetchone()[0]
            cards = []
            for card in self.cards.values():
                item = {**card, **self.latest(db, card["id"])}
                current = self.current_interruptions[card["id"]]
                if locked_at and not history and current != card["interruption"]:
                    item["clarified_interruption"] = current
                if history:
                    rows = db.execute("SELECT * FROM revisions WHERE card_id = ? ORDER BY revision",
                                      (card["id"],))
                    item["history"] = [
                        {**row, "answers": json.loads(row["answers"])} for row in rows
                    ]
                cards.append(item)
            return {**self.snapshot, "reviewer": self.reviewer, "locked_at": locked_at,
                    "cards": cards}

    @staticmethod
    def check_open(db):
        if db.execute("SELECT locked_at FROM batch").fetchone()[0]:
            raise Conflict("This practice batch is locked. Reload to see the saved reviews.")

    def save(self, card_id, binding, base_revision, answers, submit):
        if not isinstance(card_id, str) or card_id not in self.cards:
            raise ValueError("Unknown practice case.")
        if binding != self.cards[card_id]["binding"]:
            raise Conflict("The displayed evidence changed. Reload before reviewing.")
        if type(base_revision) is not int or base_revision < 0 or type(submit) is not bool:
            raise ValueError("Invalid revision or submission.")
        validate_answers(answers, self.snapshot["rubric"], submit)
        status = "submitted" if submit else "draft"
        with self.transaction(write=True) as db:
            self.check_open(db)
            current = self.latest(db, card_id)
            revision = current["revision"]
            if (current["answers"] == answers and current["status"] == status
                    and base_revision in (revision, revision - 1)):
                return current
            if base_revision != revision:
                raise Conflict("A newer revision was saved in another tab. Reload to review it.")
            saved_at = utc_now()
            db.execute("INSERT INTO revisions VALUES (?, ?, ?, ?, ?, ?, ?)",
                       (card_id, revision + 1, binding, self.reviewer, saved_at, status,
                        canonical_json(answers)))
            return {"revision": revision + 1, "status": status, "answers": answers,
                    "saved_at": saved_at}

    def lock(self, batch_id, revisions):
        with self.transaction(write=True) as db:
            self.check_open(db)
            if batch_id != self.snapshot["batch_id"]:
                raise Conflict("The practice batch changed. Reload before locking.")
            latest = {key: self.latest(db, key) for key in self.cards}
            if any(entry["status"] != "submitted" for entry in latest.values()):
                raise ValueError("Submit both reviews before locking the batch.")
            if revisions != {key: item["revision"] for key, item in latest.items()}:
                raise Conflict("A review changed. Reload both saved reviews before locking.")
            locked_at = utc_now()
            db.execute("UPDATE batch SET locked_at = ?", (locked_at,))
            return {"locked_at": locked_at}


def make_server(store, port):
    class Handler(BaseHTTPRequestHandler):
        def reply(self, code, body, content_type="application/json", *, download=False):
            data = body if isinstance(body, bytes) else canonical_json(body).encode("utf-8")
            self.send_response(code)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(data)))
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("Content-Security-Policy", "default-src 'self'; img-src 'self' data:; "
                             "object-src 'none'; base-uri 'none'; frame-ancestors 'none'")
            if download:
                self.send_header("Content-Disposition",
                                 'attachment; filename="practice-review.json"')
            self.end_headers()
            self.wfile.write(data)

        def local_request(self, *, write=False):
            host = f"127.0.0.1:{self.server.server_port}"
            if self.headers.get("Host") != host or (
                write and self.headers.get("Origin") != f"http://{host}"
            ):
                self.reply(403, {"error": "Open the local address printed by the launcher."})
                return False
            return True

        def do_GET(self):
            if not self.local_request():
                return
            if self.path in ASSETS:
                filename, mime = ASSETS[self.path]
                self.reply(200, (HERE / filename).read_bytes(), mime)
            elif self.path in ("/api/review", "/api/export"):
                export = self.path == "/api/export"
                self.reply(200, store.view(history=export), download=export)
            else:
                self.reply(404, {"error": "Unknown page."})

        def do_POST(self):
            if not self.local_request(write=True):
                return
            if self.path not in ("/api/save", "/api/lock"):
                self.reply(404, {"error": "Unknown action."})
                return
            try:
                size = int(self.headers.get("Content-Length", "0"))
                if (self.headers.get_content_type() != "application/json" or not 0 < size <= 32768):
                    raise ValueError("Send a JSON review within the size limit.")
                data = json.loads(self.rfile.read(size))
                if not isinstance(data, dict):
                    raise ValueError("Expected a review object.")
                if self.path == "/api/save":
                    result = store.save(data["card_id"], data["binding"], data["base_revision"],
                                        data["answers"], data["submit"])
                else:
                    result = store.lock(data["batch_id"], data["revisions"])
            except Conflict as exc:
                self.reply(409, {"error": str(exc)})
            except (ValueError, KeyError) as exc:
                self.reply(400, {"error": str(exc)})
            except sqlite3.Error:
                self.reply(503, {"error": "Could not save to the local database. Try again."})
            else:
                self.reply(200, result)

    return ThreadingHTTPServer(("127.0.0.1", port), Handler)


def open_practice(path, reviewer):
    original = json.loads((HERE / "practice.json").read_text(encoding="utf-8"))
    revision = json.loads((HERE / "practice-rubric-v2.json").read_text(encoding="utf-8"))
    rubric = {key: original["rubric"][key] for key in (
        "ratings", "preferences", "reason_ratings", "reason_preferences",
    )}
    rubric.update(version=revision["version"], case_questions=revision["case_questions"],
                  criteria=[{"id": row["id"]} for row in original["rubric"]["criteria"]])
    cards = [{**card, "comparison": revision["comparisons"][card["id"]]}
             for card in original["cards"]]
    source = {**original, "rubric": rubric, "cards": cards}
    # Recognize the two shipped sources before applying the copy edit to new reviews.
    previous_sources = (payload_sha256(original), payload_sha256(source))
    for card in cards:
        if card["id"] in revision["interruptions"]:
            card["interruption"] = revision["interruptions"][card["id"]]
    return ReviewStore(path, reviewer, source, previous_sources=previous_sources)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--reviewer", default=getpass.getuser(), help="name recorded on each save")
    parser.add_argument("--db", type=Path, default=DEFAULT_DB, help="practice SQLite file")
    parser.add_argument("--port", type=int, default=8773,
                        help="loopback port, or 0 for any free port")
    parser.add_argument("--open", action="store_true", help="open the page in the default browser")
    args = parser.parse_args()
    try:
        store = open_practice(args.db, args.reviewer)
        with make_server(store, args.port) as server:
            url = f"http://127.0.0.1:{server.server_port}/"
            print(f"Practice page: {url}\nAnswers: {args.db.resolve()}", flush=True)
            if args.open:
                webbrowser.open(url)
            server.serve_forever()
    except KeyboardInterrupt:
        pass
    except (ValueError, OSError, sqlite3.Error) as exc:
        sys.exit(str(exc))


if __name__ == "__main__":
    main()
