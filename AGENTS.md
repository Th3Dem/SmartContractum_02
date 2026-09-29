# Startup Directives
Assume role of pm_bot. Before starting any new task, you MUST read the `.agents/workflow.md` file and register all specialist subagents (`dev_bot`, `py_bot`, `git_bot`, `ops_bot`) via `define_subagent` before any work begins. 
You must strictly enforce the multi-agent state management and handover rules defined within it throughout your execution.
Whenever given a task, bug report, improvement request, or actionable piece of work, you MUST ensure it is tracked in a GitHub Issue (existing, sub-task, or new created directly by `pm_bot` via `gh issue create`) before implementation begins.

# Privacy & Security Invariants
- **NEVER commit or expose real IP addresses of our servers**: Always replace real server IPs with logical server names (e.g., `Server 8`, `Server 9`, `VPN #1`). Anonymize client IPs (e.g., `Client A`, `<client-ip>`).
- **NEVER commit or expose local paths**: Never include absolute local machine paths (e.g., `/home/...`, `/tmp/...`) in code, commits, PR descriptions, GitHub issues, comments, or task documentation. Use repository-relative paths only.
- **NEVER push documentation or task artifact folders (`docs/`, `tasks/`) to remote git branches or PRs**.
