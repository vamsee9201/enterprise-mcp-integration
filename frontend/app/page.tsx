"use client";
import {
  useCallback,
  useEffect,
  useRef,
  useState,
  type FormEvent,
} from "react";
import {
  Activity,
  ArrowRight,
  CalendarDays,
  Check,
  ChevronRight,
  Clock3,
  ClipboardCheck,
  HelpCircle,
  ListTodo,
  LogOut,
  Menu,
  Sprout,
  Plus,
  Plug,
  RefreshCw,
  ShieldCheck,
  Users,
  X,
} from "lucide-react";
import {
  api,
  ApiError,
  setCsrf,
  today,
  weekOf,
  type User,
  type Project,
  type Sheet,
  type Entry,
  type Item,
  type Page,
} from "../lib/api";
import { Loading } from "../components/ui";

import type { View, ModalKind } from "../lib/types";
import { TimesheetView } from "../components/timesheet-view";
import { RecordsView } from "../components/records-view";
import { WorkflowDialog } from "../components/workflow-dialog";

const navigation = [
  {
    id: "timesheet",
    label: "My Timesheet",
    icon: Clock3,
    caption: "A clear view of your working week.",
  },
  {
    id: "tasks",
    label: "Tasks",
    icon: ListTodo,
    caption: "Keep everyday work moving forward.",
  },
  {
    id: "leave",
    label: "Leave",
    icon: CalendarDays,
    caption: "Plan time away and follow your requests.",
  },
  {
    id: "tickets",
    label: "Support Tickets",
    icon: HelpCircle,
    caption: "Get help and track issues to resolution.",
  },
  {
    id: "directory",
    label: "Employee Directory",
    icon: Users,
    caption: "Find the people behind the work.",
  },
  {
    id: "review",
    label: "Manager Review",
    icon: ClipboardCheck,
    caption: "Review your team’s timesheets and leave.",
  },
  {
    id: "activity",
    label: "Activity",
    icon: Activity,
    caption: "Every change, with a clear trail.",
  },
] as const;
const endpoints: Record<Exclude<View, "timesheet">, string> = {
  tasks: "/tasks",
  leave: "/leave-requests",
  tickets: "/tickets",
  directory: "/employees",
  review: "/approvals",
  activity: "/audit-events",
};

