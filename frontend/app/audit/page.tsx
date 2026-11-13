"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import { api, type AuditEvent } from "@/lib/api";
import { ACTION_WORDS, formatTime, STATUS_LABEL } from "@/lib/labels";
import { useActingAs } from "../acting-as";

export default function AuditPage() {
  const { nameOf } = useActingAs();
  const [events, setEvents] = useState<AuditEvent[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(() => {
    api<AuditEvent[]>("/api/audit?limit=200").then(
      (rows) => {
        setEvents(rows);
        setError(null);
      },
      (e: Error) => setError(e.message),
    );
  }, []);

  useEffect(load, [load]);

  return (
    <section aria-labelledby="audit-heading">
      <div className="heading-row">
        <h1 id="audit-heading">Audit log</h1>
        <button className="secondary" onClick={load}>
          Refresh
        </button>
      </div>
      <p className="muted small">
        Every change to every request, newest first. The database refuses to edit or delete these rows.
      </p>
      {error && (
        <p className="banner error" role="alert">
          {error}
        </p>
      )}
      {events?.length === 0 && <p className="muted">Nothing has happened yet.</p>}
      {events && events.length > 0 && (
        <div className="table-wrap">
          <table>
            <thead>
              <tr>
                <th>When</th>
                <th>Who</th>
                <th>What</th>
                <th>Request</th>
                <th>Note</th>
              </tr>
            </thead>
            <tbody>
              {events.map((e) => (
                <tr key={e.id}>
                  <td className="small">{formatTime(e.at)}</td>
                  <td>{nameOf(e.actor)}</td>
                  <td>
                    {ACTION_WORDS[e.action] ?? e.action}
                    {e.from_status && (
                      <div className="muted small">
                        {STATUS_LABEL[e.from_status]} → {STATUS_LABEL[e.to_status]}
                      </div>
                    )}
                  </td>
                  <td>
                    <Link href={`/requests/${e.request_id}`}>
                      #{e.request_id} {e.request_title}
                    </Link>
                  </td>
                  <td className="small">{e.note}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </section>
  );
}
