# SmartContractum Agent Framework

This directory contains the multi-agent system profiles and operating procedures for the SmartContractum project (`Th3Dem/SmartContractum_02`).

These files define the identity, workflow constraints, roles, and handoff protocols for each automated agent.

## Directory Structure

- `workflow.md`: Master Operating Manual defining the state machine, GitHub-first lifecycle, test execution policy, and handoff protocols.
- `pm_bot.md`: Project Manager & Orchestrator. Coordinates the delivery cycle, analyzes issues, verifies Acceptance Criteria, and controls delivery up to `READY FOR CLAUDE REVIEW`.
- `py_bot.md`: Senior Python Developer. Backend logic, SQLite schema, API endpoints, server-side invariants, and automated tests.
- `dev_bot.md`: Lead Frontend Developer. Client modules, responsive CSS, DOM interactions, accessibility, and client-side contract tests.
- `git_bot.md`: Git & PR Operations Specialist. Sole commit and push authority, branch lifecycle, PR management, and GitHub Actions CI watchdog.
- `ops_bot.md`: DevOps & Infrastructure Operations. Deployment management, container orchestration, and server health monitoring.

## Core Process & Operating Principle

The development workflow is GitHub-first:
1. **Human Owner** creates the GitHub Issue and initiates work: "Возьми Issue #N в работу".
2. **Claude Code** (a separate model, same folder, never at the same time) refines the Issue with the owner and pushes acceptance tests on the feature branch.
3. **pm_bot** analyzes the issue, explores code and dependencies, and orchestrates specialist agents on that branch.
4. **Coding agents** (`py_bot`, `dev_bot`) implement code and required tests. Targeted local verification is allowed; redundant full local test runs are not mandatory.
5. **git_bot** creates feature branches, commits with Conventional Commits, pushes, opens PRs linking the issue, and tracks GitHub Actions CI.
6. **GitHub Actions** is the primary automated test runner. If CI fails, `pm_bot` organizes targeted fixes on the same branch until green.
7. **Two-gate verification**: PR goes to review only after Gate 1 (Technical Checks GREEN) and Gate 2 (Acceptance Criteria verified by `pm_bot`). Gemini stops at `READY FOR CLAUDE REVIEW`.
8. **Claude Code review loop**: Claude reviews the PR on GitHub; findings come back to Gemini on the same branch until Claude's verdict `READY FOR OWNER MERGE` (up to 4 rework rounds, then the owner decides).
9. **Owner Authority**: Only the Human Owner merges. Agents never merge PRs, enable auto-merge, or deploy to production without explicit Human Owner command.

All agents share one local folder (`Projects_04`) and work strictly one after another; see `workflow.md` section 13.
