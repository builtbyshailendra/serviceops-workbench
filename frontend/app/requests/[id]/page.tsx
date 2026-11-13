"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useCallback, useEffect, useState } from "react";
import { api, type Action, type AuditEvent, type ServiceRequest, type Status } from "@/lib/api";
import { ACTION_WORDS, categoryLabel, formatTime, PRIORITY_LABEL, STATUS_LABEL } from "@/lib/labels";
import { useActingAs } from "../../acting-as";
import { StatusBadge } from "../../status-badge";

export default function RequestPage() {
  const { id } = useParams<{ id: string }>();
  const { me } = useActingAs();
  const [request, setRequest] = useState<ServiceRequest | null>(null);
  const [events, setEvents] = useState<AuditEvent[]>([]);
  const [error, setError] = useState<string | null>(null);

  // Reloads when the person changes, because what they can do depends on who they are.
  const load = useCallback(async () => {
    try {
      const [r, history] = await Promise.all([
        api<ServiceRequest>(`/api/requests/${id}`, { actingAs: me?.id }),
        api<AuditEvent[]>(`/api/requests/${id}/events`),
      ]);
      setRequest(r);
      setEvents(history);
      setError(null);
    } catch (e) {
      setError((e as Error).message);
    }
  }, [id, me?.id]);

  useEffect(() => {
    void load();
  }, [load]);

  if (error && !request) {
    return (
      <p className="banner error" role="alert">
        {error} <Link href="/">Back to all requests</Link>
      </p>
    );
  }
  if (!request) return <p className="muted">Loading…</p>;

  return (
    <div className="two-columns detail">
      <div>
        <Summary request={request} />
        <NextStep request={request} onChanged={load} />
      </div>
      <History events={events} />
    </div>
  );
}

function Summary({ request }: { request: ServiceRequest }) {
  const { nameOf } = useActingAs();
  return (
    <section className="card" aria-labelledby="request-heading">
      <p className="muted small">
        <Link href="/">All requests</Link> / #{request.id}
      </p>
      <h1 id="request-heading">{request.title}</h1>
      <p>
        <StatusBadge status={request.status} />
      </p>
      <dl className="facts">
        <dt>Category</dt>
        <dd>{categoryLabel(request.category)}</dd>
        <dt>Raised by</dt>
        <dd>
          {nameOf(request.requested_by)} on {formatTime(request.created_at)}
        </dd>
        <dt>Priority</dt>
        <dd>{request.priority ? PRIORITY_LABEL[request.priority] : "Not set yet"}</dd>
        <dt>Decision</dt>
        <dd data-testid="decision">{decisionText(request, nameOf)}</dd>
      </dl>
      {request.description && <p className="description">{request.description}</p>}
    </section>
  );
}

function decisionText(request: ServiceRequest, nameOf: (id: string | null) => string): string {
  if (!request.decided_by || !request.decided_at) return "Not decided yet";
  const verb = request.status === "rejected" ? "Rejected" : "Approved";
  return `${verb} by ${nameOf(request.decided_by)} on ${formatTime(request.decided_at)}`;
}

const WAITING: Record<Status, string> = {
  new: "Waiting for the service desk to triage it.",
  triaged: "Waiting for an approver to decide.",
  approved: "Approved. Waiting for the service desk to do the work.",
  rejected: "Rejected, so it's closed.",
  done: "Done. Nothing left to do.",
};

function NextStep({ request, onChanged }: { request: ServiceRequest; onChanged: () => Promise<void> }) {
  const { me } = useActingAs();
  const [note, setNote] = useState("");
  const [priority, setPriority] = useState("medium");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const allowed = request.allowed_actions;

  async function take(action: Action) {
    if (!me) return;
    setBusy(true);
    setError(null);
    try {
      await api(`/api/requests/${request.id}/${action}`, {
        method: "POST",
        body: action === "triage" ? { note, priority } : { note },
        actingAs: me.id,
      });
      setNote("");
      await onChanged();
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }

  if (!me) return null;

  if (allowed.length === 0) {
    const ownRequest = request.status === "triaged" && me.role === "approver" && me.id === request.requested_by;
    return (
      <section className="card" aria-labelledby="next-heading">
        <h2 id="next-heading">Next step</h2>
        <p>{WAITING[request.status]}</p>
        <p className="muted small">
          {ownRequest
            ? `${me.name} raised this request, so another approver has to decide.`
            : `Nothing for ${me.name} to do here right now.`}
        </p>
      </section>
    );
  }

  const noteLabel = allowed.includes("complete")
    ? "What was done"
    : allowed.includes("reject")
      ? "Note (needed to reject)"
      : "Note (optional)";

  return (
    <section className="card" aria-labelledby="next-heading">
      <h2 id="next-heading">Next step</h2>
      <div className="form">
        {allowed.includes("triage") && (
          <label>
            Priority
            <select value={priority} onChange={(e) => setPriority(e.target.value)}>
              <option value="low">Low</option>
              <option value="medium">Medium</option>
              <option value="high">High</option>
            </select>
          </label>
        )}
        <label>
          {noteLabel}
          <textarea value={note} onChange={(e) => setNote(e.target.value)} rows={3} maxLength={2000} />
        </label>
        <div className="buttons">
          {allowed.includes("triage") && (
            <button onClick={() => take("triage")} disabled={busy}>
              Triage
            </button>
          )}
          {allowed.includes("approve") && (
            <button onClick={() => take("approve")} disabled={busy}>
              Approve
            </button>
          )}
          {allowed.includes("reject") && (
            <button className="danger" onClick={() => take("reject")} disabled={busy}>
              Reject
            </button>
          )}
          {allowed.includes("complete") && (
            <button onClick={() => take("complete")} disabled={busy}>
              Mark done
            </button>
          )}
        </div>
      </div>
      {error && (
        <p className="banner error" role="alert">
          {error}
        </p>
      )}
    </section>
  );
}

function History({ events }: { events: AuditEvent[] }) {
  const { nameOf } = useActingAs();
  return (
    <section aria-labelledby="history-heading">
      <h2 id="history-heading">History</h2>
      <ol className="timeline">
        {events.map((e) => (
          <li key={e.id}>
            <div className="muted small">{formatTime(e.at)}</div>
            <div>
              <strong>{nameOf(e.actor)}</strong> {ACTION_WORDS[e.action] ?? e.action}
              {e.from_status && (
                <span className="muted">
                  {" "}
                  ({STATUS_LABEL[e.from_status]} → {STATUS_LABEL[e.to_status]})
                </span>
              )}
            </div>
            {e.note && <div className="note">{e.note}</div>}
          </li>
        ))}
      </ol>
    </section>
  );
}
