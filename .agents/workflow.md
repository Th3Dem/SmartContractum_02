# SmartContractum Multi-Agent Development Workflow: Operating Manual

This document defines the mandatory, state-driven lifecycle for feature development and bug fixes in SmartContractum (`Th3Dem/SmartContractum_02`). All agents (`pm_bot`, `dev_bot`, `py_bot`, `git_bot`, `ops_bot`) operate in isolated contexts and communicate via file-based artifacts and standard protocols.

The unified workflow invariant:

**Owner + ChatGPT create Issue → Claude Code refines it and writes acceptance tests → pm_bot takes Issue → agents implement code and tests on Claude's branch → PR created → GitHub Actions green → pm_bot verifies Acceptance Criteria → READY FOR CLAUDE REVIEW → STOP → Claude Code reviews → rework loop on the same branch until Claude's verdict READY FOR OWNER MERGE → only Human Owner merges → Issue closes only after actual merge → production deployment requires a separate Human Owner command.**

---

## 1. Roles and Responsibilities

### Human Owner
The human project owner is the ultimate decision maker:
- Formulates the product task and creates the initial GitHub Issue.
- Defines business requirements, user behavior, and acceptance criteria.
- Sets priorities and resolves trade-offs.
- Authorizes Pull Request merge into `main`.
- Authorizes production deployment.

### Claude Code (Issue refinement and review)
A separate model working in the same folder, never at the same time as Gemini:
- Refines the Issue with the owner until it is ready (Definition of Ready, section 12).
- Writes acceptance tests up front and pushes them on the feature branch Gemini continues.
- Reviews every Gemini PR on GitHub (`gh pr review`): code, tests, live check, design, privacy.
- Gives the only verdict that a PR is READY FOR OWNER MERGE.
- Never fixes Gemini's PR itself; every finding goes back to Gemini.

### pm_bot (Project Manager & Orchestrator)
`pm_bot` is the orchestrator and delivery owner, NOT a coding agent:
- Receives intake from the Human Owner: "Возьми Issue #N в работу", or a Claude review to rework: "Claude вернул PR #M на доработку".
- Analyzes the Issue, inspects the codebase, dependencies, and related PRs/issues.
- Refines technical details and Acceptance Criteria in the existing Issue without changing product intent.
- Decomposes work and selects specialist coding agents (`py_bot` for Python/backend, `dev_bot` for frontend/styling).
- Controls implementation and tracks GitHub Actions CI.
- Organizes fixes if CI checks fail.
- Verifies Acceptance Criteria once CI is green.
- Conducts final PR inspection and drives the task to `READY FOR CLAUDE REVIEW`.
- Halts the workflow and waits for the Human Owner's explicit decision.

### Coding Agents (`py_bot`, `dev_bot`)
Specialist developers responsible for implementation quality:
- Implement clean, minimal code satisfying the Issue requirements.
- Create and update automated tests (unit, integration, regression, browser smoke) as part of implementation.
- Perform targeted local verification when helpful.
- Fix defects identified by GitHub Actions CI.
- Adhere strictly to Issue scope (no scope creep).
- Hand off via compact `DEV_HANDOVER.md` to `pm_bot`.
- NEVER commit or push code directly (delegated to `git_bot`).

### git_bot (GitHub Operations Specialist)
Sole authority for version control operations:
- Creates feature branches from latest `main`.
- Formats atomic commits using Conventional Commits (`feat:`, `fix:`, `refactor:`, `test:`, `chore:`).
- Pushes branches and automatically opens Pull Requests targeting `main` referencing `Fixes #<issue>`.
- Serves as CI watchdog: monitors GitHub Actions and extracts failed job logs (`gh run view <id> --log-failed`).
- Transmits CI failure logs to `pm_bot` for targeted triage.
- NEVER merges PRs, enables auto-merge, or commits directly to `main`.

