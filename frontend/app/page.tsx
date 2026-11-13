"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import { api, type ServiceRequest } from "@/lib/api";
import { CATEGORIES, categoryLabel, formatTime, PRIORITY_LABEL } from "@/lib/labels";
import { useActingAs } from "./acting-as";
import { StatusBadge } from "./status-badge";

export default function RequestsPage() {
  const [requests, setRequests] = useState<ServiceRequest[] | null>(null);
  const [loadError, setLoadError] = useState<string | null>(null);

  const load = useCallback(() => {
    api<ServiceRequest[]>("/api/requests").then(
      (rows) => {
        setRequests(rows);
        setLoadError(null);
      },
      (e: Error) => setLoadError(e.message),
    );
  }, []);

  useEffect(load, [load]);

  return (
    <div className="two-columns">
      <IntakeForm onCreated={load} />
      <section aria-labelledby="list-heading">
        <h2 id="list-heading">All requests</h2>
        {loadError && (
          <p className="banner error" role="alert">
            {loadError}
          </p>
        )}
        {requests === null && !loadError && <p className="muted">Loading…</p>}
        {requests?.length === 0 && <p className="muted">No requests yet. Raise the first one.</p>}
        {requests && requests.length > 0 && <RequestTable requests={requests} />}
      </section>
    </div>
  );
}

function RequestTable({ requests }: { requests: ServiceRequest[] }) {
  const { nameOf } = useActingAs();
  return (
    <div className="table-wrap">
      <table>
        <thead>
          <tr>
            <th>#</th>
            <th>Request</th>
            <th>Status</th>
            <th>Priority</th>
            <th>Raised by</th>
            <th>Updated</th>
          </tr>
        </thead>
        <tbody>
          {requests.map((r) => (
            <tr key={r.id}>
              <td className="muted">{r.id}</td>
              <td>
                <Link href={`/requests/${r.id}`}>{r.title}</Link>
                <div className="muted small">{categoryLabel(r.category)}</div>
              </td>
              <td>
                <StatusBadge status={r.status} />
              </td>
              <td>{r.priority ? PRIORITY_LABEL[r.priority] : <span className="muted">Not set</span>}</td>
              <td>{nameOf(r.requested_by)}</td>
              <td className="small">{formatTime(r.updated_at)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function IntakeForm({ onCreated }: { onCreated: () => void }) {
  const { me } = useActingAs();
  const [title, setTitle] = useState("");
  const [category, setCategory] = useState("access");
  const [description, setDescription] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [created, setCreated] = useState<ServiceRequest | null>(null);

  async function submit(event: React.FormEvent) {
    event.preventDefault();
    if (!me) return;
    setBusy(true);
    setError(null);
    try {
      const request = await api<ServiceRequest>("/api/requests", {
        method: "POST",
        body: { title, category, description },
        actingAs: me.id,
      });
      setCreated(request);
      setTitle("");
      setDescription("");
      onCreated();
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <section aria-labelledby="form-heading" className="card">
      <h2 id="form-heading">Raise a request</h2>
      <p className="muted small">Raised as {me ? me.name : "…"}. Anyone can raise a request.</p>
      <form onSubmit={submit}>
        <label>
          Title
          <input value={title} onChange={(e) => setTitle(e.target.value)} required minLength={3} maxLength={200} />
        </label>
        <label>
          Category
          <select value={category} onChange={(e) => setCategory(e.target.value)}>
            {CATEGORIES.map((c) => (
              <option key={c.value} value={c.value}>
                {c.label}
              </option>
            ))}
          </select>
        </label>
        <label>
          Details
          <textarea value={description} onChange={(e) => setDescription(e.target.value)} rows={4} maxLength={4000} />
        </label>
        <button type="submit" disabled={busy || !me}>
          {busy ? "Submitting…" : "Submit request"}
        </button>
      </form>
      {error && (
        <p className="banner error" role="alert">
          {error}
        </p>
      )}
      {created && !error && (
        <p className="banner ok" role="status">
          Request #{created.id} created. <Link href={`/requests/${created.id}`}>Open it</Link>
        </p>
      )}
    </section>
  );
}
