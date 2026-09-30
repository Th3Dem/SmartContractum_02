#!/usr/bin/env python3
"""
scripts/migration_diagnostic.py

Migration diagnostic tool for Q&A data integrity and invariants audit.
Part of Issue #26 (SC-024.3).

Verifies SQLite database for:
1. Duplicate active answers per user on questions.
2. Multiple accepted solutions per question.
3. Solution flags on non-answers.
4. Answers on non-question materials.
5. Orphaned replies (missing parent, non-published, non-answer, or wrong article).
6. Mismatched counters across publications and profiles.

CLI Parameters:
  --db <path>: Path to SQLite database (default: data/moderation.db).
  --json: Output results in JSON format.
  --verbose: Display detailed information for discovered inconsistencies.

Exit code 0 on clean database, 1 if violations are found.
Strict compliance: zero emojis, zero em dashes, masked paths and sensitive data.
"""

import argparse
import datetime
import json
import os
import sqlite3
import sys
from typing import Any, Dict, List, Optional, Tuple

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
DEFAULT_DB_REL_PATH = "data/moderation.db"


def mask_path(path: Optional[str]) -> str:
    """
    Masks absolute filesystem paths to prevent leaking host machine environment.
    Converts paths inside repository to relative paths.
    Masks paths outside repository as <DB_PATH>/<basename>.
    """
    if not path:
        return ""
    norm = os.path.normpath(os.path.abspath(path))
    try:
        rel = os.path.relpath(norm, REPO_ROOT)
        if not rel.startswith("..") and not os.path.isabs(rel):
            return rel.replace("\\", "/")
    except Exception:
        pass
    basename = os.path.basename(norm)
    return f"<DB_PATH>/{basename}"