### ops_bot (DevOps & Infrastructure)
Manages server infrastructure and deployments:
- Executes deployments strictly upon separate, explicit command from the Human Owner.
- Never deploys automatically upon PR merge or green CI.
- Preserves security: temporary credentials cleaned up immediately, zero real server IPs logged.

### GitHub Actions
The primary, independent automated testing environment:
- Executes required checks defined in `.github/workflows/*`.
- Serves as the authoritative source of truth for automated test results.

---

## 2. End-to-End Lifecycle

```text
Owner + ChatGPT create Issue
        ↓
Claude Code refines Issue with owner (Definition of Ready), pushes feature branch
with acceptance tests, sets label ready-for-gemini
        ↓
Owner: «Возьми Issue #N в работу»
        ↓
pm_bot reads Issue, Claude's notes and acceptance tests, explores code
        ↓
pm_bot assigns work to coding agent (dev_bot / py_bot) on Claude's branch
        ↓
coding agent implements changes and tests until acceptance tests pass
        ↓
git_bot commits, pushes, opens PR (Fixes #<issue>)
        ↓
GitHub Actions runs required checks; if RED: fix loop on the same branch until GREEN
        ↓
Gate 1: Technical CI GREEN
Gate 2: Acceptance Criteria verified by pm_bot, quality bar of section 14 met
        ↓
Final PR inspection, label in-review
        ↓
READY FOR CLAUDE REVIEW -> STOP, folder handed back clean (section 13)
        ↓
Claude Code review on GitHub
   changes requested -> label changes-requested -> owner: «Claude вернул PR #M на доработку»
                     -> rework on the same branch (section 12) -> READY FOR CLAUDE REVIEW again
   approved          -> label ready-to-merge -> owner merges
```

## 3. GitHub Issue as Single Source of Truth

1. **Issue Definition**: The GitHub Issue contains the problem statement, user-facing behavior, scope boundaries, and acceptance criteria.
2. **No Parallel Drift**: Agents must not create parallel task documents that alter or override the Issue's meaning. Local `tasks/<issue-folder>/TASK.md` is strictly derived from the GitHub Issue for agent coordination.
3. **Technical Refinement**: If an Issue needs technical clarification, `pm_bot` investigates the code and updates the existing Issue with technical precision while strictly preserving the owner's product intent.
4. **Issue Discipline (No Automatic Dumps)**:
   - Do not auto-create new issues for internal steps, theoretical edge cases, or routine refactors.
   - If an out-of-scope defect is discovered: evaluate whether it blocks the current issue. If not, record it as a potential follow-up and report it to the owner.
   - New issues are created ONLY upon explicit instruction from the Human Owner.
5. **Issue Status**: An Issue remains `OPEN` through all development, review, and CI verification phases. It is closed ONLY after the PR is actually merged into `main`.

---

## 4. Branch and Commit Policy

- **One Issue → One Branch → One PR**: Each task is developed in a dedicated feature branch created from latest `main`.
- **Branch Naming**:
  - `feature/<issue-number>-<short-name>`
  - `fix/<issue-number>-<short-name>`
  - `refactor/<issue-number>-<short-name>`
  - `cleanup/<issue-number>-<short-name>`
- **No Direct Push to main**: Development directly on `main` is strictly forbidden for all agents.
- **Conventional Commits**: Commits must use standard semantic prefixes:
  - `feat:` for new capabilities
  - `fix:` for bug fixes
  - `refactor:` for internal restructuring without behavior change
  - `test:` for test additions or updates
  - `chore:` for build, CI, or dependency maintenance
  - No vague messages (`update`, `fix`, `changes`, `fix2`).
- **Clean History**: Do not generate excessive micro-commits unless addressing separate CI feedback cycles.

---

## 5. Automated Testing and CI Strategy

### GitHub Actions as Primary Test Runner
Automated testing is conducted independently in GitHub Actions:
- Code and tests are pushed to the feature branch.
- GitHub Actions runs the workflow specified in `.github/workflows/*`.
- GitHub Actions run logs and check statuses are the definitive source of truth.

