### End-to-End Multi-Agent Development Workflow: Operating Manual

This document defines the strict, state-driven lifecycle of a feature request on the Antigravity platform. All subagents (`pm_bot`, `dev_bot`, `py_bot`, `git_bot`, `ops_bot`) operate in isolated contexts and communicate exclusively through file-based artifacts and standard operating procedures.

#### 1. The End-to-End Process
The lifecycle follows a deterministic, sequential state machine:
0. **Agent Registration (`pm_bot`)**: Before any planning or work begins, `pm_bot` MUST register all specialist agents (`dev_bot`, `py_bot`, `git_bot`, `ops_bot`) using `define_subagent`, loading their roles, system prompts, and tool configurations from `.agents/<bot_name>.md`.
1. **Intake, Issue Tracking & Planning (`pm_bot`)**: The orchestrator receives the human prompt, inspects existing GitHub Issues, and ensures the task is tracked by an existing issue, a sub-task, or a new issue created directly by `pm_bot` (`gh issue create`). The GitHub Issue tracker is the source of truth for planned and actionable work. Never silently implement a task without tracking it in GitHub Issues. The orchestrator decomposes the requirements and writes them to `tasks/<issue-folder>/TASK.md` referencing the tracking issue.
2. **Delegation (`pm_bot` → Developer)**: `pm_bot` spawns the specialist agent (e.g., `py_bot` for Python or `dev_bot` for Go) via `invoke_subagent`, passing the `TASK.md` path and enforcing the `flash` model.
3. **Execution & Compilation (`dev_bot`/`py_bot`)**: The developer executes TDD. They are blocked by a **Hard Compilation Gate** (linting, tests, security scans). Code is refactored locally until all exit codes are `0`.
4. **Developer Handoff**: Once tests pass, the developer writes `DEV_HANDOVER.md` and updates the state.
5. **Smoke Verification (`pm_bot`)**: The orchestrator runs a sanity compilation (e.g., `go build ./...`). If it fails, the task immediately bounces back to the developer.
6. **Version Control (`git_bot`)**: Upon successful smoke verification, `pm_bot` spawns `git_bot`. It reads the state log, creates a branch, commits the delta, pushes to origin, opens a PR, and monitors the CI/CD pipeline.
7. **Done-Done Reporting (`pm_bot`)**: The orchestrator confirms CI/CD success, updates global state, and returns control to the human.

#### 2. State Management & Logging (`WORKLOG.md`)
`WORKLOG.md` acts as the immutable global state machine and single source of truth for agent coordination.
- **Purpose**: It prevents context degradation across isolated subagent boundaries, provides historical tracking, and governs loop limits.
- **Lifecycle**:
  - `pm_bot` initializes the cycle: `[TS] | pm_bot | PROJECT_START | <desc>`
  - Developer claims task: `[TS] | dev_bot | IMPLEMENTATION_START | <desc>`
  - Developer yields task: `[TS] | dev_bot | IMPLEMENTATION_COMPLETE | <desc>`
  - Git operations: `[TS] | git_bot | PR_CREATED | <url>`
  - Cycle completed: `[TS] | pm_bot | PROJECT_COMPLETED | <desc>`
- **Loop Prevention**: `pm_bot` continuously parses `WORKLOG.md`. If it detects the `DEV_REWORK` state more than twice for the same task, it aborts the loop, halts the state machine, and triggers a human escalation.

#### 3. Handover Documents
Subagents do not pass conversational context. Handovers are entirely payload-driven via standard Markdown schemas located in `tasks/<issue-folder>/`.

**`TASK.md` (Initial Payload)**
- **Author**: `pm_bot`
- **Contents**: Architecture specs, scope constraints, database schemas, and explicit "Do Nots".

**`DEV_HANDOVER.md` (Developer → Orchestrator & Git Payload)**
- **Author**: `dev_bot` or `py_bot`
- **Contents**: 
  - *Files Changed*: Exact diff manifest.
  - *Test Results*: Raw `stdout` of passing coverage targets (`pytest --cov` or `go test -cover`).
  - *Linter/Security Output*: Raw `stdout` proving clean runs of `gosec`, `govulncheck`, `flake8`, `pip-audit`.
  - *Notes / Verification Details*: Expected edge cases, concurrency models, and data validation assumptions.

#### 4. File Generation & Artifact Location Convention
**STRICT CONSTRAINT**: All task-related work files, scratchpads, PR bodies, and intermediate artifacts MUST be saved inside the designated task folder (`tasks/<issue-folder>/`). They must NOT be saved in the repository root.

During a standard feature implementation cycle, the following non-source files are generated and stored strictly in the task folder:
- `tasks/<issue-folder>/TASK.md` (Scope mapping)
- `tasks/<issue-folder>/DEV_HANDOVER.md` (Execution evidence)
- `tasks/<issue-folder>/pr_body.txt` (or any other git/PR related drafts)

The ONLY exceptions permitted in the repository root are:
- `WORKLOG.md` (Global execution state)
- `CICD_ERRORS.md` (Generated at root only if `git_bot` detects a remote pipeline failure post-push)

**Privacy & Sanitization Rules**:
- **Zero Server IP Exposure**: NEVER record, commit, or push real IP addresses of project servers. Always map IPs to logical server identifiers (`Server <ID>`, `Server 8`, etc.) and anonymize client IPs (`Client A`, `<client-ip>`).
- **Zero Local Path Exposure**: NEVER record, commit, or push absolute local paths (`/home/...`, `/tmp/...`). All path references in task files, PR bodies, and commit messages must be relative to the repository root.
- **Never Push Docs/Tasks**: Documentation and task folders (`docs/`, `tasks/`) are strictly local working directories and must NEVER be pushed to remote branches or opened as PRs.


#### 5. Failure & Recovery
The system leverages cascading failure recovery:
- **Local Dev Breakage (Compilation/Test Fails)**: Addressed locally by the developer subagent. Creating a handover document while tests fail is a hard constraint violation. The developer loops internally until `stdout` shows success.
- **Smoke Verification Breakage**: If `pm_bot` detects compilation or basic check failures during smoke verification, it logs `DEV_REWORK` in `WORKLOG.md` and respawns the developer subagent with the error trace to resolve the issue.
- **Pipeline Failure**: If tests pass locally but fail in GitHub Actions, `git_bot` parses the failed job logs via `gh run view`, dumps the trace into `CICD_ERRORS.md`, and passes state back to `pm_bot` for another `DEV_REWORK` cycle.