def run_diagnostic(db_path: str, verbose: bool = False) -> Dict[str, Any]:
    """
    Executes dry-run audit checks on the SQLite database without destructive modifications.
    Returns structured results dictionary.
    """
    resolved_path = os.path.abspath(db_path)
    if not os.path.isfile(resolved_path):
        return {
            "clean": False,
            "error": f"Database file not found: {mask_path(db_path)}",
            "violations_count": 1,
            "summary": {
                "duplicate_answers": 0,
                "multiple_solutions": 0,
                "invalid_solutions": 0,
                "answers_on_non_questions": 0,
                "orphaned_replies": 0,
                "mismatched_counters": 1,
            },
            "details": {
                "duplicate_answers": [],
                "multiple_solutions": [],
                "invalid_solutions": [],
                "answers_on_non_questions": [],
                "orphaned_replies": [],
                "mismatched_counters": [
                    {
                        "entity_type": "system",
                        "id": "database_file",
                        "field": "file_existence",
                        "cached_value": None,
                        "actual_value": "file_not_found",
                    }
                ],
            },
            "database": mask_path(db_path),
            "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        }

    conn = None
    try:
        conn = sqlite3.connect(resolved_path)
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()

        # Verify required tables exist
        cur.execute("SELECT name FROM sqlite_master WHERE type='table'")
        existing_tables = {r["name"] for r in cur.fetchall()}

        if "article_comments" not in existing_tables or "moderation_submissions" not in existing_tables:
            return {
                "clean": False,
                "error": "Required database tables missing (article_comments or moderation_submissions)",
                "violations_count": 1,
                "summary": {
                    "duplicate_answers": 0,
                    "multiple_solutions": 0,
                    "invalid_solutions": 0,
                    "answers_on_non_questions": 0,
                    "orphaned_replies": 0,
                    "mismatched_counters": 1,
                },
                "details": {
                    "duplicate_answers": [],
                    "multiple_solutions": [],
                    "invalid_solutions": [],
                    "answers_on_non_questions": [],
                    "orphaned_replies": [],
                    "mismatched_counters": [
                        {
                            "entity_type": "schema",
                            "id": "tables",
                            "field": "required_tables",
                            "cached_value": list(existing_tables),
                            "actual_value": "missing_required_tables",
                        }
                    ],
                },
                "database": mask_path(db_path),
                "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
            }

        details: Dict[str, List[Dict[str, Any]]] = {
            "duplicate_answers": [],
            "multiple_solutions": [],
            "invalid_solutions": [],
            "answers_on_non_questions": [],
            "orphaned_replies": [],
            "mismatched_counters": [],
        }

        # Check 1: Duplicate active answers per user on questions
        cur.execute("""
            SELECT article_id, user_id, COUNT(*) AS count, GROUP_CONCAT(id) AS comment_ids
            FROM article_comments
            WHERE comment_type = 'answer' AND status = 'published'
            GROUP BY article_id, user_id
            HAVING COUNT(*) > 1
        """)
        for r in cur.fetchall():
            c_ids = [cid.strip() for cid in (r["comment_ids"] or "").split(",") if cid.strip()]
            details["duplicate_answers"].append({
                "article_id": r["article_id"],
                "user_id": r["user_id"],
                "count": r["count"],
                "comment_ids": c_ids,
            })

        # Check 2: Multiple solutions per question
        cur.execute("""
            SELECT article_id, COUNT(*) AS count, GROUP_CONCAT(id) AS comment_ids
            FROM article_comments
            WHERE is_solution = 1
            GROUP BY article_id
            HAVING COUNT(*) > 1
        """)
        for r in cur.fetchall():
            c_ids = [cid.strip() for cid in (r["comment_ids"] or "").split(",") if cid.strip()]
            details["multiple_solutions"].append({
                "article_id": r["article_id"],
                "count": r["count"],
                "comment_ids": c_ids,
            })

        # Check 3: Solution flags on non-answers
        cur.execute("""
            SELECT id, article_id, user_id, comment_type, is_solution
            FROM article_comments
            WHERE is_solution = 1 AND (comment_type != 'answer' OR comment_type IS NULL)
        """)
        for r in cur.fetchall():
            details["invalid_solutions"].append({
                "comment_id": r["id"],
                "article_id": r["article_id"],
                "user_id": r["user_id"],
                "comment_type": r["comment_type"],
            })

        # Check 4: Answers on non-question materials
        cur.execute("""
            SELECT ac.id, ac.article_id, ac.user_id, ms.id AS ms_id, ms.publication_settings
            FROM article_comments ac
            LEFT JOIN moderation_submissions ms ON (ac.article_id = ms.id OR ac.article_id = ms.draft_id)
            WHERE ac.comment_type = 'answer'
        """)
        for r in cur.fetchall():
            is_non_question = False
            mat_type = "unknown"
            if r["ms_id"] is None:
                is_non_question = True
                mat_type = "missing_publication"
            else:
                try:
                    pst = json.loads(r["publication_settings"]) if r["publication_settings"] else {}
                    mat_type = (pst.get("materialType") or pst.get("type") or "article").strip().lower()
                except Exception:
                    mat_type = "invalid_settings"
                if mat_type != "question":
                    is_non_question = True

            if is_non_question:
                details["answers_on_non_questions"].append({
                    "comment_id": r["id"],
                    "article_id": r["article_id"],
                    "user_id": r["user_id"],
                    "material_type": mat_type,
                })

        # Check 5: Orphaned replies
        cur.execute("""
            SELECT c.id, c.article_id, c.user_id, c.parent_answer_id,
                   p.id AS parent_id, p.status AS parent_status,
                   p.comment_type AS parent_type, p.article_id AS parent_article_id
            FROM article_comments c
            LEFT JOIN article_comments p ON c.parent_answer_id = p.id
            WHERE c.parent_answer_id IS NOT NULL AND TRIM(c.parent_answer_id) != ''
              AND (
                  p.id IS NULL
                  OR p.status != 'published'
                  OR p.comment_type != 'answer'
                  OR p.article_id != c.article_id
              )
        """)
        for r in cur.fetchall():
            reasons = []
            if r["parent_id"] is None:
                reasons.append("parent_missing")
            else:
                if r["parent_status"] != "published":
                    reasons.append(f"parent_status_{r['parent_status']}")
                if r["parent_type"] != "answer":
                    reasons.append(f"parent_type_{r['parent_type']}")
                if r["parent_article_id"] != r["article_id"]:
                    reasons.append("parent_article_mismatch")

            details["orphaned_replies"].append({
                "comment_id": r["id"],
                "article_id": r["article_id"],
                "user_id": r["user_id"],
                "parent_answer_id": r["parent_answer_id"],
                "reasons": reasons,
            })

        # Check 6: Mismatched counters
        cur.execute("PRAGMA table_info(moderation_submissions)")
        ms_cols = {col["name"] for col in cur.fetchall()}

        cur.execute("""
            SELECT article_id,
                   SUM(CASE WHEN comment_type = 'answer' AND status = 'published' THEN 1 ELSE 0 END) AS actual_answers,
                   SUM(CASE WHEN comment_type = 'answer' AND status = 'published' AND is_solution = 1 THEN 1 ELSE 0 END) AS actual_solutions
            FROM article_comments
            GROUP BY article_id
        """)
        article_counts: Dict[str, Tuple[int, int]] = {
            r["article_id"]: (r["actual_answers"] or 0, r["actual_solutions"] or 0)
            for r in cur.fetchall()
        }

        cur.execute("SELECT id, draft_id, publication_settings FROM moderation_submissions")
        pub_rows = cur.fetchall()

        for pr in pub_rows:
            art_id = pr["id"]
            draft_id = pr["draft_id"]
            actual_ans, actual_sol = article_counts.get(art_id, article_counts.get(draft_id, (0, 0)))

            try:
                pst = json.loads(pr["publication_settings"]) if pr["publication_settings"] else {}
            except Exception:
                pst = {}

            mat_type = (pst.get("materialType") or pst.get("type") or "article").strip().lower()

            for key in ("answersCount", "answers_count"):
                if key in pst:
                    exp_val = pst[key]
                    if isinstance(exp_val, int) and exp_val != actual_ans:
                        details["mismatched_counters"].append({
                            "entity_type": "publication_settings",
                            "id": art_id,
                            "field": key,
                            "cached_value": exp_val,
                            "actual_value": actual_ans,
                        })

            for key in ("solutionsCount", "solutions_count"):
                if key in pst:
                    exp_val = pst[key]
                    if isinstance(exp_val, int) and exp_val != actual_sol:
                        details["mismatched_counters"].append({
                            "entity_type": "publication_settings",
                            "id": art_id,
                            "field": key,
                            "cached_value": exp_val,
                            "actual_value": actual_sol,
                        })

            if "hasSolution" in pst and isinstance(pst["hasSolution"], bool):
                exp_has_sol = pst["hasSolution"]
                actual_has_sol = (actual_sol > 0)
                if exp_has_sol != actual_has_sol:
                    details["mismatched_counters"].append({
                        "entity_type": "publication_settings",
                        "id": art_id,
                        "field": "hasSolution",
                        "cached_value": exp_has_sol,
                        "actual_value": actual_has_sol,
                    })

            if mat_type == "question" and "questionStatus" in pst:
                q_status = str(pst["questionStatus"]).strip().lower()
                if q_status == "solved" and actual_sol == 0:
                    details["mismatched_counters"].append({
                        "entity_type": "publication_settings",
                        "id": art_id,
                        "field": "questionStatus",
                        "cached_value": q_status,
                        "actual_value": f"solutions_count={actual_sol}",
                    })
                elif q_status == "unanswered" and actual_ans > 0:
                    details["mismatched_counters"].append({
                        "entity_type": "publication_settings",
                        "id": art_id,
                        "field": "questionStatus",
                        "cached_value": q_status,
                        "actual_value": f"answers_count={actual_ans}",
                    })
                elif q_status == "unsolved" and actual_sol > 0:
                    details["mismatched_counters"].append({
                        "entity_type": "publication_settings",
                        "id": art_id,
                        "field": "questionStatus",
                        "cached_value": q_status,
                        "actual_value": f"solutions_count={actual_sol}",
                    })

        # Check moderation_submissions explicit columns if present
        for col in ("answers_count", "answersCount"):
            if col in ms_cols:
                cur.execute(f"SELECT id, {col} FROM moderation_submissions")
                for row in cur.fetchall():
                    val = row[col]
                    if val is not None:
                        actual_ans, _ = article_counts.get(row["id"], (0, 0))
                        if val != actual_ans:
                            details["mismatched_counters"].append({
                                "entity_type": "publication_column",
                                "id": row["id"],
                                "field": col,
                                "cached_value": val,
                                "actual_value": actual_ans,
                            })

        for col in ("solutions_count", "solutionsCount"):
            if col in ms_cols:
                cur.execute(f"SELECT id, {col} FROM moderation_submissions")
                for row in cur.fetchall():
                    val = row[col]
                    if val is not None:
                        _, actual_sol = article_counts.get(row["id"], (0, 0))
                        if val != actual_sol:
                            details["mismatched_counters"].append({
                                "entity_type": "publication_column",
                                "id": row["id"],
                                "field": col,
                                "cached_value": val,
                                "actual_value": actual_sol,
                            })

        # User profile counters check
        if "user_profiles" in existing_tables:
            cur.execute("PRAGMA table_info(user_profiles)")
            up_cols = {col["name"] for col in cur.fetchall()}

            cur.execute("""
                SELECT ac.user_id,
                       COUNT(*) AS total_answers,
                       SUM(CASE WHEN ac.is_solution = 1 THEN 1 ELSE 0 END) AS total_solutions
                FROM article_comments ac
                JOIN moderation_submissions ms ON (ac.article_id = ms.id OR ac.article_id = ms.draft_id)
                WHERE ac.status = 'published'
                  AND ac.comment_type = 'answer'
                  AND ms.status = 'approved'
                  AND (
                      json_extract(ms.publication_settings, '$.materialType') = 'question'
                      OR json_extract(ms.publication_settings, '$.type') = 'question'
                  )
                GROUP BY ac.user_id
            """)
            user_stats: Dict[str, Tuple[int, int]] = {
                r["user_id"]: (r["total_answers"] or 0, r["total_solutions"] or 0)
                for r in cur.fetchall()
            }

            for col in ("answers_count", "answersCount"):
                if col in up_cols:
                    cur.execute(f"SELECT user_id, {col} FROM user_profiles")
                    for row in cur.fetchall():
                        val = row[col]
                        if val is not None:
                            actual_ans, _ = user_stats.get(row["user_id"], (0, 0))
                            if val != actual_ans:
                                details["mismatched_counters"].append({
                                    "entity_type": "user_profile_column",
                                    "id": row["user_id"],
                                    "field": col,
                                    "cached_value": val,
                                    "actual_value": actual_ans,
                                })

            for col in ("solutions_count", "solutionsCount"):
                if col in up_cols:
                    cur.execute(f"SELECT user_id, {col} FROM user_profiles")
                    for row in cur.fetchall():
                        val = row[col]
                        if val is not None:
                            _, actual_sol = user_stats.get(row["user_id"], (0, 0))
                            if val != actual_sol:
                                details["mismatched_counters"].append({
                                    "entity_type": "user_profile_column",
                                    "id": row["user_id"],
                                    "field": col,
                                    "cached_value": val,
                                    "actual_value": actual_sol,
                                })

            if "stats" in up_cols:
                cur.execute("SELECT user_id, stats FROM user_profiles WHERE stats IS NOT NULL")
                for row in cur.fetchall():
                    try:
                        st = json.loads(row["stats"]) if row["stats"] else {}
                    except Exception:
                        st = {}
                    actual_ans, actual_sol = user_stats.get(row["user_id"], (0, 0))
                    if "answersCount" in st and isinstance(st["answersCount"], int) and st["answersCount"] != actual_ans:
                        details["mismatched_counters"].append({
                            "entity_type": "user_profile_stats",
                            "id": row["user_id"],
                            "field": "answersCount",
                            "cached_value": st["answersCount"],
                            "actual_value": actual_ans,
                        })
                    if "solutionsCount" in st and isinstance(st["solutionsCount"], int) and st["solutionsCount"] != actual_sol:
                        details["mismatched_counters"].append({
                            "entity_type": "user_profile_stats",
                            "id": row["user_id"],
                            "field": "solutionsCount",
                            "cached_value": st["solutionsCount"],
                            "actual_value": actual_sol,
                        })

        summary = {k: len(v) for k, v in details.items()}
        total_violations = sum(summary.values())

        return {
            "clean": (total_violations == 0),
            "violations_count": total_violations,
            "summary": summary,
            "details": details,
            "database": mask_path(db_path),
            "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        }

    except Exception as exc:
        return {
            "clean": False,
            "error": f"Database audit failed: {str(exc)}",
            "violations_count": 1,
            "summary": {
                "duplicate_answers": 0,
                "multiple_solutions": 0,
                "invalid_solutions": 0,
                "answers_on_non_questions": 0,
                "orphaned_replies": 0,
                "mismatched_counters": 1,
            },
            "details": {
                "duplicate_answers": [],
                "multiple_solutions": [],
                "invalid_solutions": [],
                "answers_on_non_questions": [],
                "orphaned_replies": [],
                "mismatched_counters": [
                    {
                        "entity_type": "system",
                        "id": "exception",
                        "field": "audit_execution",
                        "cached_value": None,
                        "actual_value": str(exc),
                    }
                ],
            },
            "database": mask_path(db_path),
            "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        }
    finally:
        if conn:
            try:
                conn.close()
            except Exception:
                pass


def format_text_report(results: Dict[str, Any], verbose: bool = False) -> str:
    """Formats diagnostic results into a clean, human-readable report."""
    lines: List[str] = []
    lines.append("======================================================================")
    lines.append("Q&A MIGRATION DIAGNOSTIC AUDIT REPORT")
    lines.append(f"Target Database: {results.get('database', '')}")
    status_str = "CLEAN" if results.get("clean") else "VIOLATIONS DETECTED"
    lines.append(f"Status: {status_str}")
    lines.append(f"Total Violations: {results.get('violations_count', 0)}")
    lines.append("======================================================================")

    if results.get("error"):
        lines.append(f"ERROR: {results['error']}")
        lines.append("======================================================================")
        return "\n".join(lines)

    summary = results.get("summary", {})
    lines.append(f"- Duplicate active answers: {summary.get('duplicate_answers', 0)}")
    lines.append(f"- Multiple solutions per question: {summary.get('multiple_solutions', 0)}")
    lines.append(f"- Solution flags on non-answers: {summary.get('invalid_solutions', 0)}")
    lines.append(f"- Answers on non-question materials: {summary.get('answers_on_non_questions', 0)}")
    lines.append(f"- Orphaned discussion replies: {summary.get('orphaned_replies', 0)}")
    lines.append(f"- Mismatched counters: {summary.get('mismatched_counters', 0)}")
    lines.append("======================================================================")

    if verbose and results.get("violations_count", 0) > 0:
        details = results.get("details", {})
        lines.append("VIOLATION DETAILS:")

        for category, items in details.items():
            if not items:
                continue
            lines.append(f"\n--- [{category}] ({len(items)} items) ---")
            for idx, item in enumerate(items, 1):
                item_desc = ", ".join(f"{k}: {v}" for k, v in item.items())
                lines.append(f"  {idx}. {item_desc}")

        lines.append("======================================================================")
    elif not verbose and results.get("violations_count", 0) > 0:
        lines.append("Hint: Run with --verbose to view detailed violation records.")
        lines.append("======================================================================")

    return "\n".join(lines)


def main() -> int:
    """CLI entrypoint."""
    parser = argparse.ArgumentParser(
        description="Dry-run diagnostic verification of Q&A database integrity and invariants."
    )
    parser.add_argument(
        "--db",
        type=str,
        default=DEFAULT_DB_REL_PATH,
        help="Path to SQLite database file (default: data/moderation.db)",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Output audit results as JSON",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Display detailed violation records",
    )

    args = parser.parse_args()

    results = run_diagnostic(db_path=args.db, verbose=args.verbose)

    if args.json:
        print(json.dumps(results, indent=2, ensure_ascii=False))
    else:
        print(format_text_report(results, verbose=args.verbose))

    return 0 if results.get("clean") else 1


if __name__ == "__main__":
    sys.exit(main())