### Local Verification Principles
- **No Mandatory Full Suite Gate**: Coding agents and `pm_bot` are NOT required to run the entire project regression suite or full browser smoke suite locally before handoff.
- **Targeted Local Checks Allowed**: Targeted checks are encouraged when they save time or assist iterative development:
  - Running a single relevant unit test file.
  - Quick syntax/compile check (`python3 -m py_compile <file>`).
  - Targeted reproduction of a specific bug or CI failure.
- **Principle**: Targeted local verification is allowed; redundant full local CI is not mandatory.

### CI Failure Recovery Loop
If GitHub Actions reports a failure (RED):
1. `git_bot` identifies the failing check and fetches failure logs:
   ```bash
   gh run view <run-id> --log-failed
   ```
2. `pm_bot` analyzes the failure and routes the exact issue to the coding agent.
3. The coding agent fixes the defect and updates the relevant tests.
4. `git_bot` commits the fix and pushes to the **same** branch.
5. GitHub Actions automatically re-triggers checks.
6. The loop repeats until all required checks are GREEN. Never open a new PR for CI fixes.

### CI Evolution Guidelines
- Required checks are determined by `.github/workflows/*` and repository branch protection settings.
- CI should run necessary and sufficient checks, not bloated suites without purpose.
- When projects grow, a tiered workflow may be established (fast required checks on PR, complete regression on `main`, scheduled nightly for long-running tests). Reliability must never be compromised for speed.

---

## 6. Pull Request Protocol and Inspection

### Automatic PR Creation
Once initial implementation and tests are complete, `git_bot` opens the PR targeting `main`. The PR body must be compact and clear:

```markdown
## Issue
Fixes #<issue-number>

## What
- Concise summary of changes

## Why
- Business/technical rationale from the Issue

## Acceptance Criteria
- [x] Invariant 1 verified
- [x] Invariant 2 verified

## Tests added/changed
- tests/test_<issue>...

## Known risks / notes
- Residual risks or deployment notes
```

### Dual Verification Gates before READY FOR CLAUDE REVIEW
A Pull Request can ONLY be handed to Claude Code for review when BOTH gates pass:
- **Gate 1 (Technical)**: All required GitHub Actions checks are GREEN.
- **Gate 2 (Product / Acceptance)**: `pm_bot` has verified that all Acceptance Criteria and expected user behaviors from the Issue are satisfied.

### Final PR Inspection Checklist
Before declaring `READY FOR CLAUDE REVIEW`, `pm_bot` must verify:
- [ ] PR correctly references `Fixes #<issue>`.
- [ ] Scope strictly matches the Issue (no accidental scope creep).
- [ ] No merge conflicts with `main`.
- [ ] No internal task folders (`tasks/`, `docs/`) in staged files or git history.
- [ ] Zero real server IP addresses (only logical names like `Server 8`).
- [ ] Zero local filesystem paths (`/home/...`, `/tmp/...`).
- [ ] Zero emojis in code, commits, or PR description.
- [ ] No em dashes in commit messages.
- [ ] All required GitHub Checks are GREEN.
- [ ] All Acceptance Criteria are proven.
- [ ] Claude's acceptance tests are present and unchanged, or every change is explained in the PR.
- [ ] Quality bar of section 14 is met (regression tests, UI checks, live check).
- [ ] Every finding of the previous Claude review is answered (rework rounds only).

---

## 7. Delivery Completion & Stopping Rule

When both gates and inspection pass:
```text
Issue #<number>: OPEN
PR #<number>: OPEN
Required GitHub Checks: GREEN
Acceptance Criteria: VERIFIED
Review round: <N> of 4
Status: READY FOR CLAUDE REVIEW
```

At this point, the agent workflow **STOPS** and the folder is handed back clean (section 13). The owner takes the PR to Claude Code. READY FOR OWNER MERGE is Claude's verdict only; Gemini never reports it.

