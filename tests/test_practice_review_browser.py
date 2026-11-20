"""Optional real Chromium exercise. All automated answers use an isolated practice file."""

import json
import os
import subprocess
import sys
from contextlib import contextmanager
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
LAUNCHER = ROOT / "experiments/continuation-review/practice_review.py"


@contextmanager
def serve(db):
    command = [sys.executable, str(LAUNCHER), "--port", "0", "--db", str(db),
               "--reviewer", "Browser verification"]
    env = {**os.environ, "PYTHONPATH": str(ROOT / "src")}
    with subprocess.Popen(command, env=env, stdout=subprocess.PIPE, text=True) as proc:
        try:
            line = proc.stdout.readline()
            assert line.startswith("Practice page: http://127.0.0.1:"), line
            yield line.split()[-1]
        finally:
            proc.terminate()
            proc.wait(timeout=10)


def fill_ratings(page):
    for group in page.locator(".rating").all():
        group.get_by_text("Cannot judge", exact=True).click()
    page.get_by_text("Insufficient evidence", exact=True).click()


def test_practice_in_chromium_after_restart(tmp_path):
    api = pytest.importorskip("playwright.sync_api")
    db = tmp_path / "browser-verification.sqlite3"
    errors = []
    with api.sync_playwright() as engine:
        if not Path(engine.chromium.executable_path).is_file():
            pytest.skip("Playwright Chromium is not installed")
        browser = engine.chromium.launch(executable_path=engine.chromium.executable_path)
        with serve(db) as url:
            page = browser.new_page(viewport={"width": 1280, "height": 900})
            page.on("pageerror", lambda error: errors.append(str(error)))
            page.goto(url)
            api.expect(page.get_by_role("heading", level=1)).to_have_text("Export a reading list")
            title_question = "Does the first Title cell contain the whole title “Winter, Again”?"
            api.expect(page.get_by_role("group", name=title_question, exact=True)).to_have_count(2)
            sheets = page.get_by_role("table", name="How this download opens")
            first_rows = [sheet.locator("tbody tr").first.locator("td").all_text_contents()
                          for sheet in sheets.all()]
            assert sorted(first_rows) == [
                ["Winter", " Again", "Ada Vale"], ["Winter, Again", "Ada Vale"],
            ]
            page.screenshot(path=tmp_path / "desktop.png")
            for private_file in ("practice.json", "practice.sqlite3", "practice_review.py"):
                assert page.request.get(url + private_file).status == 404
            sides = page.locator(".output").all_text_contents()
            page.get_by_text("Changes and evidence").first.click()
            api.expect(page.locator(".evidence").first).to_be_visible()
            stale = browser.new_page()
            stale.goto(url)
            api.expect(stale.locator("#save-state")).to_have_text("No answers yet")
            page.get_by_text("Partly", exact=True).first.click()
            api.expect(page.locator("#save-state")).to_have_text("Saved · revision 1")
            stale.get_by_text("Yes", exact=True).first.click()
            api.expect(stale.get_by_role("alert")).to_contain_text("newer revision")
            stale.close()
            page.locator("#reason").fill("Automated draft.")
            page.get_by_role("button", name="02 Reschedule", exact=False).click()
            api.expect(page.locator("h1")).to_have_text("Reschedule a pickup reminder")
            api.expect(page.locator("#interruption")).to_contain_text(
                "move Saturday and Sunday reminders to Friday"
            )
            calendars = page.get_by_role("table", name="What appears on the calendar")
            api.expect(calendars).to_have_count(2)
            for table in calendars.all():
                sunday = table.locator("tbody tr").nth(1).locator("td").all_text_contents()
                assert sunday[:2] == ["Sunday 16:30", "Friday 16:30"]
            api.expect(page.get_by_role("group", name="Did both weekend pickups move to Friday?",
                                        exact=True)).to_have_count(2)
            page.reload()
            api.expect(page.locator("h1")).to_have_text("Reschedule a pickup reminder")
            page.close()
        # A new server process and browser context have no in-memory or browser-store answers.
        with serve(db) as url:
            page = browser.new_page(viewport={"width": 390, "height": 844})
            page.on("pageerror", lambda error: errors.append(str(error)))
            page.goto(url)
            api.expect(page.locator("h1")).to_have_text("Export a reading list")
            api.expect(page.get_by_role("radio", name="Partly", exact=True).first).to_be_checked()
            api.expect(page.locator("#reason")).to_have_value("Automated draft.")
            assert page.locator(".output").all_text_contents() == sides
            assert page.evaluate("document.documentElement.scrollWidth <= innerWidth")
            page.screenshot(path=tmp_path / "mobile.png")
            page.route("**/api/save", lambda route: route.abort())
            page.get_by_text("Cannot judge", exact=True).first.click()
            api.expect(page.get_by_role("alert")).to_contain_text("unsaved answers")
            page.unroute("**/api/save")
            page.get_by_role("button", name="Retry save").click()
            api.expect(page.get_by_role("alert")).to_be_hidden()
            fill_ratings(page)
            page.locator("#preference").scroll_into_view_if_needed()
            page.screenshot(path=tmp_path / "mobile-ratings.png")
            page.locator("#reason").fill("")
            page.get_by_role("button", name="Submit review").click()
            assert not page.locator("#reason").evaluate("(field) => field.checkValidity()")
            page.locator("#reason").fill("Automated submission.")
            page.get_by_role("button", name="Submit review").click()
            api.expect(page.locator("h1")).to_have_text("Reschedule a pickup reminder")
            fill_ratings(page)
            page.locator("#reason").fill("Second automated submission.")
            page.get_by_role("button", name="Submit review").click()
            api.expect(page.locator("#finish-title")).to_have_text("Both reviews are submitted")
            page.get_by_role("button", name="Revise answers").click()
            page.locator("#reason").fill("Revised automated submission.")
            page.get_by_role("button", name="Submit review").click()
            page.get_by_role("button", name="Lock practice batch").click()
            page.get_by_role("button", name="Keep editing").click()
            api.expect(page.get_by_role("button", name="Revise answers")).to_be_visible()
            page.get_by_role("button", name="Lock practice batch").click()
            page.get_by_role("button", name="Lock both reviews").click()
            api.expect(page.locator("#finish-title")).to_have_text("Practice batch locked")
            page.reload()
            api.expect(page.locator("#save-state")).to_have_text("Batch locked")
            api.expect(page.get_by_role("radio").first).to_be_disabled()
            with page.expect_download() as download:
                page.get_by_role("link", name="Export answers").click()
            export = json.loads(download.value.path().read_text(encoding="utf-8"))
            assert export["reviewer"] == "Browser verification"
            assert export["mode"] == "practice" and export["locked_at"]
            for card in export["cards"]:
                assert card["status"] == "submitted"
                assert all(row["binding"] == card["binding"] for row in card["history"])
            second = export["cards"][1]["history"]
            reasons = [row["answers"]["reason"] for row in second if row["status"] == "submitted"]
            assert reasons == ["Second automated submission.", "Revised automated submission."]
            assert not errors
            page.close()
        browser.close()