export default function Portal() {
  const [user, setUser] = useState<User | null>(null),
    [accounts, setAccounts] = useState<User[]>([]),
    [booting, setBooting] = useState(true);
  const [view, setView] = useState<View>("timesheet"),
    [week, setWeek] = useState(weekOf(today()));
  const [projects, setProjects] = useState<Project[]>([]),
    [people, setPeople] = useState<User[]>([]);
  const [sheet, setSheet] = useState<Sheet | null>(null),
    [page, setPage] = useState<Page<Item>>({
      items: [],
      total: 0,
      limit: 50,
      offset: 0,
    });
  const [filters, setFilters] = useState<Record<string, string>>({}),
    [offset, setOffset] = useState(0);
  const [loading, setLoading] = useState(false),
    [busy, setBusy] = useState(false),
    [error, setError] = useState(""),
    [notice, setNotice] = useState("");
  const [modal, setModal] = useState<ModalKind | null>(null),
    [selected, setSelected] = useState<Item | null>(null),
    [editing, setEditing] = useState<Entry | null>(null);
  const [entryDefaults, setEntryDefaults] = useState<{
    project_id: string;
    work_date: string;
  } | null>(null);
  const [formError, setFormError] = useState(""),
    [mobile, setMobile] = useState(false);
  const version = useRef(0);
  const manager = user?.role !== "EMPLOYEE";
  const active = navigation.find((n) => n.id === view)!;

  const clearWorkspace = useCallback(() => {
    ++version.current;
    setNotice("");
    setError("");
    setFormError("");
    setSelected(null);
    setEditing(null);
    setEntryDefaults(null);
    setSheet(null);
    setProjects([]);
    setPeople([]);
    setPage({ items: [], total: 0, limit: 50, offset: 0 });
    setView("timesheet");
    setFilters({});
    setOffset(0);
    setModal(null);
    setMobile(false);
    setLoading(false);
  }, []);

  useEffect(() => {
    async function init() {
      try {
        const auth = await api<{ user: User; csrf_token: string }>("/auth/me");
        setCsrf(auth.csrf_token);
        setUser(auth.user);
      } catch (e) {
        if (e instanceof ApiError && e.status === 401) {
          try {
            setAccounts(await api<User[]>("/auth/demo-accounts"));
          } catch (err) {
            setError((err as Error).message);
          }
        } else setError((e as Error).message);
      } finally {
        setBooting(false);
      }
    }
    void init();
  }, []);

  useEffect(() => {
    if (!user) return;
    let live = true;
    Promise.all([
      api<Page<Project>>("/projects?limit=100"),
      api<Page<User>>("/employees?limit=100"),
    ])
      .then(([p, u]) => {
        if (live) {
          setProjects(p.items);
          setPeople(u.items);
        }
      })
      .catch((e) => {
        if (live) setError(e.message);
      });
    return () => {
      live = false;
    };
  }, [user]);

  const load = useCallback(
    async (showLoading = false, reconcileSession = false) => {
      if (!user && !reconcileSession) return;
      const v = ++version.current;
      if (showLoading) setLoading(true);
      try {
        // Cookies are shared across tabs. Reconcile identity before loading records.
        const auth = await api<{ user: User; csrf_token: string }>("/auth/me");
        if (v !== version.current) return;
        setCsrf(auth.csrf_token);
        if (!user || auth.user.id !== user.id || auth.user.role !== user.role) {
          clearWorkspace();
          setUser(auth.user);
          return;
        }
        if (view === "review" && user.role === "EMPLOYEE") return;
        const query = new URLSearchParams(
          Object.entries(filters).filter(([, v]) => v),
        );
        query.set("offset", String(offset));
        query.set("limit", "50");
        if (view === "timesheet") {
          const next = await api<Sheet>(`/timesheets/me?week=${week}`);
          if (v === version.current) setSheet(next);
        } else {
          const next = await api<Page<Item>>(`${endpoints[view]}?${query}`);
          if (v === version.current) setPage(next);
        }
        if (v === version.current) setError("");
      } catch (e) {
        if (v === version.current) {
          setError((e as Error).message);
          if (e instanceof ApiError && e.status === 401) {
            clearWorkspace();
            setUser(null);
            setCsrf("");
            setAccounts(
              await api<User[]>("/auth/demo-accounts").catch(() => []),
            );
          }
        }
      } finally {
        if (v === version.current) setLoading(false);
      }
    },
    [user, view, week, filters, offset, clearWorkspace],
  );

  useEffect(() => {
    void load(true);
    const refresh = () => {
      if (document.visibilityState === "visible") void load(false, true);
    };
    const interval = setInterval(refresh, 10000);
    window.addEventListener("focus", refresh);
    const sessionChanged = (event: StorageEvent) => {
      if (event.key === "portal-session-changed") void load(true, true);
    };
    window.addEventListener("storage", sessionChanged);
    return () => {
      ++version.current;
      clearInterval(interval);
      window.removeEventListener("focus", refresh);
      window.removeEventListener("storage", sessionChanged);
    };
  }, [load]);

  useEffect(() => {
    if (!notice) return;
    const timeout = setTimeout(() => setNotice(""), 4500);
    return () => clearTimeout(timeout);
  }, [notice]);

  async function login(account: User) {
    setBusy(true);
    setError("");
    try {
      const auth = await api<{ user: User; csrf_token: string }>(
        "/auth/demo-login",
        "POST",
        { user_id: account.id },
      );
      setCsrf(auth.csrf_token);
      clearWorkspace();
      setUser(auth.user);
      localStorage.setItem("portal-session-changed", crypto.randomUUID());
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }
  async function logout() {
    setBusy(true);
    try {
      await api("/auth/logout", "POST");
      clearWorkspace();
      setUser(null);
      setCsrf("");
      localStorage.setItem("portal-session-changed", crypto.randomUUID());
      setAccounts(await api<User[]>("/auth/demo-accounts"));
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }
  function navigate(next: View) {
    setView(next);
    setFilters({});
    setOffset(0);
    setPage({ items: [], total: 0, limit: 50, offset: 0 });
    setMobile(false);
    setError("");
  }
  function filter(key: string, value: string) {
    setOffset(0);
    setFilters((f) => ({ ...f, [key]: value }));
  }
  function open(kind: typeof modal, item: Item | null = null) {
    setModal(kind);
    setSelected(item);
    setFormError("");
    setEditing(null);
    setEntryDefaults(null);
  }
  async function mutate(
    path: string,
    method: string,
    body?: unknown,
    message = "Changes saved",
  ) {
    setBusy(true);
    setFormError("");
    try {
      const auth = await api<{ user: User; csrf_token: string }>("/auth/me");
      if (auth.user.id !== user?.id || auth.user.role !== user?.role) {
        clearWorkspace();
        setCsrf(auth.csrf_token);
        setUser(auth.user);
        return;
      }
      setCsrf(auth.csrf_token);
      await api(path, method, body);
      setModal(null);
      setNotice(message);
      await load();
    } catch (e) {
      if (modal) setFormError((e as Error).message);
      else setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }
  function values(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    return Object.fromEntries(new FormData(e.currentTarget));
  }
  function submitEntry(e: FormEvent<HTMLFormElement>) {
    const b = values(e);
    void mutate(
      editing ? `/time-entries/${editing.id}` : "/time-entries",
      editing ? "PUT" : "POST",
      { ...b, hours: Number(b.hours) },
      "Time entry saved",
    );
  }
  function submitNew(e: FormEvent<HTMLFormElement>) {
    const b = values(e);
    if (view === "tasks") {
      b.project_id ||= "";
      void mutate(
        selected ? `/tasks/${selected.id}` : "/tasks",
        selected ? "PUT" : "POST",
        {
          ...b,
          project_id: b.project_id || null,
          due_date: b.due_date || null,
        },
        "Task saved",
      );
    }
    if (view === "leave")
      void mutate("/leave-requests", "POST", b, "Leave requested");
    if (view === "tickets")
      void mutate("/tickets", "POST", b, "Ticket created");
  }
  async function details(item: Item) {
    open("details", item);
    try {
      const path =
        view === "review"
          ? item.kind === "timesheet"
            ? `/timesheets/${item.id}`
            : `/leave-requests/${item.id}`
          : `${endpoints[view as Exclude<View, "timesheet">]}/${item.id}`;
      if (view !== "activity")
        setSelected({ ...(await api<Item>(path)), kind: item.kind });
    } catch (e) {
      setFormError((e as Error).message);
    }
  }
  function assignees() {
    return people.filter(
      (p) =>
        user?.role === "ADMIN" ||
        p.id === user?.id ||
        p.manager_id === user?.id,
    );
  }

  if (booting) return <Loading />;
  if (!user)
    return (
      <main className="login">
        <div className="login-brand">
          <Sprout size={32} />
          <strong>
            pied piper<span>OPERATIONS</span>
          </strong>
        </div>
        <div className="login-card">
          <div className="eyebrow">YOUR DEMO WORKSPACE</div>
          <h1>Work, connected.</h1>
          <p>Choose a demo account to explore everyday enterprise workflows.</p>
          {error && (
            <div className="alert" role="alert">
              {error}
            </div>
          )}
          <div className="accounts">
            {accounts.map((a) => (
              <button
                key={a.id}
                disabled={busy}
                onClick={() => void login(a)}
                aria-label={`Sign in as ${a.name}`}
              >
                <span className="avatar">
                  {a.name
                    .split(" ")
                    .map((n) => n[0])
                    .join("")}
                </span>
                <span>
                  <strong>{a.name}</strong>
                  <small>
                    {a.department} · {a.role.toLowerCase()}
                  </small>
                </span>
                <ArrowRight size={18} />
              </button>
            ))}
          </div>
          <div className="login-note">
            <ShieldCheck size={16} /> Seeded identities · local demo environment
          </div>
        </div>
        <p className="login-footer">
          One workspace. Shared rules. People and agents.
        </p>
      </main>
    );

  return (
    <div className="shell">
      <aside className={`sidebar ${mobile ? "mobile-open" : ""}`}>
        <div className="brand">
          <Sprout size={30} />
          <strong>
            pied piper<span>OPERATIONS</span>
          </strong>
          <button
            className="mobile-close icon-button"
            aria-label="Close navigation"
            onClick={() => setMobile(false)}
          >
            <X size={18} />
          </button>
        </div>
        <div className="workspace-tag">
          <span className="dot" /> Demo workspace <span>LOCAL</span>
        </div>
        <div className="nav-caption">WORKSPACE</div>
        <nav aria-label="Main navigation">
          {navigation.map(({ id, label, icon: Icon }) => (
            <button
              key={id}
              aria-label={label}
              className={view === id ? "active" : ""}
              onClick={() => navigate(id)}
              aria-current={view === id ? "page" : undefined}
            >
              <Icon size={19} />
              {label}
              {id === "review" && user.role === "EMPLOYEE" && (
                <span className="nav-restriction">Mgr</span>
              )}
            </button>
          ))}
        </nav>
        <div className="sidebar-bottom">
          <div className="agent-note">
            <Plug size={19} />
            <div>
              <strong>Team workspace</strong>
              <p>Everyday work in one place.</p>
            </div>
          </div>
        </div>
      </aside>
      <div className="main-shell">
        <header className="topbar">
          <button
            className="icon-button mobile-menu"
            aria-label="Open navigation"
            onClick={() => setMobile(true)}
          >
            <Menu size={21} />
          </button>
          <div className="breadcrumb">
            Workspace <ChevronRight size={14} />
            <strong>{active.label}</strong>
          </div>
          <div className="identity">
            <span className="avatar small">
              {user.name
                .split(" ")
                .map((n) => n[0])
                .join("")}
            </span>
            <span>
              <strong>{user.name}</strong>
              <small>{user.role.toLowerCase()}</small>
            </span>
            <button
              className="icon-button"
              disabled={busy}
              aria-label="Switch account"
              title="Switch account"
              onClick={() => void logout()}
            >
              <LogOut size={18} />
            </button>
          </div>
        </header>
        <main className="content">
          <div className="page-heading">
            <div>
              <div className="eyebrow">
                WORKSPACE / {active.label.toUpperCase()}
              </div>
              <h1>{active.label}</h1>
              <p>{active.caption}</p>
            </div>
            <div className="heading-actions">
              <span className="live-indicator">
                <span className="dot" /> Live workspace
              </span>
              <button
                className="icon-button"
                aria-label="Refresh records"
                onClick={() => void load(true)}
              >
                <RefreshCw size={18} />
              </button>
              {view === "timesheet" && (
                <button
                  className="primary"
                  disabled={
                    !sheet || !["DRAFT", "REJECTED"].includes(sheet.status)
                  }
                  onClick={() => open("entry")}
                >
                  <Plus size={17} /> Log time
                </button>
              )}
              {(["leave", "tickets"].includes(view) ||
                (view === "tasks" && manager)) && (
                <button className="primary" onClick={() => open("create")}>
                  <Plus size={17} />
                  {view === "tasks"
                    ? "New task"
                    : view === "leave"
                      ? "Request leave"
                      : "New ticket"}
                </button>
              )}
            </div>
          </div>
          {error && (
            <div className="alert" role="alert">
              {error}
            </div>
          )}
          {notice && (
            <div className="toast" role="status">
              <Check size={17} />
              {notice}
            </div>
          )}
          {view === "timesheet" ? (
            <TimesheetView
              key={week}
              sheet={sheet}
              projects={projects}
              week={week}
              setWeek={setWeek}
              loading={loading}
              busy={busy}
              openEntry={(entry, projectId, workDate) => {
                open("entry");
                setEditing(entry);
                setEntryDefaults({
                  project_id: projectId,
                  work_date: workDate,
                });
              }}
              mutate={mutate}
            />
          ) : (
            <RecordsView
              view={view}
              manager={manager}
              loading={loading}
              page={page}
              filters={filters}
              offset={offset}
              setOffset={setOffset}
              filter={filter}
              people={people}
              assignees={assignees}
              details={details}
            />
          )}
          <footer className="content-footer">
            <span>Pied Piper Operations</span>
            <span>Shared workflows for people & agents</span>
          </footer>
        </main>
      </div>

      {modal && (
        <WorkflowDialog
          modal={modal}
          view={view}
          editing={editing}
          entryDefaults={entryDefaults}
          selected={selected}
          formError={formError}
          busy={busy}
          manager={manager}
          projects={projects}
          user={user}
          people={people}
          week={week}
          assignees={assignees}
          submitEntry={submitEntry}
          submitNew={submitNew}
          values={values}
          mutate={mutate}
          setModal={setModal}
          setFormError={setFormError}
        />
      )}
    </div>
  );
}
