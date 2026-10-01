"use client";
import {
  useEffect,
  useRef,
  useId,
  cloneElement,
  isValidElement,
  type ReactElement,
} from "react";
import { X, Inbox, Loader2 } from "lucide-react";
export function Badge({ value }: { value?: string }) {
  return (
    <span className={`badge badge-${value?.toLowerCase()}`}>
      {value?.replaceAll("_", " ") || "—"}
    </span>
  );
}
export function Empty({
  title = "Nothing here yet",
  text = "New records will appear here.",
}: {
  title?: string;
  text?: string;
}) {
  return (
    <div className="empty">
      <Inbox size={32} strokeWidth={1.3} />
      <h3>{title}</h3>
      <p>{text}</p>
    </div>
  );
}
export function Loading() {
  return (
    <div className="empty" role="status">
      <Loader2 className="spin" size={24} />
      <p>Loading your workspace…</p>
    </div>
  );
}
export function Modal({
  title,
  children,
  close,
}: {
  title: string;
  children: React.ReactNode;
  close: () => void;
}) {
  const ref = useRef<HTMLDialogElement>(null);
  useEffect(() => {
    const dialog = ref.current;
    dialog?.showModal();
    return () => dialog?.close();
  }, []);
  return (
    <dialog
      ref={ref}
      onCancel={close}
      onClick={(e) => {
        if (e.target === ref.current) close();
      }}
      className="modal"
    >
      <div className="modal-head">
        <h2>{title}</h2>
        <button
          className="icon-button"
          aria-label="Close dialog"
          onClick={close}
        >
          <X size={20} />
        </button>
      </div>
      {children}
    </dialog>
  );
}
export function Field({
  label,
  children,
}: {
  label: string;
  children: React.ReactNode;
}) {
  const id = useId();
  return (
    <div className="field">
      <label htmlFor={id}>{label}</label>
      {isValidElement(children)
        ? cloneElement(children as ReactElement<{ id: string }>, { id })
        : children}
    </div>
  );
}
