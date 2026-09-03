"""Phase 3 (AI) tests: LLM client parsing, claim extraction, drafts.

All tests use a fake client — zero network. The invariants under test:
LLM output only ever creates *pending* claims or *pending* drafts; a human
must apply/approve before anything changes published state.
"""

from __future__ import annotations

import json

import pytest
from agents.claim_extraction import extract_claims
from agents.drafts import (
    DraftError,
    apply_draft,
    draft_explanation,
    draft_translation,
    pending_drafts,
    reject_draft,
)
from agents.llm import OpenAICompatClient, parse_json_block
from app.seed import seed
from app.sources import create_source


class FakeLLM:
    """Deterministic stand-in for the OpenAI-compatible client."""

    def __init__(self, reply: str):
        self.reply = reply
        self.calls: list[tuple[str, str]] = []

    def complete(self, system: str, user: str, *, json_mode: bool = False) -> str:
        self.calls.append((system, user))
        return self.reply


def test_parse_json_block_plain():
    assert parse_json_block('{"a": 1}') == {"a": 1}


def test_parse_json_block_fenced():
    fenced = '```json\n{"claims": []}\n```'
    assert parse_json_block(fenced) == {"claims": []}


def test_parse_json_block_prose_wrapped():
    wrapped = 'Here you go: {"x": {"y": 2}} hope that helps'
    assert parse_json_block(wrapped) == {"x": {"y": 2}}


def test_parse_json_block_garbage():
    from agents.llm import LLMError

    with pytest.raises(LLMError, match="could not parse"):
        parse_json_block("no json here at all")


def test_client_config_defaults():
    c = OpenAICompatClient(endpoint="http://localhost:1234/v1", model="local-model")
    assert c.model == "local-model"
    assert c.api_key == ""


# ---------------------------------------------------------------------------
# Claim extraction
# ---------------------------------------------------------------------------

REPLY_TWO_CLAIMS = json.dumps(
    {
        "claims": [
            {
                "text": "The ministry delivered ten vehicles.",
                "speaker": "SEED Ministry",
                "speaker_type": "government",
                "date": "2024-03-01",
            },
            {
                "text": "The vehicles were funded by the regional budget.",
                "speaker": "SEED Ministry",
                "speaker_type": "government",
                "date": "2024-03-01",
            },
        ]
    }
)


def test_extract_creates_pending_claims(tmp_db):
    sid = create_source(
        tmp_db, url="https://x.example/1", title="X", source_type="news", content_text="body"
    )
    result = extract_claims(
        tmp_db, source_id=sid, text="anything", client=FakeLLM(REPLY_TWO_CLAIMS)
    )
    assert result["created"] == 2
    rows = tmp_db.execute("SELECT * FROM claims").fetchall()
    assert all(r["review_status"] == "pending" for r in rows)
    assert all(r["status"] == "unknown" for r in rows)  # LLM never sets status
    assert rows[0]["source_id"] == sid


def test_extract_dedupes_on_second_run(tmp_db):
    sid = create_source(
        tmp_db, url="https://x.example/1", title="X", source_type="news", content_text="body"
    )
    client = FakeLLM(REPLY_TWO_CLAIMS)
    extract_claims(tmp_db, source_id=sid, text="t", client=client)
    result = extract_claims(tmp_db, source_id=sid, text="t", client=client)
    assert result["created"] == 0
    assert result["duplicates"] == 2


def test_extract_rejects_missing_source(tmp_db):
    with pytest.raises(Exception, match="does not exist"):
        extract_claims(
            tmp_db, source_id="SRC-2026-9999", text="t", client=FakeLLM(REPLY_TWO_CLAIMS)
        )


def test_extract_rejects_bad_reply(tmp_db):
    sid = create_source(
        tmp_db, url="https://x.example/1", title="X", source_type="news", content_text="body"
    )
    with pytest.raises(Exception, match="could not parse"):
        extract_claims(tmp_db, source_id=sid, text="t", client=FakeLLM("garbage"))


def test_extract_rejects_empty_text(tmp_db):
    sid = create_source(
        tmp_db, url="https://x.example/1", title="X", source_type="news", content_text="body"
    )
    with pytest.raises(Exception, match="no text"):
        extract_claims(tmp_db, source_id=sid, text="  ", client=FakeLLM(REPLY_TWO_CLAIMS))


