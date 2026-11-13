import type { Role, Status } from "./api";

export const STATUS_LABEL: Record<Status, string> = {
  new: "New",
  triaged: "Triaged",
  approved: "Approved",
  rejected: "Rejected",
  done: "Done",
};

export const ROLE_LABEL: Record<Role, string> = {
  requester: "Requester",
  service_desk: "Service desk",
  approver: "Approver",
};

export const PRIORITY_LABEL: Record<string, string> = { low: "Low", medium: "Medium", high: "High" };

export const CATEGORIES = [
  { value: "access", label: "Access to a system" },
  { value: "hardware", label: "Hardware" },
  { value: "software", label: "Software or licence" },
  { value: "other", label: "Something else" },
];

export function categoryLabel(value: string): string {
  return CATEGORIES.find((c) => c.value === value)?.label ?? value;
}

const TIME = new Intl.DateTimeFormat("en-GB", { dateStyle: "medium", timeStyle: "short" });

export function formatTime(iso: string): string {
  return TIME.format(new Date(iso));
}

// How the audit log reads each event: "Meera approved it".
export const ACTION_WORDS: Record<string, string> = {
  created: "raised it",
  triaged: "triaged it",
  approved: "approved it",
  rejected: "rejected it",
  completed: "marked it done",
};
