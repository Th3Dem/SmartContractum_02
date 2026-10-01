# SmartContractum Agent Framework

This directory contains the multi-agent system profiles and operating procedures for the SmartContractum project (`Th3Dem/SmartContractum_02`).

These files define the identity, workflow constraints, roles, and handoff protocols for each automated agent.

## Directory Structure

- `workflow.md`: Master Operating Manual defining the state machine, GitHub-first lifecycle, test execution policy, and handoff protocols.
- `pm_bot.md`: Project Manager & Orchestrator. Coordinates the delivery cycle, analyzes issues, verifies Acceptance Criteria, and controls delivery up to `READY FOR OWNER MERGE`.
- `py_bot.md`: Senior Python Developer. Backend logic, SQLite schema, API endpoints, server-side invariants, and automated tests.
- `dev_bot.md`: Lead Frontend Developer. Client modules, responsive CSS, DOM interactions, accessibility, and client-side contract tests.
- `git_bot.md`: Git & PR Operations Specialist. Sole commit and push authority, branch lifecycle, PR management, and GitHub Actions CI watchdog.
- `ops_bot.md`: DevOps & Infrastructure Operations. Deployment management, container orchestration, and server health monitoring.

## Core Process & Operating Principle

The development workflow is GitHub-first:
1. **Human Owner** creates the GitHub Issue and initiates work: "Возьми Issue #N в работу".
2. **pm_bot** analyzes the issue, explores code and dependencies, refines technical details in the issue, and orchestrates specialist agents.
3. **Coding agents** (`py_bot`, `dev_bot`) implement code and required tests. Targeted local verification is allowed; redundant full local test runs are not mandatory.
4. **git_bot** creates feature branches, commits with Conventional Commits, pushes, opens PRs linking the issue, and tracks GitHub Actions CI.
5. **GitHub Actions** is the primary automated test runner. If CI fails, `pm_bot` organizes targeted fixes on the same branch until green.
6. **Two-gate verification**: PR is ready only after Gate 1 (Technical Checks GREEN) and Gate 2 (Acceptance Criteria verified by `pm_bot`).
7. **Owner Authority**: Workflow strictly stops at `READY FOR OWNER MERGE`. Agents never merge PRs, enable auto-merge, or deploy to production without explicit Human Owner command.
