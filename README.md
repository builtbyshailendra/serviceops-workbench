# serviceops-workbench

**A service request goes from intake to a human-approved action, and every step is written to an audit trail.**

> Personal learning project. Every person, team and request here is made up.

## Build log

### Step 1: requests table and intake API

**Built:** a FastAPI backend on PostgreSQL. One table holds service requests; `POST /api/requests` creates one as `new`, and two `GET` endpoints list and fetch them. There's no login: four made-up people (a requester, a service desk agent and two approvers) and the caller says who they are in an `X-Acting-As` header.

**Decision:** the most important rules also live in the database as `CHECK` constraints: a request past triage has a priority, an approved or rejected request records who decided and when, and nobody decides their own request. If the API ever has a bug, PostgreSQL still refuses the bad row. Tests insert bad rows directly to prove it.

**What broke:** the script that starts a local PostgreSQL hung on Windows after the server was already up. The server outlives the script and had inherited its output pipe, so whatever read that pipe waited forever. Redirecting the server's output to `/dev/null` fixed it.

### Step 2: status flow and the approval step

**Built:** four steps, each with one role allowed to take it: the service desk triages (and sets a priority), an approver approves or rejects, and the service desk completes. Approving and rejecting are the human decision, so they record who decided and when. Rejecting needs a reason and completing needs a note on what was done. Every refusal says why in plain words, for example `Can't approve a request that is new. It has to be triaged first.` The rules live in one small file with no database, so they're easy to test on their own.

**What broke:** my first test for two approvers clicking at once was useless. It started both approvals together and expected one to win, but it passed five times out of five with the row lock turned off, because the two requests never really overlapped. The new test holds the row open the way a slow first approval would, then sends the second. With the lock, the second approver waits and gets `409`. Without it, the second approval quietly overwrites the first, and the test fails.

### Step 3: audit trail

**Built:** an `audit_events` table. Creating a request and every step write one event (who, what, from which status to which, the note and the time) in the same transaction as the change, so a change can't happen without its event. `GET /api/requests/{id}/events` returns one request's history and `GET /api/audit` returns everything, newest first.

**Decision:** the API never edits or deletes events, but that's only a promise. A PostgreSQL trigger makes it a rule: any `UPDATE` or `DELETE` on `audit_events` fails with `audit_events is append-only`. The foreign key also stops a request with history from being deleted. Tests try all three straight against the database.

**Learned:** the approval time on the request and the time on its audit event are exactly equal, not just close. PostgreSQL's `now()` is fixed at the start of a transaction, and both rows are written in one.

### Step 4: intake form and request list

**Built:** a Next.js frontend. The home page has a form to raise a request and a table of every request with its status, priority and who raised it. An "Acting as" picker in the header replaces a login; it's remembered in the browser and sent with every API call. Next.js passes `/api/*` on to FastAPI, so the browser sees one origin and there's no CORS setup.

**Decision:** pinned TypeScript to 5.9. The newest release is TypeScript 7, the rewrite in Go, and I'd rather not find out mid-build whether Next.js's type checking works with it yet.
