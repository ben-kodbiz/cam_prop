"""Command-line interface for the open-evidence pipeline."""

from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from pathlib import Path

from app.config import load_config
from app.db import connect, init_db
from app.util import utcnow_iso

ROOT = Path(__file__).resolve().parent.parent


def cmd_init_db(args: argparse.Namespace) -> int:
    cfg = load_config(env_file=args.env)
    init_db(cfg.db_path)
    print(f"initialized {cfg.db_path}")
    return 0


def cmd_seed(args: argparse.Namespace) -> int:
    cfg = load_config(env_file=args.env)
    init_db(cfg.db_path)
    conn = connect(cfg.db_path)
    try:
        from app.seed import seed

        ids = seed(conn, archive_dir=cfg.archive_dir)
        conn.commit()
        print(json.dumps(ids, indent=2))
    finally:
        conn.close()
    return 0


def cmd_export(args: argparse.Namespace) -> int:
    cfg = load_config(env_file=args.env)
    if not Path(cfg.db_path).is_file():
        print(f"database not found at {cfg.db_path}; run 'init-db' first", file=sys.stderr)
        return 1
    from app.export import export_all, export_site_data

    counts = export_all(cfg.db_path, cfg.generated_dir, site_url=cfg.site_url)
    web_counts = export_site_data(cfg.db_path, cfg.web_dir, site_url=cfg.site_url)
    print(json.dumps({"generated": counts, "web_data": web_counts}, indent=2))
    return 0


def cmd_queue(args: argparse.Namespace) -> int:
    cfg = load_config(env_file=args.env)
    conn = connect(cfg.db_path, readonly=True)
    try:
        from app.claims import pending_review_queue

        rows = pending_review_queue(conn)
        for r in rows:
            print(
                f"{r['id']} [{r['review_status']}] {r['importance'] or '-':8}"
                f" sup={r['n_supporting']} con={r['n_contradicting']} :: {r['claim_text'][:80]}"
            )
        print(f"-- {len(rows)} pending")
    finally:
        conn.close()
    return 0


def cmd_review(args: argparse.Namespace) -> int:
    cfg = load_config(env_file=args.env)
    conn = connect(cfg.db_path)
    try:
        from app.review import submit_review

        checklist = None
        if args.approve_high_impact:
            checklist = {
                k: True
                for k in (
                    "original_claim_represented",
                    "speaker_identified",
                    "date_correct",
                    "primary_source",
                    "contradictory_evidence_searched",
                    "fact_separated_from_interpretation",
                    "allegation_distinguished_from_finding",
                    "legal_terminology_accurate",
                    "other_party_response_included",
                    "citations_correct",
                    "uncertainty_stated",
                    "no_false_certainty",
                )
            }
        decision = {"approve": "approve", "reject": "reject", "request": "request_evidence"}[
            args.decision
        ]
        submit_review(
            conn,
            subject_type=args.subject_type,
            subject_id=args.subject_id,
            reviewer=args.reviewer,
            decision=decision,
            checklist=checklist,
            notes=args.notes,
        )
        conn.commit()
        print(f"review recorded: {args.subject_type} {args.subject_id} -> {decision}")
        return 0
    except ValueError as e:
        print(f"error: {e}", file=sys.stderr)
        return 1
    finally:
        conn.close()


def cmd_assess(args: argparse.Namespace) -> int:
    cfg = load_config(env_file=args.env)
    conn = connect(cfg.db_path, readonly=True)
    try:
        from agents.evidence_agent import assess_claim, assess_pending

        if args.claim_id:
            print(assess_claim(conn, args.claim_id).to_json())
        else:
            print(json.dumps(assess_pending(conn), indent=2))
    finally:
        conn.close()
    return 0


def cmd_search(args: argparse.Namespace) -> int:
    cfg = load_config(env_file=args.env)
    conn = connect(cfg.db_path, readonly=True)
    try:
        from app.search import search

        hits = search(conn, args.query, status=args.status, limit=args.limit)
        for h in hits:
            print(f"{h.claim_id} [{h.status}] ({h.matched_by}) {h.claim_text[:90]}")
        print(f"-- {len(hits)} hits")
    finally:
        conn.close()
    return 0


