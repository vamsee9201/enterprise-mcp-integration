"use client";
import {
  ArrowRight,
  ChevronLeft,
  ChevronRight,
  Clock3,
  Pencil,
  ShieldCheck,
  Trash2,
} from "lucide-react";
import {
  dateLabel,
  shiftDate,
  weekOf,
  type Project,
  type Sheet,
  type Entry,
} from "../lib/api";
import { Badge, Empty, Loading } from "./ui";
import type { Mutate } from "../lib/types";

type Props = {
  sheet: Sheet | null;
  projects: Project[];
  week: string;
  setWeek: (week: string) => void;
  loading: boolean;
  busy: boolean;
  openEntry: (entry: Entry) => void;
  mutate: Mutate;
};
export function TimesheetView({
  sheet,
  projects,
  week,
  setWeek,
  loading,
  busy,
  openEntry,
  mutate,
}: Props) {
  return (
    <>
      <div className="summary-grid">
        <div className="summary-card">
          <span>HOURS THIS WEEK</span>
          <strong>
            {sheet?.total_hours || 0}
            <small> hrs</small>
          </strong>
          <p>
            Across {new Set(sheet?.entries.map((e) => e.project_id)).size || 0}{" "}
            projects
          </p>
        </div>
        <div className="summary-card">
          <span>TIMESHEET STATUS</span>
          <div className="summary-value">
            <Badge value={sheet?.status || "DRAFT"} />
          </div>
          <p>
            {sheet?.status === "APPROVED"
              ? `Reviewed by ${sheet.reviewer_name}`
              : sheet?.status === "SUBMITTED"
                ? "Waiting for manager review"
                : "Ready when your week is complete"}
          </p>
        </div>
        <div className="summary-card">
          <span>YOUR PROJECTS</span>
          <strong>
            {projects.length}
            <small> active</small>
          </strong>
          <p>Assigned and available for time logging</p>
        </div>
      </div>
      <section className="panel">
        <div className="panel-head">
          <div>
            <h2>Weekly entries</h2>
            <span className="subtle">
              {dateLabel(week)} – {dateLabel(shiftDate(week, 6))}
            </span>
          </div>
          <div className="week-control">
            <button
              className="icon-button"
              aria-label="Previous week"
              onClick={() => setWeek(shiftDate(week, -7))}
            >
              <ChevronLeft size={18} />
            </button>
            <input
              aria-label="Timesheet week"
              type="date"
              value={week}
              onChange={(e) => {
                if (e.target.value) setWeek(weekOf(e.target.value));
              }}
            />
            <button
              className="icon-button"
              aria-label="Next week"
              onClick={() => setWeek(shiftDate(week, 7))}
            >
              <ChevronRight size={18} />
            </button>
          </div>
        </div>
        {sheet?.rejection_reason && (
          <div className="inline-note">
            Manager feedback: {sheet.rejection_reason}
          </div>
        )}
        {loading ? (
          <Loading />
        ) : !sheet?.entries.length ? (
          <Empty
            title="Your week starts here"
            text="Log hours against an assigned project to build your timesheet."
          />
        ) : (
          <div className="table-scroll">
            <table>
              <thead>
                <tr>
                  <th>Date</th>
                  <th>Project</th>
                  <th>Work description</th>
                  <th>Hours</th>
                  <th>
                    <span className="sr-only">Actions</span>
                  </th>
                </tr>
              </thead>
              <tbody>
                {sheet.entries.map((e) => (
                  <tr key={e.id}>
                    <td>{dateLabel(e.work_date)}</td>
                    <td>
                      <strong>{e.project_name}</strong>
                    </td>
                    <td>{e.description}</td>
                    <td>
                      <strong>{e.hours}</strong>
                    </td>
                    <td className="row-actions">
                      {["DRAFT", "REJECTED"].includes(sheet.status) && (
                        <>
                          <button
                            className="icon-button"
                            aria-label={`Edit ${e.description}`}
                            onClick={() => {
                              openEntry(e);
                            }}
                          >
                            <Pencil size={15} />
                          </button>
                          <button
                            className="icon-button danger"
                            aria-label={`Delete ${e.description}`}
                            disabled={busy}
                            onClick={() =>
                              void mutate(
                                `/time-entries/${e.id}`,
                                "DELETE",
                                undefined,
                                "Entry deleted",
                              )
                            }
                          >
                            <Trash2 size={15} />
                          </button>
                        </>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
        <div className="panel-footer">
          <span>
            <Clock3 size={15} /> Week starts Monday · America/Chicago
          </span>
          <button
            className="primary"
            disabled={
              busy ||
              !sheet?.entries.length ||
              !["DRAFT", "REJECTED"].includes(sheet?.status || "")
            }
            onClick={() =>
              void mutate(
                `/timesheets/submit?week=${week}`,
                "POST",
                undefined,
                "Timesheet submitted",
              )
            }
          >
            Submit week <ArrowRight size={16} />
          </button>
        </div>
      </section>
      <div className="helper-note">
        <ShieldCheck size={17} />
        <p>
          Submitted timesheets are locked for review. Your manager can approve
          or return them with feedback.
        </p>
      </div>
    </>
  );
}
