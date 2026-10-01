export class ApiError extends Error {
  constructor(
    message: string,
    public status: number,
  ) {
    super(message);
  }
}
let csrf = "";
export function setCsrf(value: string) {
  csrf = value;
}
export async function api<T>(
  path: string,
  method = "GET",
  body?: unknown,
): Promise<T> {
  const res = await fetch(`/api/v1${path}`, {
    method,
    credentials: "same-origin",
    cache: "no-store",
    headers: {
      "Content-Type": "application/json",
      ...(method !== "GET" ? { "X-CSRF-Token": csrf } : {}),
    },
    ...(body !== undefined ? { body: JSON.stringify(body) } : {}),
  });
  const data = await res.json();
  if (!res.ok)
    throw new ApiError(
      data.error?.message ||
        (Array.isArray(data.detail)
          ? data.detail.map((e: { msg: string }) => e.msg).join("; ")
          : data.detail) ||
        "Request failed",
      res.status,
    );
  return data;
}
export type User = {
  id: string;
  name: string;
  email: string;
  role: string;
  department: string;
  manager_id: string | null;
  manager_name?: string;
  active: boolean;
};
export type Project = { id: string; name: string; description: string };
export type Entry = {
  id: string;
  project_id: string;
  project_name: string;
  work_date: string;
  hours: number;
  description: string;
};
export type Sheet = {
  id: string | null;
  status: string;
  week_start: string;
  total_hours: number;
  entries: Entry[];
  rejection_reason?: string;
  reviewer_name?: string;
};
export type Item = {
  id: string;
  title?: string;
  description?: string;
  status?: string;
  created_at: string;
  user_name?: string;
  user_id?: string;
  assignee_id?: string;
  assignee_name?: string;
  creator_name?: string;
  project_id?: string;
  project_name?: string;
  due_date?: string;
  priority?: string;
  start_date?: string;
  end_date?: string;
  reason?: string;
  rejection_reason?: string;
  reviewer_name?: string;
  kind?: string;
  week_start?: string;
  entries?: Entry[];
  total_hours?: number;
  name?: string;
  email?: string;
  role?: string;
  department?: string;
  manager_name?: string;
  actor_name?: string;
  actor_id?: string;
  source?: string;
  action?: string;
  resource_type?: string;
  resource_id?: string;
  outcome?: string;
  details?: { error?: string };
  request_id?: string;
};
export type Page<T> = {
  items: T[];
  total: number;
  limit: number;
  offset: number;
};
export function today() {
  return new Intl.DateTimeFormat("en-CA", {
    timeZone: "America/Chicago",
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
  }).format(new Date());
}
export function weekOf(date: string) {
  const d = new Date(`${date}T12:00:00Z`);
  d.setUTCDate(d.getUTCDate() - ((d.getUTCDay() + 6) % 7));
  return d.toISOString().slice(0, 10);
}
export function shiftDate(date: string, days: number) {
  const d = new Date(`${date}T12:00:00Z`);
  d.setUTCDate(d.getUTCDate() + days);
  return d.toISOString().slice(0, 10);
}
export function dateLabel(date?: string) {
  return date
    ? new Date(`${date}T12:00:00Z`).toLocaleDateString("en-US", {
        month: "short",
        day: "numeric",
        year: "numeric",
        timeZone: "UTC",
      })
    : "—";
}
export function timestamp(value: string) {
  return new Date(value).toLocaleString("en-US", {
    timeZone: "America/Chicago",
    month: "short",
    day: "numeric",
    hour: "numeric",
    minute: "2-digit",
  });
}
