// Types and a small fetch helper for the FastAPI backend.
// Paths start with /api, which Next.js passes on to the backend (see next.config.ts).

export type Role = "requester" | "service_desk" | "approver";
export type Status = "new" | "triaged" | "approved" | "rejected" | "done";
export type Action = "triage" | "approve" | "reject" | "complete";

export type Person = { id: string; name: string; role: Role };

export type ServiceRequest = {
  id: number;
  title: string;
  description: string;
  category: string;
  requested_by: string;
  status: Status;
  priority: string | null;
  decided_by: string | null;
  decided_at: string | null;
  created_at: string;
  updated_at: string;
  allowed_actions: Action[];
};

export type AuditEvent = {
  id: number;
  request_id: number;
  request_title: string;
  action: string;
  actor: string;
  from_status: Status | null;
  to_status: Status;
  note: string;
  at: string;
};

export class ApiError extends Error {
  constructor(message: string, public status: number) {
    super(message);
  }
}

type Options = { method?: "GET" | "POST"; body?: unknown; actingAs?: string };

export async function api<T>(path: string, { method = "GET", body, actingAs }: Options = {}): Promise<T> {
  const headers: Record<string, string> = {};
  if (body !== undefined) headers["Content-Type"] = "application/json";
  if (actingAs) headers["X-Acting-As"] = actingAs;

  let response: Response;
  try {
    response = await fetch(path, {
      method,
      headers,
      body: body === undefined ? undefined : JSON.stringify(body),
      cache: "no-store",
    });
  } catch {
    throw new ApiError("Can't reach the API. Is the backend running?", 0);
  }
  const data = await response.json().catch(() => null);
  if (!response.ok) {
    throw new ApiError(errorMessage(data) ?? `Request failed with status ${response.status}`, response.status);
  }
  return data as T;
}

// FastAPI sends {"detail": "text"} for our own errors and
// {"detail": [{"loc": [...], "msg": "..."}]} when the input doesn't validate.
function errorMessage(data: unknown): string | null {
  if (!data || typeof data !== "object" || !("detail" in data)) return null;
  const detail = (data as { detail: unknown }).detail;
  if (typeof detail === "string") return detail;
  if (Array.isArray(detail)) {
    return detail
      .map((d: { loc?: unknown[]; msg?: string }) => `${String(d.loc?.at(-1) ?? "input")}: ${d.msg ?? "invalid"}`)
      .join("; ");
  }
  return null;
}
