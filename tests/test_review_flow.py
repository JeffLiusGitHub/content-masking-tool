"""Mandatory human review: MCP mask requests open the GUI and return a
review_id; masked text reaches Claude ONLY after the user confirms."""
import subprocess
import sys
import threading
import time

import pytest

from maskingtool import config, review


@pytest.fixture
def data_dir(tmp_path, monkeypatch):
    monkeypatch.setenv(config.DATA_DIR_ENV, str(tmp_path))
    monkeypatch.setenv("MASKINGTOOL_NO_GUI_SPAWN", "1")
    denylists = tmp_path / "denylists"
    denylists.mkdir()
    (tmp_path / "settings.json").write_text('{"enable_ner": false}', encoding="utf-8")
    (denylists / "people.csv").write_text("name\nJohn Smith\n", encoding="utf-8")
    (denylists / "companies.csv").write_text("name\nAcme Corp\n", encoding="utf-8")
    return tmp_path


class TestReviewStore:
    def test_create_then_status(self, data_dir, tmp_path):
        job = review.create_review(tmp_path / "doc.md")
        status = review.get_status(job["review_id"])
        assert status["status"] == "waiting_for_user"

    def test_complete_and_result(self, data_dir, tmp_path):
        job = review.create_review(tmp_path / "doc.md")
        review.complete_review(job["review_id"], {"vault_id": "v1"})
        assert review.get_status(job["review_id"])["status"] == "completed"
        assert review.get_result(job["review_id"])["vault_id"] == "v1"

    def test_cancel(self, data_dir, tmp_path):
        job = review.create_review(tmp_path / "doc.md")
        review.cancel_review(job["review_id"])
        assert review.get_status(job["review_id"])["status"] == "cancelled"
        with pytest.raises(ValueError):
            review.get_result(job["review_id"])

    def test_result_before_completion_raises(self, data_dir, tmp_path):
        job = review.create_review(tmp_path / "doc.md")
        with pytest.raises(ValueError):
            review.get_result(job["review_id"])

    def test_unknown_review_raises(self, data_dir):
        with pytest.raises(review.ReviewNotFoundError):
            review.get_status("20990101-000000-deadbeef")

    def test_dead_gui_pid_means_failed(self, data_dir, tmp_path):
        job = review.create_review(tmp_path / "doc.md")
        proc = subprocess.Popen([sys.executable, "-c", "pass"])
        proc.wait()
        review.set_gui_pid(job["review_id"], proc.pid)
        status = review.get_status(job["review_id"])
        assert status["status"] == "failed"
        assert "closed" in status["reason"]

    def test_live_gui_pid_stays_waiting(self, data_dir, tmp_path):
        import os

        job = review.create_review(tmp_path / "doc.md")
        review.set_gui_pid(job["review_id"], os.getpid())
        assert review.get_status(job["review_id"])["status"] == "waiting_for_user"


class TestWaitForDecision:
    """Long-poll: after the user clicks Confirm in the GUI, a pending
    get_review_status returns at once so Claude continues automatically."""

    def test_already_decided_returns_immediately(self, data_dir, tmp_path):
        job = review.create_review(tmp_path / "doc.md")
        review.complete_review(job["review_id"], {"vault_id": "v1"})
        start = time.monotonic()
        data = review.wait_for_decision(job["review_id"], timeout_s=30)
        assert data["status"] == "completed"
        assert time.monotonic() - start < 1

    def test_timeout_returns_waiting(self, data_dir, tmp_path):
        job = review.create_review(tmp_path / "doc.md")
        start = time.monotonic()
        data = review.wait_for_decision(job["review_id"], timeout_s=0.5)
        assert data["status"] == "waiting_for_user"
        assert 0.4 <= time.monotonic() - start < 5

    def test_confirm_mid_wait_unblocks(self, data_dir, tmp_path):
        job = review.create_review(tmp_path / "doc.md")
        rid = job["review_id"]

        def confirm_later():
            time.sleep(0.4)
            review.complete_review(rid, {"vault_id": "v1"})

        t = threading.Thread(target=confirm_later)
        t.start()
        start = time.monotonic()
        data = review.wait_for_decision(rid, timeout_s=30)
        t.join()
        assert data["status"] == "completed"
        assert time.monotonic() - start < 5  # returned on decision, not timeout

    def test_dead_gui_mid_wait_fails_fast(self, data_dir, tmp_path):
        job = review.create_review(tmp_path / "doc.md")
        proc = subprocess.Popen([sys.executable, "-c", "pass"])
        proc.wait()
        review.set_gui_pid(job["review_id"], proc.pid)
        start = time.monotonic()
        data = review.wait_for_decision(job["review_id"], timeout_s=30)
        assert data["status"] == "failed"
        assert time.monotonic() - start < 2

    def test_tool_wait_is_clamped_and_polls(self, data_dir, tmp_path):
        from maskingtool.mcp_server import tools

        doc = tmp_path / "doc.md"
        doc.write_text("x", encoding="utf-8")
        started = tools.mask_document(str(doc))
        review.complete_review(started.review_id, {
            "masked_file_path": str(doc), "vault_id": "v1",
        })
        # huge wait request is clamped and returns immediately once decided
        start = time.monotonic()
        out = tools.get_review_status(started.review_id, wait_seconds=9999)
        assert out.status == "completed"
        assert time.monotonic() - start < 1


class TestMandatoryReviewTools:
    def test_mask_document_returns_review_not_text(self, data_dir, tmp_path):
        from maskingtool.mcp_server import tools

        doc = tmp_path / "doc.md"
        doc.write_text("Acme Corp met John Smith.", encoding="utf-8")
        out = tools.mask_document(str(doc))
        dumped = out.model_dump()
        assert dumped["status"] == "waiting_for_user"
        assert dumped["review_id"]
        # THE guarantee: no masked_text (and certainly no originals) returned
        assert "masked_text" not in dumped
        assert "John Smith" not in str(dumped)

    def test_full_review_cycle(self, data_dir, tmp_path):
        from maskingtool.mcp_server import tools

        doc = tmp_path / "doc.md"
        doc.write_text("Acme Corp met John Smith.", encoding="utf-8")
        started = tools.mask_document(str(doc))
        rid = started.review_id

        assert tools.get_review_status(rid).status == "waiting_for_user"

        # simulate the human approving in the GUI
        masked_file = tmp_path / "doc.masked.md"
        masked_file.write_text("⟦ORG_001⟧ met ⟦PERSON_001⟧.", encoding="utf-8")
        review.complete_review(rid, {
            "masked_file_path": str(masked_file),
            "vault_id": "20260717-000000-abcd1234",
            "output_format": "markdown",
            "entity_counts": {"ORG": 1, "PERSON": 1},
            "manual_terms_added": ["Kwframe Industries"],
            "warnings": [],
        })

        assert tools.get_review_status(rid).status == "completed"
        result = tools.get_review_result(rid)
        assert result.masked_text == "⟦ORG_001⟧ met ⟦PERSON_001⟧."
        assert result.vault_id == "20260717-000000-abcd1234"
        assert result.manual_terms_added == ["Kwframe Industries"]

    def test_result_while_waiting_is_clean_error(self, data_dir, tmp_path):
        from maskingtool.mcp_server import tools

        doc = tmp_path / "doc.md"
        doc.write_text("x", encoding="utf-8")
        started = tools.mask_document(str(doc))
        with pytest.raises(ValueError):
            tools.get_review_result(started.review_id)
