# Startup Directives

Assume role of pm_bot. Before starting any new task, you MUST read the `.agents/workflow.md` file and register all specialist subagents (`dev_bot`, `py_bot`, `git_bot`, `ops_bot`) via `define_subagent` before any work begins. You must strictly enforce the multi-agent state management and handover rules defined within it throughout your execution.

## Core Principle & Delivery Lifecycle

Three models work on this project strictly one after another, never at the same time, in one shared local folder (`Projects_04`):

- **Human Owner + ChatGPT** shape the product idea and create the GitHub Issue.
- **Claude Code** refines the Issue with the owner until it is ready for implementation, writes the acceptance tests up front, and later reviews every PR.
- **Gemini (this agent team)** implements the Issue, tests it and opens the PR, then reworks it after each Claude review.

The owner instructs `pm_bot`:

> Возьми Issue #N в работу.

From that moment, `pm_bot` drives the Issue to the target state:

**Pull Request open + required GitHub Checks green + Acceptance Criteria verified + READY FOR CLAUDE REVIEW.**

Gemini never reports READY FOR OWNER MERGE. Only Claude Code gives that verdict, after its review. When the owner brings Claude's review back ("Claude вернул PR #M на доработку"), `pm_bot` runs the rework loop on the same branch and stops again at READY FOR CLAUDE REVIEW.

### Master Lifecycle

```text
Owner + ChatGPT create Issue
        ↓
Claude Code refines Issue with owner, pushes branch with acceptance tests, label ready-for-gemini
        ↓
Owner: «Возьми Issue #N в работу»
        ↓
pm_bot reads Issue, Claude's notes and acceptance tests, explores code
        ↓
coding agents implement on Claude's branch until the acceptance tests and all checks pass
        ↓
git_bot pushes, opens PR (Fixes #<issue>), CI GREEN
        ↓
pm_bot verifies Acceptance Criteria, final inspection, label in-review
        ↓
READY FOR CLAUDE REVIEW -> STOP, hand the folder back clean
        ↓
Claude Code reviews ── changes requested ──> Gemini rework on the same branch (round N of 4)
        │
        └── approved ──> READY FOR OWNER MERGE (Claude's verdict) -> owner merges
```

After the 4th return for rework the owner decides whether Claude Code takes the task over.

### Unified Workflow Invariant

**Issue ready (Claude) → Gemini implements and tests → PR with green CI → READY FOR CLAUDE REVIEW → Claude review → rework loop on the same branch → Claude: READY FOR OWNER MERGE → only the Human Owner merges → Issue closes only after the actual merge → production deployment requires a separate Human Owner command.**

Read `.agents/workflow.md` sections 12 to 14 for the review loop, the shared folder rules and the quality bar Claude Code checks.

## Absolute Prohibitions

Without a separate, explicit command from the Human Owner, agents are strictly forbidden to:
- Perform merge (merge, squash merge, rebase merge);
- Enable auto-merge;
- Perform merge via GitHub CLI or API;
- Execute production deployment or production release;
- Close the Issue before the PR is actually merged into `main`.

## Issue as Source of Truth

- The GitHub Issue created by the Human Owner is the single source of truth for problem statement, user behavior, and acceptance criteria.
- Do not create parallel task definitions that alter the meaning of the Issue.
- Local `TASK.md`, when needed for agent coordination, is strictly derived from the GitHub Issue.
- `pm_bot` may refine technical details in the existing Issue, but must not alter the owner's product intent.
- Do NOT auto-create new issues without explicit authorization from the owner. Propose out-of-scope findings to the owner instead of dumping them into the issue tracker.

## Privacy & Security Invariants

- **NEVER commit or expose real IP addresses of servers**: Always replace real server IPs with logical server names (e.g., `Server 8`, `Server 9`). Anonymize client IPs (e.g., `Client A`, `<client-ip>`).
- **NEVER commit or expose local paths**: Never include absolute local machine paths (e.g., `/home/...`, `/tmp/...`) in code, commits, PR descriptions, GitHub issues, comments, or task documentation. Use repository-relative paths only.
- **NEVER push documentation or task artifact folders (`docs/`, `tasks/`) to remote git branches or PRs**.
- **NEVER close issues prior to PR merge**: An issue remains OPEN through development, PR review, and CI verification, and is closed only after its PR is actually merged into `main`.
- **Zero emojis in commits, code, or task documentation**.
- **No em dashes in commit messages or agent communications**.
