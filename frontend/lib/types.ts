export type View =
  | "timesheet"
  | "tasks"
  | "leave"
  | "tickets"
  | "directory"
  | "review"
  | "activity";
export type ModalKind = "create" | "entry" | "details";
export type Mutate = (
  path: string,
  method: string,
  body?: unknown,
  message?: string,
) => Promise<void>;