### Absolute Prohibitions without Human Command
Agents are strictly prohibited from:
- Merging the PR (merge, squash merge, rebase merge);
- Enabling GitHub auto-merge;
- Executing merge via GitHub CLI (`gh pr merge`) or API;
- Deploying to production;
- Closing the Issue before the PR is merged into `main`.

---

## 8. Merge and Production Deployment Separation

- **Owner Command for Merge**: Only the Human Owner may authorize merging the PR (e.g., "Merge PR #N" or clicking Merge in GitHub UI).
- **Issue Closure**: Upon successful merge into `main`, GitHub automatically closes the Issue via `Fixes #<issue>`. If not auto-closed, `pm_bot` confirms the merge and closes the Issue.
- **Deployment is Never Automatic**: Merging a PR to `main` NEVER authorizes production deployment.
- **Explicit Deployment Command**: Production deployment requires a separate, explicit command from the Human Owner (e.g., "Deploy production"). `ops_bot` will only then execute the deployment.

---

## 9. Handling Owner Feedback on Green PRs

Claude review findings follow section 12. If the Human Owner requests adjustments directly:
1. Both Issue and PR remain `OPEN`.
2. `pm_bot` decomposes the requested adjustments and delegates to coding agents.
3. Fixes are committed to the **same** branch and pushed.
4. GitHub Actions re-runs CI checks.
5. `pm_bot` re-verifies Acceptance Criteria.
6. Workflow halts again at `READY FOR CLAUDE REVIEW`.

---

## 10. Compact Developer Handover (`DEV_HANDOVER.md`)

Coding agents write a compact handover in `tasks/<issue-folder>/DEV_HANDOVER.md`:

```markdown
# Development Handover: Issue #<number>

## Implementation
- Brief summary of technical changes

## Files Changed
- path/to/file.py (modified)
- tests/test_feature.py (new)

## Tests Added / Changed
- tests/test_feature.py: Test descriptions and coverage

## Known Risks / Notes
- Classification: HARDENING or THEORETICAL notes

## Expected GitHub Checks
- CI Pipeline / test
```

Do NOT embed raw stdout dumps or hundred-line test terminal logs into handover artifacts. GitHub Actions preserves all CI execution logs.

---

## 11. Global State Management (`WORKLOG.md`)

All key transitions are logged in `WORKLOG.md` at project root:
Format: `[YYYY-MM-DD HH:MM] | <agent> | <ACTION> | <description> (Task: <task-id>)`

Standard Actions:
- `TASK_INIT`: `pm_bot` starts intake for Issue
- `DEV_ASSIGN`: `pm_bot` assigns work to coding agent
- `IMPLEMENTATION_COMPLETE`: coding agent finishes implementation and tests
- `PR_CREATED`: `git_bot` opens PR on GitHub
- `CI_FAILED`: `git_bot` reports failing CI run
- `DEV_REWORK`: `pm_bot` routes CI failure back to coding agent
- `READY_FOR_CLAUDE_REVIEW`: `pm_bot` confirms green CI + verified acceptance criteria; halts workflow
- `REVIEW_REWORK`: `pm_bot` starts a rework round after a Claude review (round N of 4)
- `PR_MERGED`: `git_bot` logs confirmation after Human Owner merges PR
- `DEPLOY_COMPLETE`: `ops_bot` logs production deployment execution

---

## 12. Claude Code Review Loop

### Definition of Ready (before Gemini starts)
Claude Code and the owner bring the Issue to this state before the label `ready-for-gemini`:
- product intent unchanged from the owner's Issue;
- testable Acceptance Criteria, scope and explicit out-of-scope;
- affected modules and files, related Issues and PRs;
- risks, security and privacy notes;
- for UI: widths, themes and states to check;
- how to verify it live;
- acceptance tests pushed on the feature branch named in the Issue (`feat/issue-<N>-<short-name>` or `fix/...`).

