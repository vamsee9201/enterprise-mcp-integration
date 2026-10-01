"use client";
import type { FormEvent } from "react";
import { Check, Pencil } from "lucide-react";
import {
  dateLabel,
  shiftDate,
  weekOf,
  today,
  timestamp,
  type User,
  type Project,
  type Entry,
  type Item,
} from "../lib/api";
import { Badge, Modal, Field } from "./ui";
import type { View, ModalKind, Mutate } from "../lib/types";

const ticketNext: Record<string, string[]> = {
  OPEN: ["IN_PROGRESS"],
  IN_PROGRESS: ["OPEN", "RESOLVED"],
  RESOLVED: ["CLOSED", "OPEN"],
  CLOSED: ["OPEN"],
};
type Props = {
  modal: ModalKind;
  view: View;
  editing: Entry | null;
  entryDefaults: { project_id: string; work_date: string } | null;
  selected: Item | null;
  formError: string;
  busy: boolean;
  manager: boolean;
  projects: Project[];
  user: User;
  people: User[];
  week: string;
  assignees: () => User[];
  submitEntry: (event: FormEvent<HTMLFormElement>) => void;
  submitNew: (event: FormEvent<HTMLFormElement>) => void;
  values: (
    event: FormEvent<HTMLFormElement>,
  ) => Record<string, FormDataEntryValue>;
  mutate: Mutate;
  setModal: (modal: ModalKind | null) => void;
  setFormError: (error: string) => void;
};
export function WorkflowDialog({
  modal,
  view,
  editing,
  entryDefaults,
  selected,
  formError,
  busy,
  manager,
  projects,
  user,
  people,
  week,
  assignees,
  submitEntry,
  submitNew,
  values,
  mutate,
  setModal,
  setFormError,
}: Props) {
  return (
    <Modal
      title={
        modal === "entry"
          ? editing
            ? "Edit time entry"
            : "Log time"
          : modal === "create"
            ? selected
              ? "Edit task"
              : view === "tasks"
                ? "New task"
                : view === "leave"
                  ? "Request leave"
                  : "New support ticket"
            : view === "review"
              ? "Review request"
              : "Record details"
      }
      close={() => {
        if (!busy) setModal(null);
      }}
    >
      {formError && (
        <div className="alert" role="alert">
          {formError}
        </div>
      )}
      {modal === "entry" && (
        <form onSubmit={submitEntry} className="form">
          <Field label="Project">
            <select
              name="project_id"
              defaultValue={
                editing?.project_id ||
                entryDefaults?.project_id ||
                projects[0]?.id
              }
              required
            >
              {projects.map((p) => (
                <option key={p.id} value={p.id}>
                  {p.name}
                </option>
              ))}
            </select>
          </Field>
          <div className="form-grid">
            <Field label="Work date">
              <input
                type="date"
                name="work_date"
                min={week}
                max={shiftDate(week, 6)}
                defaultValue={
                  editing?.work_date ||
                  entryDefaults?.work_date ||
                  (weekOf(today()) === week ? today() : week)
                }
                required
              />
            </Field>
            <Field label="Hours">
              <input
                name="hours"
                type="number"
                min="0.01"
                max="24"
                step="0.01"
                defaultValue={editing?.hours || 7}
                required
              />
            </Field>
          </div>
          <Field label="Work description (optional)">
            <textarea
              name="description"
              maxLength={1000}
              defaultValue={editing?.description}
              placeholder="What did you work on?"
            />
          </Field>
          <div className="form-footer">
            <button
              type="button"
              className="secondary"
              disabled={busy}
              onClick={() => setModal(null)}
            >
              Cancel
            </button>
            <button className="primary" disabled={busy || !projects.length}>
              {busy ? "Saving…" : "Save entry"}
            </button>
          </div>
        </form>
      )}
      {modal === "create" && (
        <form onSubmit={submitNew} className="form">
          {view !== "leave" && (
            <>
              <Field label="Title">
                <input
                  name="title"
                  maxLength={200}
                  defaultValue={selected?.title}
                  required
                />
              </Field>
              <Field label="Description">
                <textarea
                  name="description"
                  maxLength={2000}
                  defaultValue={selected?.description}
                />
              </Field>
            </>
          )}
          {view === "tasks" && (
            <>
              {!selected && (
                <Field label="Assignee">
                  <select name="assignee_id" defaultValue={user.id} required>
                    {assignees().map((p) => (
                      <option key={p.id} value={p.id}>
                        {p.name}
                      </option>
                    ))}
                  </select>
                </Field>
              )}
              <div className="form-grid">
                <Field label="Project (optional)">
                  <select
                    name="project_id"
                    defaultValue={selected?.project_id || ""}
                  >
                    <option value="">No project</option>
                    {projects.map((p) => (
                      <option key={p.id} value={p.id}>
                        {p.name}
                      </option>
                    ))}
                  </select>
                </Field>
                <Field label="Due date (optional)">
                  <input
                    type="date"
                    name="due_date"
                    defaultValue={selected?.due_date || ""}
                  />
                </Field>
              </div>
            </>
          )}
          {view === "tickets" && (
            <Field label="Priority">
              <select name="priority" defaultValue="MEDIUM">
                {["LOW", "MEDIUM", "HIGH"].map((p) => (
                  <option key={p}>{p}</option>
                ))}
              </select>
            </Field>
          )}
          {view === "leave" && (
            <>
              <div className="form-grid">
                <Field label="Start date">
                  <input
                    type="date"
                    name="start_date"
                    defaultValue={today()}
                    required
                  />
                </Field>
                <Field label="End date">
                  <input
                    type="date"
                    name="end_date"
                    defaultValue={today()}
                    required
                  />
                </Field>
              </div>
              <Field label="Reason (optional)">
                <textarea
                  name="reason"
                  maxLength={1000}
                  placeholder="Add any context for your manager"
                />
              </Field>
              <p className="subtle">
                Dates include both the first and last day. Pending and approved
                requests cannot overlap.
              </p>
            </>
          )}
          <div className="form-footer">
            <button
              type="button"
              className="secondary"
              disabled={busy}
              onClick={() => setModal(null)}
            >
              Cancel
            </button>
            <button className="primary" disabled={busy}>
              {busy ? "Saving…" : selected ? "Save changes" : "Create"}
            </button>
          </div>
        </form>
      )}
      {modal === "details" && selected && (
        <div className="details">
          <div className="detail-title">
            <h3>{selected.title || selected.user_name || selected.action}</h3>
            <Badge value={selected.status || selected.outcome} />
          </div>
          {(selected.description || selected.reason) && (
            <p>{selected.description || selected.reason}</p>
          )}
          {selected.week_start && (
            <>
              <p>
                Week of {dateLabel(selected.week_start)} ·{" "}
                <strong>{selected.total_hours} hours</strong>
              </p>
              <div className="review-entries">
                {selected.entries?.map((e) => (
                  <div key={e.id}>
                    <strong>{e.project_name}</strong>
                    <span>
                      {dateLabel(e.work_date)} · {e.hours} hrs
                    </span>
                    <p>{e.description}</p>
                  </div>
                ))}
              </div>
            </>
          )}
          {selected.start_date && (
            <p>
              {dateLabel(selected.start_date)} – {dateLabel(selected.end_date)}
            </p>
          )}
          {selected.reviewer_name && (
            <p className="subtle">Reviewed by {selected.reviewer_name}</p>
          )}
          {selected.rejection_reason && (
            <div className="inline-note">
              Feedback: {selected.rejection_reason}
            </div>
          )}
          {view === "tasks" && (
            <>
              <div className="detail-meta">
                <span>
                  Assigned to <strong>{selected.assignee_name}</strong>
                </span>
                <span>
                  Due <strong>{dateLabel(selected.due_date)}</strong>
                </span>
              </div>
              <Field label="Update task status">
                <select
                  value={selected.status}
                  disabled={busy}
                  onChange={(e) =>
                    void mutate(`/tasks/${selected.id}/status`, "PATCH", {
                      status: e.target.value,
                    })
                  }
                >
                  {["TODO", "IN_PROGRESS", "DONE"].map((s) => (
                    <option key={s}>{s}</option>
                  ))}
                </select>
              </Field>
              {manager && (
                <>
                  <Field label="Assign task">
                    <select
                      value={selected.assignee_id}
                      disabled={busy}
                      onChange={(e) =>
                        void mutate(`/tasks/${selected.id}/assignee`, "PATCH", {
                          assignee_id: e.target.value,
                        })
                      }
                    >
                      {assignees().map((p) => (
                        <option key={p.id} value={p.id}>
                          {p.name}
                        </option>
                      ))}
                    </select>
                  </Field>
                  <button
                    className="secondary"
                    onClick={() => {
                      setModal("create");
                      setFormError("");
                    }}
                  >
                    <Pencil size={15} />
                    Edit details
                  </button>
                </>
              )}
            </>
          )}
          {view === "tickets" && (
            <>
              <p className="subtle">
                Created by {selected.creator_name} · Assigned to{" "}
                {selected.assignee_name || "Nobody yet"}
              </p>
              <Field label="Move ticket to">
                <select
                  defaultValue=""
                  disabled={busy}
                  onChange={(e) => {
                    if (e.target.value)
                      void mutate(`/tickets/${selected.id}/status`, "PATCH", {
                        status: e.target.value,
                      });
                  }}
                >
                  <option value="">Choose next status</option>
                  {ticketNext[selected.status || "OPEN"].map((s) => (
                    <option key={s}>{s}</option>
                  ))}
                </select>
              </Field>
              {manager && (
                <>
                  <Field label="Priority">
                    <select
                      value={selected.priority}
                      disabled={busy}
                      onChange={(e) =>
                        void mutate(
                          `/tickets/${selected.id}/priority`,
                          "PATCH",
                          { priority: e.target.value },
                        )
                      }
                    >
                      {["LOW", "MEDIUM", "HIGH"].map((s) => (
                        <option key={s}>{s}</option>
                      ))}
                    </select>
                  </Field>
                  <Field label="Assign ticket">
                    <select
                      value={selected.assignee_id || ""}
                      disabled={busy}
                      onChange={(e) => {
                        if (e.target.value)
                          void mutate(
                            `/tickets/${selected.id}/assignee`,
                            "PATCH",
                            { assignee_id: e.target.value },
                          );
                      }}
                    >
                      <option value="">Unassigned</option>
                      {people.map((p) => (
                        <option key={p.id} value={p.id}>
                          {p.name}
                        </option>
                      ))}
                    </select>
                  </Field>
                </>
              )}
            </>
          )}
          {view === "review" && (
            <form
              onSubmit={(e) => {
                const b = values(e);
                void mutate(
                  `/${selected.kind === "timesheet" ? "timesheets" : "leave-requests"}/${selected.id}/reject`,
                  "POST",
                  b,
                  "Request rejected",
                );
              }}
              className="review-form"
            >
              <Field label="Reason for rejection">
                <textarea
                  name="reason"
                  placeholder="Required when returning a request"
                  maxLength={1000}
                  required
                />
              </Field>
              <div className="form-footer">
                <button className="secondary danger" disabled={busy}>
                  Reject request
                </button>
                <button
                  type="button"
                  className="primary"
                  disabled={busy}
                  onClick={() =>
                    void mutate(
                      `/${selected.kind === "timesheet" ? "timesheets" : "leave-requests"}/${selected.id}/approve`,
                      "POST",
                      undefined,
                      "Request approved",
                    )
                  }
                >
                  <Check size={16} />
                  Approve
                </button>
              </div>
            </form>
          )}
          {view === "activity" && (
            <dl className="audit-details">
              <dt>Source</dt>
              <dd>{selected.source}</dd>
              <dt>Resource</dt>
              <dd>{selected.resource_type}</dd>
              <dt>Resource ID</dt>
              <dd>
                <code>{selected.resource_id || "—"}</code>
              </dd>
              <dt>Request ID</dt>
              <dd>
                <code>{selected.request_id}</code>
              </dd>
              <dt>Time</dt>
              <dd>{timestamp(selected.created_at)}</dd>
              {selected.details?.error && (
                <>
                  <dt>Reason</dt>
                  <dd>{selected.details.error}</dd>
                </>
              )}
            </dl>
          )}
        </div>
      )}
    </Modal>
  );
}
