"use client";
import { ChevronLeft, ChevronRight, Search } from "lucide-react";
import {
  dateLabel,
  timestamp,
  type User,
  type Item,
  type Page,
} from "../lib/api";
import { Badge, Empty, Loading } from "./ui";
import type { View } from "../lib/types";

type Props = {
  view: View;
  manager: boolean;
  loading: boolean;
  page: Page<Item>;
  filters: Record<string, string>;
  offset: number;
  setOffset: (offset: number) => void;
  filter: (key: string, value: string) => void;
  people: User[];
  assignees: () => User[];
  details: (item: Item) => Promise<void>;
};
export function RecordsView({
  view,
  manager,
  loading,
  page,
  filters,
  offset,
  setOffset,
  filter,
  people,
  assignees,
  details,
}: Props) {
  return view === "review" && !manager ? (
    <section className="panel">
      <Empty
        title="Manager access required"
        text="Your manager reviews submitted timesheets and pending leave here."
      />
    </section>
  ) : (
    <section className="panel">
      <div className="filters">
        {["tasks", "tickets", "directory"].includes(view) && (
          <div className="search">
            <Search size={17} />
            <input
              aria-label="Search records"
              placeholder={
                view === "directory"
                  ? "Search people, teams, or managers…"
                  : `Search ${view}…`
              }
              value={filters.query || ""}
              onChange={(e) => filter("query", e.target.value)}
            />
          </div>
        )}
        {["tasks", "leave", "tickets"].includes(view) && (
          <select
            aria-label="Filter status"
            value={filters.status || ""}
            onChange={(e) => filter("status", e.target.value)}
          >
            <option value="">All statuses</option>
            {(view === "tasks"
              ? ["TODO", "IN_PROGRESS", "DONE"]
              : view === "leave"
                ? ["PENDING", "APPROVED", "REJECTED"]
                : ["OPEN", "IN_PROGRESS", "RESOLVED", "CLOSED"]
            ).map((s) => (
              <option key={s}>{s}</option>
            ))}
          </select>
        )}
        {view === "tickets" && (
          <select
            aria-label="Filter priority"
            value={filters.priority || ""}
            onChange={(e) => filter("priority", e.target.value)}
          >
            <option value="">All priorities</option>
            {["LOW", "MEDIUM", "HIGH"].map((s) => (
              <option key={s}>{s}</option>
            ))}
          </select>
        )}
        {["tasks", "tickets"].includes(view) && manager && (
          <select
            aria-label="Filter assignee"
            value={filters.assignee_id || ""}
            onChange={(e) => filter("assignee_id", e.target.value)}
          >
            <option value="">All assignees</option>
            {(view === "tasks" ? assignees() : people).map((p) => (
              <option key={p.id} value={p.id}>
                {p.name}
              </option>
            ))}
          </select>
        )}
        {view === "directory" && (
          <select
            aria-label="Filter department"
            value={filters.department || ""}
            onChange={(e) => filter("department", e.target.value)}
          >
            <option value="">All departments</option>
            {Array.from(new Set(people.map((p) => p.department))).map((d) => (
              <option key={d}>{d}</option>
            ))}
          </select>
        )}
        {view === "review" && (
          <>
            <h2>Pending requests</h2>
            <select
              aria-label="Filter request type"
              value={filters.kind || ""}
              onChange={(e) => filter("kind", e.target.value)}
            >
              <option value="">All request types</option>
              <option value="timesheet">Timesheets</option>
              <option value="leave">Leave requests</option>
            </select>
          </>
        )}
        {view === "activity" && (
          <>
            <select
              aria-label="Filter source"
              value={filters.source || ""}
              onChange={(e) => filter("source", e.target.value)}
            >
              <option value="">All sources</option>
              <option>UI</option>
              <option>MCP</option>
            </select>
            <select
              aria-label="Filter outcome"
              value={filters.outcome || ""}
              onChange={(e) => filter("outcome", e.target.value)}
            >
              <option value="">All outcomes</option>
              {["SUCCESS", "DENIED", "FAILED"].map((s) => (
                <option key={s}>{s}</option>
              ))}
            </select>
            <select
              aria-label="Filter actor"
              value={filters.actor_id || ""}
              onChange={(e) => filter("actor_id", e.target.value)}
            >
              <option value="">All visible actors</option>
              {assignees().map((p) => (
                <option key={p.id} value={p.id}>
                  {p.name}
                </option>
              ))}
            </select>
            <select
              aria-label="Filter resource"
              value={filters.resource_type || ""}
              onChange={(e) => filter("resource_type", e.target.value)}
            >
              <option value="">All resources</option>
              {[
                "time_entry",
                "timesheet",
                "task",
                "leave_request",
                "ticket",
              ].map((s) => (
                <option key={s}>{s}</option>
              ))}
            </select>
            <input
              aria-label="Filter action"
              placeholder="Action name"
              value={filters.action || ""}
              onChange={(e) => filter("action", e.target.value)}
            />
            <input
              aria-label="Activity start date"
              type="date"
              value={filters.start_date || ""}
              onChange={(e) => filter("start_date", e.target.value)}
            />
            <input
              aria-label="Activity end date"
              type="date"
              value={filters.end_date || ""}
              onChange={(e) => filter("end_date", e.target.value)}
            />
          </>
        )}
      </div>
      {loading ? (
        <Loading />
      ) : !page.items.length ? (
        <Empty
          title={
            view === "review" ? "You’re all caught up" : "No matching records"
          }
          text={
            view === "review"
              ? "Submitted team requests will appear here for review."
              : "Try another filter or create a new record."
          }
        />
      ) : (
        <div className="table-scroll">
          <table>
            <thead>
              <tr>
                {(view === "tasks"
                  ? ["Task", "Assignee", "Project", "Due date", "Status"]
                  : view === "tickets"
                    ? [
                        "Ticket",
                        "Created by",
                        "Assigned to",
                        "Priority",
                        "Status",
                      ]
                    : view === "leave"
                      ? ["Employee", "Dates", "Reason", "Status"]
                      : view === "directory"
                        ? ["Employee", "Department", "Manager", "Role"]
                        : view === "review"
                          ? ["Employee", "Type", "Period", "Details", "Status"]
                          : [
                              "Time (Chicago)",
                              "Actor",
                              "Action",
                              "Resource",
                              "Source",
                              "Outcome",
                            ]
                ).map((h) => (
                  <th key={h}>{h}</th>
                ))}
                <th>
                  <span className="sr-only">Details</span>
                </th>
              </tr>
            </thead>
            <tbody>
              {page.items.map((item) => (
                <tr key={item.id}>
                  {view === "tasks" && (
                    <>
                      <td>
                        <strong>{item.title}</strong>
                        <small className="cell-note">{item.description}</small>
                      </td>
                      <td>{item.assignee_name}</td>
                      <td>{item.project_name || "—"}</td>
                      <td>{dateLabel(item.due_date)}</td>
                      <td>
                        <Badge value={item.status} />
                      </td>
                    </>
                  )}
                  {view === "tickets" && (
                    <>
                      <td>
                        <strong>{item.title}</strong>
                        <small className="cell-note">{item.description}</small>
                      </td>
                      <td>{item.creator_name}</td>
                      <td>{item.assignee_name || "Unassigned"}</td>
                      <td>
                        <Badge value={item.priority} />
                      </td>
                      <td>
                        <Badge value={item.status} />
                      </td>
                    </>
                  )}
                  {view === "leave" && (
                    <>
                      <td>
                        <strong>{item.user_name}</strong>
                      </td>
                      <td>
                        {dateLabel(item.start_date)} –{" "}
                        {dateLabel(item.end_date)}
                      </td>
                      <td>{item.reason || "—"}</td>
                      <td>
                        <Badge value={item.status} />
                      </td>
                    </>
                  )}
                  {view === "directory" && (
                    <>
                      <td>
                        <div className="person-cell">
                          <span className="avatar small">
                            {item.name
                              ?.split(" ")
                              .map((n) => n[0])
                              .join("")}
                          </span>
                          <div>
                            <strong>{item.name}</strong>
                            <small>{item.email}</small>
                          </div>
                        </div>
                      </td>
                      <td>{item.department}</td>
                      <td>{item.manager_name || "—"}</td>
                      <td>
                        <Badge value={item.role} />
                      </td>
                    </>
                  )}
                  {view === "review" && (
                    <>
                      <td>
                        <strong>{item.user_name}</strong>
                      </td>
                      <td>
                        {item.kind === "timesheet" ? "Timesheet" : "Leave"}
                      </td>
                      <td>
                        {item.kind === "timesheet"
                          ? `Week of ${dateLabel(item.week_start)}`
                          : `${dateLabel(item.start_date)} – ${dateLabel(item.end_date)}`}
                      </td>
                      <td>
                        {item.kind === "timesheet"
                          ? `${item.total_hours} hours`
                          : item.reason || "—"}
                      </td>
                      <td>
                        <Badge value={item.status} />
                      </td>
                    </>
                  )}
                  {view === "activity" && (
                    <>
                      <td>{timestamp(item.created_at)}</td>
                      <td>{item.actor_name}</td>
                      <td>
                        <code>{item.action}</code>
                      </td>
                      <td>{item.resource_type?.replaceAll("_", " ")}</td>
                      <td>
                        <Badge value={item.source} />
                      </td>
                      <td>
                        <Badge value={item.outcome} />
                      </td>
                    </>
                  )}
                  <td>
                    {view !== "directory" && (
                      <button
                        className="text-button"
                        onClick={() => void details(item)}
                        aria-label={`View ${item.title || item.user_name || item.action}`}
                      >
                        {view === "review" ? "Review" : "View"}
                        <ChevronRight size={14} />
                      </button>
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
          {page.total} {view === "directory" ? "people" : "records"} · Updates
          every 10 seconds
        </span>
        <div className="pagination">
          <button
            className="icon-button"
            aria-label="Previous page"
            disabled={!offset}
            onClick={() => setOffset(offset - 50)}
          >
            <ChevronLeft size={17} />
          </button>
          <span>
            {Math.floor(offset / 50) + 1} /{" "}
            {Math.max(1, Math.ceil(page.total / 50))}
          </span>
          <button
            className="icon-button"
            aria-label="Next page"
            disabled={offset + 50 >= page.total}
            onClick={() => setOffset(offset + 50)}
          >
            <ChevronRight size={17} />
          </button>
        </div>
      </div>
    </section>
  );
}