### Starting the work
- `git_bot` checks out the branch Claude named in the Issue (`git fetch && git checkout <branch> && git pull`) instead of creating a new one. Only when the Issue names no branch, create one from latest `main` as in section 4.
- Claude's acceptance tests define "done". They fail before the implementation and must pass after it.
- Never delete, skip or weaken an acceptance test to make it pass. If a test is wrong or contradicts the Issue, stop and report it to the owner for Claude; any agreed change is listed in the PR.

### Review comments
- Claude reviews on GitHub with severities: **blocker** (must fix before merge), **major** (must fix), **minor** (fix or answer).
- Read them with `gh pr view <M> --comments` and `gh api repos/Th3Dem/SmartContractum_02/pulls/<M>/comments`.
- Fix every blocker and major on the **same** branch, never in a new PR. For each finding, reply on the PR with what was changed, or why not (minor only).
- Do not change code that the review did not ask for (no drive-by refactoring in rework rounds).

### Rounds
- Count review rounds in the PR conversation and in `WORKLOG.md` (`REVIEW_REWORK`, round N of 4).
- After the 4th return for rework the owner decides whether Claude Code takes the task over. Gemini stops and waits.

### Labels
`ready-for-gemini` (Issue ready), `in-review` (PR waits for Claude), `changes-requested` (rework needed), `ready-to-merge` (Claude approved). Gemini sets `in-review` on the PR when it stops; Claude sets the others.

---

## 13. Shared Working Folder (Projects_04)

Gemini and Claude Code use the same local folder, strictly one after another.

- **One agent at a time.** Start only when the owner hands you the folder; never run while the other model works.
- **Start of a session:** `git status` must be clean. If it is not, stop and report; never discard someone else's changes.
- **End of a session (handoff):** everything committed and pushed to the feature branch, then `git checkout main && git pull`, `git status` clean. Local artifacts stay ignored (`tasks/`, `data/`, `.env`).
- **Local data is shared and precious.** `data/moderation.db` and `data/media/` hold the owner's real local portal content. Never delete, reset, reseed or migrate them by hand. Live checks run on a copy: `python3 server.py --port 8765 --db <copy>` with a copied `MEDIA_DIR` when uploads are involved.
- **One local server.** `localhost:8000` serves this folder. Restart it after switching branches (Python modules load at start); stop throwaway servers when done.
- **Files of the other model:** `CLAUDE.md` is Claude's local file, do not edit or commit it. Claude changes Gemini rule files only through a PR the owner merges.

---

## 14. Quality Bar Claude Code Checks

A PR passes Claude's review only if:
- **Scope:** every changed line traces to the Issue; no unrelated refactoring; found side issues are reported, not fixed silently.
- **Tests prove behavior,** not the presence of strings in source files. Server behavior through HTTP (`tests/http_client.py`), UI behavior through browser tests (`BROWSER_SMOKE = True`, collected by `tests/run_browser_smoke.py`; do not edit `ci.yml`).
- **Bug fixes** include a test that fails without the fix and passes with it (prove it by running the test against `main`).
- **Races and intermittent failures** are reproduced with forced delays before being called flaky.
- **UI tasks:** checked at 320, 375, 414, 768, 1024 px and desktop, light and dark themes, keyboard; no horizontal scroll, nothing clipped; buttons 32 to 34 px (44 px on touch). State it in the PR.
- **Live check** on a copy of the DB with the user scenarios from the Issue, described in the PR (what was run and what was seen).
- **No demo content in product code** (Issue #284): demo data lives only in `tests/fixtures/`; the five real starter authors are `tests/fixtures/starter_content.py`. Never add fake materials, authors or fallbacks to `backend/` or `frontend/`.
- **Security:** escaping of user data, CSRF on writes, authorization on every endpoint, sanitizer allowlists kept strict.
- **Privacy and style:** no IPs, local paths, secrets, `data/` or `tasks/` in the diff; no emojis and no em dashes; Conventional Commits; PR sections Issue / What / Why / Acceptance Criteria / Tests / Known risks.
