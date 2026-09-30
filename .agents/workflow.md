### End-to-End Multi-Agent Development Workflow: Operating Manual

This document defines the strict, state-driven lifecycle of a feature request on the Antigravity platform. All subagents (`pm_bot`, `dev_bot`, `py_bot`, `git_bot`, `ops_bot`) operate in isolated contexts and communicate exclusively through file-based artifacts and standard operating procedures.

The system enforces a goal-driven loop:
`FIND -> CLASSIFY -> PRIORITIZE -> DECIDE -> IMPLEMENT -> VERIFY -> MERGE`

#### 1. The Issue and Implementation Lifecycle
The lifecycle follows a deterministic state machine:

0. **Agent Registration (`pm_bot`)**:
   - Before any planning or work begins, `pm_bot` MUST register all specialist agents (`dev_bot`, `py_bot`, `git_bot`, `ops_bot`) using `define_subagent`, loading their roles, system prompts, and tool configurations from `.agents/<bot_name>.md`.

1. **Issue: OPEN**:
   - `pm_bot` inspects existing GitHub Issues.
   - The issue defines the business problem, production impact, and explicit acceptance criteria based on business invariants.
   - Never use the issue tracker as a dev scratchpad or journal of theoretical edge cases.

2. **Issue: IN_PROGRESS (Intake & Test Boundaries)**:
   - `pm_bot` creates `tasks/<issue-folder>/TASK.md`.
   - For concurrency or distributed logic, `TASK.md` MUST specify upfront **Test Boundaries** ("Must Prove" invariants list).
   - `pm_bot` spawns the developer bot (`py_bot` or `dev_bot`) enforcing the `flash` model.

3. **Issue: IMPLEMENTED (Execution & Hard Compilation Gate)**:
   - The developer writes code and tests satisfying the "Must Prove" invariants.
   - Blocked by the Hard Compilation Gate (linting, tests, security scans).
   - Once tests pass, the developer writes `tasks/<issue-folder>/DEV_HANDOVER.md` documenting verified invariants and any residual risks.
   - State: code is implemented locally, but NOT yet part of `main`.

4. **Issue: VERIFIED (Smoke Check & PR Opening)**:
   - `pm_bot` runs smoke verification.
   - If clean, `pm_bot` spawns `git_bot`.
   - `git_bot` creates a feature branch, commits, pushes, and opens a PR referencing `Fixes #<issue>`.
   - Acceptance criteria in the issue reflect: `[ ] Invariant (Status: implemented in PR #..., awaiting merge)`.
   - `git_bot` monitors CI/CD.

5. **Issue: MERGED & CLOSED**:
   - The PR is reviewed, verified, and merged into `main`.
   - The issue is closed automatically via GitHub `Fixes #<issue>` or closed by `pm_bot` strictly after merge is confirmed.
   - **RULE**: An issue is NEVER marked closed when a developer finishes coding. `CLOSED` strictly requires the code to be merged into `main`.

#### 2. Merge Readiness and Finding Classification Matrix
To prevent endless edge-case discovery loops ("issue explosion"), all findings during implementation and review MUST be classified before taking action:

| Classification | Definition | Action |
|---|---|---|
| **BLOCKER** | Direct violation of business invariant in normal operations (e.g. duplicate IP, lost peer, config corruption). | Must fix in current PR. Blocks merge. |
| **HIGH** | Divergence or failure under probable network or process crash. | Must fix in current PR. |
| **MEDIUM** | Localized defect without risk of data or configuration corruption. | Fix in current PR or defer to single follow-up. |
| **HARDENING** | Extremely specific interleaving when core production invariants are already protected. | Document in PR review notes; do not block PR merge. |
| **THEORETICAL** | Race requiring multiple precisely timed, unlikely failures. | Document in `DEV_HANDOVER.md` as residual risk; do NOT create an issue. |

**Stop Rule**: Once all production-critical invariants ("Must Prove" list) pass tests, new theoretical findings do NOT block merge.

#### 3. Concurrency Test Boundaries
For complex concurrent or stateful mechanisms, `TASK.md` must lock in the test boundaries upfront.
Example "Must Prove" list:
- No duplicate resource allocation under concurrent requests.
- No lost or overwritten records/peers.
- Rollback removes exactly the intended target.
- Database state and remote configuration never silently diverge.
- Crash recovery does not permanently corrupt state.

Once these properties are proven by automated tests, theoretical interleavings are classified under the risk rubric rather than triggering automatic blocking issues.

#### 4. Architectural Escape Hatch
If a complex synchronization mechanism or locking protocol requires more than 2 rework iterations (`DEV_REWORK`) or produces recursive edge-case fixes:
1. `pm_bot` halts the micro-patching cycle.
2. An architectural review is triggered to evaluate replacing the primitive with a simpler pattern:
   - Standard `flock` / atomic filesystem operation.
   - Existing locking primitive or single-owner queue.
   - Database transactional lock.
3. Current PR fixes confirmed production bugs and merges. Simplification is scheduled as a clean, independent architectural task.

#### 5. State Management & Logging (`WORKLOG.md`)
`WORKLOG.md` acts as the immutable global state machine:
- `[TS] | pm_bot | PROJECT_START | <desc>`
- `[TS] | dev_bot | IMPLEMENTATION_START | <desc>`
- `[TS] | dev_bot | IMPLEMENTATION_COMPLETE | <desc>`
- `[TS] | git_bot | PR_CREATED | <url>`
- `[TS] | git_bot | PR_MERGED | <url>`
- `[TS] | pm_bot | PROJECT_COMPLETED | <desc>`

**Loop Prevention**: If `pm_bot` detects `DEV_REWORK` more than twice for the same task, it halts and triggers human escalation or an architectural review.

#### 6. Handover Documents
- `tasks/<issue-folder>/TASK.md`: Architecture specs, scope constraints, and explicit "Must Prove" invariants.
- `tasks/<issue-folder>/DEV_HANDOVER.md`:
  - Files Changed (diff manifest).
  - Test Results (raw stdout of coverage).
  - Linter & Security Scan outputs.
  - Invariants Verified (evidence mapping).
  - Residual Risks (classified as HARDENING or THEORETICAL).

#### 7. Artifact Location & Privacy Invariants
All task-related files must live in `tasks/<issue-folder>/`. Only `WORKLOG.md` and `CICD_ERRORS.md` are permitted at repository root.
- **Zero Server IP Exposure**: Never commit or expose real server IPs. Use logical identifiers (`Server 8`, `Server 9`). Anonymize client IPs.
- **Zero Local Path Exposure**: Never commit or expose absolute local paths. Use repository-relative paths only.
- **Never Push Docs/Tasks**: `docs/` and `tasks/` are strictly local working folders and must never be pushed to remote branches.

#### 8. Failure & Recovery
- **Local Dev Breakage**: Handled internally by developer bot before handover.
- **Smoke Verification Breakage**: If smoke test fails, `pm_bot` logs `DEV_REWORK` and sends the trace back to developer.
- **Pipeline Failure**: `git_bot` dumps failed job logs into `CICD_ERRORS.md` for a rework cycle.
