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
