"use client";
import { useState } from "react";
import {
  Plus,
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
import { Badge, Empty, Loading, Modal } from "./ui";
import type { Mutate } from "../lib/types";

type Props = {
  sheet: Sheet | null;
  projects: Project[];
  week: string;
  setWeek: (week: string) => void;
  loading: boolean;
  busy: boolean;
  openEntry: (entry: Entry | null, projectId: string, workDate: string) => void;
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
  const [selectedCell, setSelectedCell] = useState<{
    projectId: string;
    workDate: string;
  } | null>(null);
  const dates = Array.from({ length: 7 }, (_, index) => shiftDate(week, index));
  const entries = sheet?.entries || [];
  const editable = !!sheet && ["DRAFT", "REJECTED"].includes(sheet.status);
  // Keep historical hours visible if a project is no longer currently assigned.
  const rows = [...projects];
  for (const entry of entries) {
    if (!rows.some((project) => project.id === entry.project_id))
      rows.push({
        id: entry.project_id,
        name: entry.project_name,
        description: "Historical project",
      });
  }
  const matching = (projectId: string, workDate: string) =>
    entries.filter(
      (entry) => entry.project_id === projectId && entry.work_date === workDate,
    );
  const total = (items: Entry[]) =>
    items.reduce(
      (sum, entry) => sum + Math.round(Number(entry.hours) * 100),
      0,
    ) / 100;
  const shortDate = (value: string) =>
    `${value.slice(5, 7)}/${value.slice(8, 10)}`;
  const selectedProject = rows.find(
    (project) => project.id === selectedCell?.projectId,
  );
  const cellEntries = selectedCell
    ? matching(selectedCell.projectId, selectedCell.workDate)
    : [];
  const assigned = (projectId: string) =>
    projects.some((project) => project.id === projectId);
  function editCell(entry: Entry | null, projectId: string, workDate: string) {
    setSelectedCell(null);
    openEntry(entry, projectId, workDate);
  }
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
            <h2>Weekly timesheet</h2>
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
        ) : !rows.length ? (
          <Empty
            title="No assigned projects"
            text="Assigned projects will appear here for time logging."
          />
        ) : (
          <div className="table-scroll">
            <table className="timesheet-grid" aria-label="Weekly project hours">
              <thead>
                <tr>
                  <th scope="col">Project</th>
                  {dates.map((date, index) => (
                    <th scope="col" key={date}>
                      <span>{shortDate(date)}</span>
                      <small>
                        {
                          ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"][
                            index
                          ]
                        }
                      </small>
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {rows.map((project) => (
                  <tr key={project.id}>
                    <th scope="row">
                      <strong>{project.name}</strong>
                      {!assigned(project.id) && (
                        <small>Historical project</small>
                      )}
                    </th>
                    {dates.map((date) => {
                      const hours = total(matching(project.id, date));
                      return (
                        <td key={date}>
                          <button
                            className={`hours-cell ${hours ? "has-hours" : ""}`}
                            aria-label={`${project.name} on ${shortDate(date)}: ${hours} hours`}
                            disabled={
                              busy ||
                              (!hours && (!editable || !assigned(project.id)))
                            }
                            onClick={() => {
                              if (!hours && editable && assigned(project.id))
                                editCell(null, project.id, date);
                              else
                                setSelectedCell({
                                  projectId: project.id,
                                  workDate: date,
                                });
                            }}
                          >
                            {hours}
                          </button>
                        </td>
                      );
                    })}
                  </tr>
                ))}
              </tbody>
              <tfoot>
                <tr>
                  <th scope="row">Daily total</th>
                  {dates.map((date) => (
                    <td key={date}>
                      {total(
                        entries.filter((entry) => entry.work_date === date),
                      )}
                    </td>
                  ))}
                </tr>
              </tfoot>
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
      {selectedCell && selectedProject && (
        <Modal
          title={`${selectedProject.name} · ${dateLabel(selectedCell.workDate)}`}
          close={() => {
            if (!busy) setSelectedCell(null);
          }}
        >
          <div className="details">
            <p>{total(cellEntries)} hours logged for this day.</p>
            <div className="cell-entry-list">
              {cellEntries.map((entry) => (
                <div key={entry.id} className="cell-entry">
                  <div>
                    <strong>{entry.hours} hours</strong>
                    <p>{entry.description}</p>
                  </div>
                  {editable && assigned(selectedProject.id) && (
                    <div className="row-actions">
                      <button
                        className="icon-button"
                        aria-label={`Edit ${entry.description || `${entry.hours}-hour entry`}`}
                        disabled={busy}
                        onClick={() =>
                          editCell(entry, entry.project_id, entry.work_date)
                        }
                      >
                        <Pencil size={16} />
                      </button>
                      <button
                        className="icon-button danger"
                        aria-label={`Delete ${entry.description || `${entry.hours}-hour entry`}`}
                        disabled={busy}
                        onClick={() =>
                          void mutate(
                            `/time-entries/${entry.id}`,
                            "DELETE",
                            undefined,
                            "Entry deleted",
                          )
                        }
                      >
                        <Trash2 size={16} />
                      </button>
                    </div>
                  )}
                </div>
              ))}
            </div>
            {editable && assigned(selectedProject.id) && (
              <button
                className="primary"
                disabled={busy}
                onClick={() =>
                  editCell(null, selectedProject.id, selectedCell.workDate)
                }
              >
                <Plus size={16} />
                Add entry
              </button>
            )}
            {!editable && (
              <p className="subtle">This timesheet is locked for review.</p>
            )}
          </div>
        </Modal>
      )}
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