def cmd_stats(args: argparse.Namespace) -> int:
    cfg = load_config(env_file=args.env)
    conn = connect(cfg.db_path, readonly=True)
    try:
        from app.analytics import compute_stats

        out = compute_stats(conn, days=args.days)
        if args.out:
            Path(args.out).write_text(
                json.dumps(out, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
            )
            print(f"stats written to {args.out}")
        print(json.dumps(out, indent=2, ensure_ascii=False))
    finally:
        conn.close()
    return 0


def cmd_backup(args: argparse.Namespace) -> int:
    cfg = load_config(env_file=args.env)
    src = sqlite3.connect(cfg.db_path)
    try:
        dest_path = Path(args.out or f"data/evidence-backup-{utcnow_iso().replace(':', '')}.db")
        dest_path.parent.mkdir(parents=True, exist_ok=True)
        dest = sqlite3.connect(dest_path)
        try:
            src.backup(dest)
        finally:
            dest.close()
        print(f"backup written to {dest_path}")
        return 0
    finally:
        src.close()


def cmd_ingest_rss(args: argparse.Namespace) -> int:
    cfg = load_config(env_file=args.env)
    from app.rss_pipeline import DEFAULT_FEEDS_PATH, ingest_all

    conn = connect(cfg.db_path)
    try:
        results = ingest_all(
            conn,
            feeds_path=args.feeds or DEFAULT_FEEDS_PATH,
            archive_dir=cfg.archive_dir,
            fetcher=None,
        )
        conn.commit()
        total = {"discovered": 0, "registered": 0, "duplicates": 0, "errors": 0}
        for r in results:
            print(json.dumps(r.to_dict(), ensure_ascii=False))
            for k in total:
                total[k] += getattr(r, k)
        print(f"-- {len(results)} feeds: {json.dumps(total)}")
        return 0 if total["errors"] == 0 else 1
    finally:
        conn.close()


def cmd_feeds(args: argparse.Namespace) -> int:
    from app.rss_pipeline import DEFAULT_FEEDS_PATH, load_feeds

    feeds = load_feeds(args.feeds or DEFAULT_FEEDS_PATH)
    if not feeds:
        print("no enabled feeds configured (see data/feeds.json)")
        return 0
    for f in feeds:
        print(f"{f.name}: {f.url} [{f.source_type}]")
    print(f"-- {len(feeds)} enabled feeds")
    return 0


def cmd_ingest_book(args: argparse.Namespace) -> int:
    cfg = load_config(env_file=args.env)
    from modules.book_pipeline import import_book

    conn = connect(cfg.db_path)
    try:
        result = import_book(
            conn,
            path=args.path,
            title=args.title,
            author=args.author,
            publisher=args.publisher,
            year=args.year,
            isbn=args.isbn,
            language=args.language,
            archive_dir=cfg.archive_dir,
            extract_pages=not args.no_pages,
        )
        conn.commit()
        print(json.dumps(result.to_dict(), indent=2, ensure_ascii=False))
        return 0
    except (ValueError, RuntimeError) as e:
        print(f"error: {e}", file=sys.stderr)
        return 1
    finally:
        conn.close()


def cmd_book_search(args: argparse.Namespace) -> int:
    cfg = load_config(env_file=args.env)
    from modules.book_pipeline import get_book_source, search_book

    conn = connect(cfg.db_path, readonly=True)
    try:
        row = get_book_source(conn, args.source_id)
        if row is None:
            print(f"error: book source {args.source_id} not found", file=sys.stderr)
            return 1
        hits = search_book(cfg.archive_dir, args.source_id, args.query)
        for h in hits:
            page = h.get("page", "?")
            excerpt = str(h.get("excerpt", ""))[:200]
            print(f"p.{page}: {excerpt}")
        print(f"-- {len(hits)} pages matched")
        return 0
    finally:
        conn.close()


def cmd_legal(args: argparse.Namespace) -> int:
    cfg = load_config(env_file=args.env)
    from modules.international_law import iter_documents

    conn = connect(cfg.db_path, readonly=True)
    try:
        docs = iter_documents(conn, body=args.body, approved_only=args.approved_only)
        for d in docs:
            print(
                f"{d['id']} [{d['document_type']}] {d['body']} — {d['case_or_document']}"
                f" ({d['doc_date'] or 'undated'}) [{d['review_status']}]"
            )
            print(f"    finding: {d['finding'][:100]}")
            print(f"    does NOT establish: {d['does_not_establish'][:100]}")
        print(f"-- {len(docs)} legal documents")
        return 0
    finally:
        conn.close()


def cmd_books(args: argparse.Namespace) -> int:
    from modules.book_pipeline import list_books

    cfg = load_config(env_file=args.env)
    conn = connect(cfg.db_path, readonly=True)
    try:
        for b in list_books(conn):
            year = f" ({b['book_year']})" if b["book_year"] else ""
            pages = f", {b['book_pages']} pp." if b["book_pages"] else ""
            print(f"{b['id']}: {b['title']}{year}{pages} — {b['book_author'] or 'unknown author'}")
        return 0
    finally:
        conn.close()


def cmd_publish(args: argparse.Namespace) -> int:
    cfg = load_config(env_file=args.env)
    from publishing.pipeline import publish_claim

    conn = connect(cfg.db_path)
    try:
        result = publish_claim(
            conn,
            args.claim_id,
            output_dir=cfg.web_dir / "generated",
            actor=args.actor,
        )
        conn.commit()
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0
    except (ValueError, RuntimeError) as e:
        print(f"error: {e}", file=sys.stderr)
        return 1
    finally:
        conn.close()


def cmd_report(args: argparse.Namespace) -> int:
    cfg = load_config(env_file=args.env)
    import publishing.reports as reports
    from publishing.pipeline import publish_report

    conn = connect(cfg.db_path, readonly=True)
    try:
        if args.kind == "weekly":
            text = reports.weekly_report(conn)
        elif args.kind == "corporate":
            text = reports.corporate_monthly_report(conn)
        else:
            limit = args.limit or 20
            text = reports.fact_check_card_report(conn, limit=limit)
        out = publish_report(
            conn,
            text,
            name=f"{args.kind}-{utcnow_iso()[:10]}",
            output_dir=cfg.web_dir / "generated",
            actor=args.actor,
        )
        print(f"report written: {out}")
        print(text[:400] + ("…" if len(text) > 400 else ""))
        return 0
    finally:
        conn.close()


def cmd_retract(args: argparse.Namespace) -> int:
    cfg = load_config(env_file=args.env)
    from app.corrections import retract_publication

    conn = connect(cfg.db_path)
    try:
        n = retract_publication(
            conn,
            subject_type=args.subject_type,
            subject_id=args.subject_id,
            actor=args.actor,
            reason=args.reason,
        )
        conn.commit()
        print(f"retracted {n} live publication(s) of {args.subject_type} {args.subject_id}")
        return 0
    except (ValueError, RuntimeError) as e:
        print(f"error: {e}", file=sys.stderr)
        return 1
    finally:
        conn.close()


def cmd_correct(args: argparse.Namespace) -> int:
    cfg = load_config(env_file=args.env)
    from app.corrections import correct_claim

    conn = connect(cfg.db_path)
    try:
        revision = correct_claim(
            conn,
            args.claim_id,
            kind=args.kind,
            reason=args.reason,
            reviewer=args.reviewer,
            new_status=args.new_status,
            new_explanation=args.explanation,
        )
        conn.commit()
        print(f"correction recorded; {args.claim_id} is now revision {revision}")
        return 0
    except (ValueError, RuntimeError) as e:
        print(f"error: {e}", file=sys.stderr)
        return 1
    finally:
        conn.close()


def cmd_extract_claims(args: argparse.Namespace) -> int:
    cfg = load_config(env_file=args.env)
    from agents.claim_extraction import extract_claims
    from agents.llm import client_from_config

    conn = connect(cfg.db_path)
    try:
        row = conn.execute("SELECT * FROM sources WHERE id = ?", (args.source_id,)).fetchone()
        if row is None:
            print(f"error: source {args.source_id} not found", file=sys.stderr)
            return 1
        text = _source_text(cfg, row)
        result = extract_claims(
            conn,
            source_id=args.source_id,
            text=text,
            client=client_from_config(cfg.llm),
            topic=args.topic,
        )
        conn.commit()
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0
    except (ValueError, RuntimeError) as e:
        print(f"error: {e}", file=sys.stderr)
        return 1
    finally:
        conn.close()


def cmd_draft(args: argparse.Namespace) -> int:
    cfg = load_config(env_file=args.env)
    from agents.drafts import draft_explanation, draft_translation
    from agents.llm import client_from_config

    conn = connect(cfg.db_path)
    try:
        client = client_from_config(cfg.llm)
        if args.kind == "explanation":
            draft_explanation(conn, claim_id=args.claim_id, client=client, model=cfg.llm.model)
            action = "explanation"
        else:
            draft_translation(
                conn,
                claim_id=args.claim_id,
                target_language=args.language,
                client=client,
                model=cfg.llm.model,
            )
            action = f"translation ({args.language})"
        conn.commit()
        print(
            f"draft {action} stored for {args.claim_id}; apply with"
            f" `drafts --claim-id {args.claim_id}` then `apply-draft DFT-…`"
        )
        return 0
    except (ValueError, RuntimeError) as e:
        print(f"error: {e}", file=sys.stderr)
        return 1
    finally:
        conn.close()


def cmd_drafts(args: argparse.Namespace) -> int:
    cfg = load_config(env_file=args.env)
    from agents.drafts import pending_drafts

    conn = connect(cfg.db_path, readonly=True)
    try:
        rows = pending_drafts(conn, claim_id=args.claim_id)
        for d in rows:
            print(f"{d['id']} [{d['kind']}] claim={d['claim_id']}")
            print(f"    {d['draft_text'][:160]}")
        print(f"-- {len(rows)} pending drafts")
        return 0
    finally:
        conn.close()


def cmd_apply_draft(args: argparse.Namespace) -> int:
    cfg = load_config(env_file=args.env)
    from agents.drafts import apply_draft, reject_draft

    conn = connect(cfg.db_path)
    try:
        if args.reject:
            reject_draft(conn, args.draft_id, reviewer=args.reviewer, reason=args.reason)
            conn.commit()
            print(f"draft {args.draft_id} rejected")
        else:
            apply_draft(conn, args.draft_id, reviewer=args.reviewer)
            conn.commit()
            print(f"draft {args.draft_id} applied by {args.reviewer}")
        return 0
    except (ValueError, RuntimeError) as e:
        print(f"error: {e}", file=sys.stderr)
        return 1
    finally:
        conn.close()


def _source_text(cfg: object, row: sqlite3.Row) -> str:
    """Text used for claim extraction: book pages or archived content."""
    archive_dir = cfg.archive_dir
    if row["doc_kind"] == "book":
        from modules.book_pipeline import load_pages

        pages = load_pages(archive_dir, row["id"])
        return "\n".join(pages.get(i, "") for i in sorted(pages)) or row["title"]
    if row["archive_path"]:
        source_file = archive_dir / Path(row["archive_path"]) / "source.txt"
        if source_file.is_file():
            text: str = source_file.read_text(encoding="utf-8", errors="replace")
            return text
    title: str = str(row["title"])
    return title


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="open-evidence", description=__doc__)
    p.add_argument("--env", default=None, help="path to .env file")
    sub = p.add_subparsers(dest="command", required=True)

    sp = sub.add_parser("init-db", help="create SQLite schema")
    sp.set_defaults(func=cmd_init_db)

    sp = sub.add_parser("seed", help="load fixture data (marked SEED)")
    sp.set_defaults(func=cmd_seed)

    sp = sub.add_parser("export", help="export JSON for the static site")
    sp.set_defaults(func=cmd_export)

    sp = sub.add_parser("queue", help="show pending review queue")
    sp.set_defaults(func=cmd_queue)

    sp = sub.add_parser("review", help="record a human review decision")
    sp.add_argument(
        "--subject-type",
        choices=["claim", "relationship", "statement", "alternative", "legal_document"],
        required=True,
    )
    sp.add_argument("--subject-id", required=True)
    sp.add_argument("--reviewer", required=True)
    sp.add_argument("--decision", choices=["approve", "reject", "request"], required=True)
    sp.add_argument(
        "--approve-high-impact",
        action="store_true",
        help="attest the full review checklist (required for high-impact claims)",
    )
    sp.add_argument("--notes", default=None)
    sp.set_defaults(func=cmd_review)

    sp = sub.add_parser("assess", help="provisional evidence assessment (no LLM)")
    sp.add_argument("--claim-id", default=None)
    sp.set_defaults(func=cmd_assess)

    sp = sub.add_parser("search", help="search claims")
    sp.add_argument("query", nargs="?", default="")
    sp.add_argument("--status", default=None)
    sp.add_argument("--limit", type=int, default=50)
    sp.set_defaults(func=cmd_search)

    sp = sub.add_parser("feeds", help="list configured RSS feeds")
    sp.add_argument("--feeds", default=None, help="path to feeds.json")
    sp.set_defaults(func=cmd_feeds)

    sp = sub.add_parser(
        "ingest-rss",
        help="fetch configured RSS feeds and register new sources",
    )
    sp.add_argument("--feeds", default=None, help="path to feeds.json")
    sp.set_defaults(func=cmd_ingest_rss)

    sp = sub.add_parser("ingest-book", help="import a local PDF book as a source")
    sp.add_argument("path", help="path to the PDF file")
    sp.add_argument("--title", required=True)
    sp.add_argument("--author", default=None)
    sp.add_argument("--publisher", default=None)
    sp.add_argument("--year", default=None)
    sp.add_argument("--isbn", default=None)
    sp.add_argument("--language", default="en")
    sp.add_argument(
        "--no-pages",
        action="store_true",
        help="skip per-page text extraction (still hashed + archived)",
    )
    sp.set_defaults(func=cmd_ingest_book)

    sp = sub.add_parser("legal", help="list international-law documents")
    sp.add_argument("--body", default=None, help="filter by body (ICJ, ICC, UNSC…)")
    sp.add_argument("--approved-only", action="store_true")
    sp.set_defaults(func=cmd_legal)

    sp = sub.add_parser("books", help="list imported books")
    sp.set_defaults(func=cmd_books)

    sp = sub.add_parser("book-search", help="keyword search inside an imported book")
    sp.add_argument("source_id")
    sp.add_argument("query")
    sp.set_defaults(func=cmd_book_search)

    sp = sub.add_parser("stats", help="database statistics (§43 metrics)")
    sp.add_argument("--days", type=int, default=30, help="analytics window")
    sp.add_argument("--out", default=None, help="also write stats JSON to this path")
    sp.set_defaults(func=cmd_stats)

    sp = sub.add_parser("publish", help="publish an approved claim (+ card artifact)")
    sp.add_argument("claim_id")
    sp.add_argument("--actor", default="system")
    sp.set_defaults(func=cmd_publish)

    sp = sub.add_parser("report", help="generate a report artifact")
    sp.add_argument("--kind", choices=["weekly", "corporate", "cards"], default="weekly")
    sp.add_argument("--limit", type=int, default=20, help="cards report: max claims")
    sp.add_argument("--actor", default="system")
    sp.set_defaults(func=cmd_report)

    sp = sub.add_parser("retract", help="retract live publications of a subject")
    sp.add_argument(
        "--subject-type",
        choices=["claim", "relationship", "alternative", "legal_document"],
        required=True,
    )
    sp.add_argument("--subject-id", required=True)
    sp.add_argument("--reason", required=True)
    sp.add_argument("--actor", default="system")
    sp.set_defaults(func=cmd_retract)

    sp = sub.add_parser("correct", help="record a tracked correction to a claim")
    sp.add_argument("claim_id")
    sp.add_argument(
        "--kind",
        choices=[
            "correction",
            "clarification",
            "evidence_update",
            "status_change",
            "source_removal",
        ],
        required=True,
    )
    sp.add_argument("--reason", required=True)
    sp.add_argument("--reviewer", required=True)
    sp.add_argument("--new-status", default=None)
    sp.add_argument("--explanation", default=None)
    sp.set_defaults(func=cmd_correct)

    sp = sub.add_parser("extract-claims", help="LLM: propose claims from a source's text")
    sp.add_argument("source_id")
    sp.add_argument("--topic", default=None)
    sp.set_defaults(func=cmd_extract_claims)

    sp = sub.add_parser("draft", help="LLM: draft an explanation or translation")
    sp.add_argument("claim_id")
    sp.add_argument("--kind", choices=["explanation", "translation"], required=True)
    sp.add_argument("--language", default="en", help="target language for translation")
    sp.set_defaults(func=cmd_draft)

    sp = sub.add_parser("drafts", help="list pending LLM drafts")
    sp.add_argument("--claim-id", default=None)
    sp.set_defaults(func=cmd_drafts)

    sp = sub.add_parser("apply-draft", help="apply or reject a pending LLM draft")
    sp.add_argument("draft_id")
    sp.add_argument("--reviewer", required=True)
    sp.add_argument("--reject", action="store_true")
    sp.add_argument("--reason", default=None)
    sp.set_defaults(func=cmd_apply_draft)

    sp = sub.add_parser("backup", help="backup the SQLite database")
    sp.add_argument("--out", default=None)
    sp.set_defaults(func=cmd_backup)

    return p


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    rc: int = args.func(args)
    return rc


if __name__ == "__main__":
    sys.exit(main())