def test_extract_handles_speakerless_reply(tmp_db):
    reply = json.dumps({"claims": [{"text": "Something happened."}]})
    sid = create_source(
        tmp_db, url="https://x.example/1", title="X", source_type="news", content_text="body"
    )
    result = extract_claims(tmp_db, source_id=sid, text="t", client=FakeLLM(reply))
    assert result["created"] == 1
    row = tmp_db.execute("SELECT speaker FROM claims").fetchone()
    assert row["speaker"] == "Unknown speaker"


# ---------------------------------------------------------------------------
# Drafts (explanation / translation)
# ---------------------------------------------------------------------------


@pytest.fixture()
def seeded(tmp_db, tmp_path):
    ids = seed(tmp_db, archive_dir=tmp_path / "archive")
    tmp_db.commit()
    return tmp_db, ids


def test_explanation_draft_flow(seeded):
    conn, ids = seeded
    client = FakeLLM("The order indicates measures; the claim matches the record.")
    draft_explanation(conn, claim_id=ids["claim_reviewed"], client=client, model="test-model")
    rows = pending_drafts(conn, claim_id=ids["claim_reviewed"])
    assert len(rows) == 1
    assert rows[0]["kind"] == "explanation"
    assert rows[0]["model"] == "test-model"

    # claim untouched until a human applies
    claim = conn.execute(
        "SELECT explanation FROM claims WHERE id = ?", (ids["claim_reviewed"],)
    ).fetchone()
    assert claim["explanation"] is None

    value = apply_draft(conn, rows[0]["id"], reviewer="alice")
    assert value.startswith("The order indicates")
    claim = conn.execute(
        "SELECT explanation FROM claims WHERE id = ?", (ids["claim_reviewed"],)
    ).fetchone()
    assert claim["explanation"].startswith("The order indicates")
    # draft no longer pending
    assert pending_drafts(conn, claim_id=ids["claim_reviewed"]) == []


def test_translation_draft_flow(seeded):
    conn, ids = seeded
    client = FakeLLM("Kementerian mengeluarkan kenyataan.")
    draft_translation(
        conn,
        claim_id=ids["claim_reviewed"],
        target_language="ms",
        client=client,
        model="test-model",
    )
    rows = pending_drafts(conn, claim_id=ids["claim_reviewed"])
    assert rows[0]["kind"] == "translation"
    apply_draft(conn, rows[0]["id"], reviewer="alice")
    claim = conn.execute(
        "SELECT translated_text, translation_method, claim_text FROM claims WHERE id = ?",
        (ids["claim_reviewed"],),
    ).fetchone()
    assert claim["translated_text"] == "Kementerian mengeluarkan kenyataan."
    assert claim["translation_method"] == "llm"
    # §42: original text is never replaced by the translation
    assert claim["claim_text"].startswith("SEED:")


def test_reject_draft(seeded):
    conn, ids = seeded
    draft_explanation(conn, claim_id=ids["claim_reviewed"], client=FakeLLM("bad draft"))
    row = pending_drafts(conn)[0]
    reject_draft(conn, row["id"], reviewer="alice", reason="invented a detail")
    assert pending_drafts(conn) == []
    status = conn.execute("SELECT status FROM claim_drafts WHERE id = ?", (row["id"],)).fetchone()[
        "status"
    ]
    assert status == "rejected"
    claim = conn.execute(
        "SELECT explanation FROM claims WHERE id = ?", (ids["claim_reviewed"],)
    ).fetchone()
    assert claim["explanation"] is None


def test_apply_twice_fails(seeded):
    conn, ids = seeded
    draft_explanation(conn, claim_id=ids["claim_reviewed"], client=FakeLLM("once"))
    row = pending_drafts(conn)[0]
    apply_draft(conn, row["id"], reviewer="a")
    with pytest.raises(DraftError, match="already applied"):
        apply_draft(conn, row["id"], reviewer="a")


def test_draft_missing_claim(tmp_db):
    with pytest.raises(DraftError, match="does not exist"):
        draft_explanation(tmp_db, claim_id="CLM-2026-9999", client=FakeLLM("x"))


def test_llm_saw_evidence_in_prompt(seeded):
    conn, ids = seeded
    client = FakeLLM("ok")
    draft_explanation(conn, claim_id=ids["claim_reviewed"], client=client)
    system, user = client.calls[0]
    assert "never" in system.lower() or "evidence" in system.lower()
    assert "Supporting evidence: 1" in user
    assert "SEED EXCERPT" in user
