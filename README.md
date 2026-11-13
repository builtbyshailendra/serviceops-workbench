# serviceops-workbench

**A service request goes from intake to a human-approved action, and every step is written to an audit trail.**

> Personal learning project. Every person, team and request here is made up.

## Build log

### Step 1: requests table and intake API

**Built:** a FastAPI backend on PostgreSQL. One table holds service requests; `POST /api/requests` creates one as `new`, and two `GET` endpoints list and fetch them. There's no login: four made-up people (a requester, a service desk agent and two approvers) and the caller says who they are in an `X-Acting-As` header.

**Decision:** the most important rules also live in the database as `CHECK` constraints: a request past triage has a priority, an approved or rejected request records who decided and when, and nobody decides their own request. If the API ever has a bug, PostgreSQL still refuses the bad row. Tests insert bad rows directly to prove it.

**What broke:** the script that starts a local PostgreSQL hung on Windows after the server was already up. The server outlives the script and had inherited its output pipe, so whatever read that pipe waited forever. Redirecting the server's output to `/dev/null` fixed it.
