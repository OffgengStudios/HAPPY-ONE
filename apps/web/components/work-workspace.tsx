"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Check, Handshake, Inbox, ListTodo, Plus } from "lucide-react";
import { FormEvent, useState } from "react";
import { api, Me, time } from "@/lib/api";

type Task = {
  id: string; task_code: string; title: string; description: string | null;
  status: string; priority: string; owner_user_id: string | null; owner_team: string | null;
  due_at: string | null; version: number;
};
type Handoff = {
  id: string; from_workstream: string; to_workstream: string; entity_type: string;
  entity_id: string; reason: string; status: string; assigned_to: string | null; version: number;
};
type Notification = {
  id: string; title: string; body: string; kind: string; read_at: string | null;
  created_at: string; version: number;
};

export function WorkWorkspace({ user, workspace }: { user: Me; workspace: string }) {
  const client = useQueryClient();
  const [tab, setTab] = useState<"tasks" | "handoffs" | "notifications">("tasks");
  const [creating, setCreating] = useState(false);
  const [error, setError] = useState("");
  const tasks = useQuery({ queryKey: ["tasks"], queryFn: () => api<{items: Task[]}>("/tasks") });
  const handoffs = useQuery({ queryKey: ["handoffs"], queryFn: () => api<{items: Handoff[]}>("/handoffs") });
  const notices = useQuery({ queryKey: ["notifications"], queryFn: () => api<{items: Notification[]}>("/notifications") });
  const mutation = useMutation({
    mutationFn: ({ path, body }: { path: string; body: unknown }) => api(path, "POST", body),
    onSuccess: async () => { setError(""); setCreating(false); await client.invalidateQueries(); },
    onError: (value) => setError(value instanceof Error ? value.message : "Unable to save."),
  });
  const tabs = [
    ["tasks", "Tasks", ListTodo], ["handoffs", "Handoffs", Handshake], ["notifications", "Notifications", Inbox],
  ] as const;
  return <div className="space-y-6">
    <div className="flex flex-wrap items-center justify-between gap-3">
      <div><h2 className="text-xl font-semibold">My Work</h2><p className="mt-1 text-sm text-muted">Assignments and cross-workstream follow-through</p></div>
      {tab !== "notifications" && <button className="command primary" onClick={() => setCreating(true)}><Plus className="h-4 w-4" />{tab === "tasks" ? "New task" : "Send handoff"}</button>}
    </div>
    <div className="flex gap-1 border-b border-border" role="tablist">
      {tabs.map(([id, label, Icon]) => <button key={id} role="tab" aria-selected={tab === id} className={"command rounded-b-none border-b-2 " + (tab === id ? "border-primary text-primary" : "border-transparent")} onClick={() => setTab(id)}><Icon className="h-4 w-4" />{label}</button>)}
    </div>
    {error && <p role="alert" className="text-sm text-red-700">{error}</p>}
    {creating && (tab === "tasks" ? <TaskForm workspace={workspace} onCancel={() => setCreating(false)} onSubmit={(body) => mutation.mutate({path: "/tasks", body})} /> : <HandoffForm workspace={workspace} workspaces={user.workspaces.map((item) => item.code)} onCancel={() => setCreating(false)} onSubmit={(body) => mutation.mutate({path: "/handoffs", body})} />)}
    {tab === "tasks" && <RecordList pending={tasks.isPending} empty="No assigned tasks" items={tasks.data?.items.map((row) => <li key={row.id} className="flex items-start justify-between gap-4 py-4"><div><p className="font-medium">{row.title}</p><p className="mt-1 text-xs text-muted">{row.task_code} · {row.priority} · {row.owner_team ?? "Personal"}{row.due_at ? ` · Due ${time(row.due_at)}` : ""}</p>{row.description && <p className="mt-2 text-sm">{row.description}</p>}</div>{!['COMPLETED','CANCELLED'].includes(row.status) && <button className="icon-button" title="Complete task" aria-label="Complete task" onClick={() => mutation.mutate({path: `/tasks/${row.id}/complete`, body: {version: row.version}})}><Check className="h-4 w-4" /></button>}</li>)} />}
    {tab === "handoffs" && <RecordList pending={handoffs.isPending} empty="No handoffs" items={handoffs.data?.items.map((row) => <li key={row.id} className="flex items-start justify-between gap-4 py-4"><div><p className="font-medium">{row.from_workstream} to {row.to_workstream}</p><p className="mt-1 text-xs text-muted">{row.entity_type} · {row.status}</p><p className="mt-2 text-sm">{row.reason}</p></div>{row.status === 'SENT' && <button className="command" onClick={() => mutation.mutate({path: `/handoffs/${row.id}/accept`, body: {version: row.version}})}>Accept</button>}</li>)} />}
    {tab === "notifications" && <RecordList pending={notices.isPending} empty="No notifications" items={notices.data?.items.map((row) => <li key={row.id} className={"py-4 " + (!row.read_at ? "font-medium" : "")}><button className="w-full text-left" onClick={() => !row.read_at && mutation.mutate({path: `/notifications/${row.id}/read`, body: {version: row.version}})}><span>{row.title}</span><span className="mt-1 block text-sm font-normal">{row.body}</span><span className="mt-1 block text-xs font-normal text-muted">{time(row.created_at)}</span></button></li>)} />}
  </div>;
}

function RecordList({pending, empty, items}: {pending: boolean; empty: string; items?: React.ReactNode[]}) {
  if (pending) return <p role="status" className="text-sm text-muted">Loading...</p>;
  return items?.length ? <ul className="divide-y divide-border border-y border-border">{items}</ul> : <div className="flex min-h-40 items-center justify-center border-y border-border text-sm text-muted">{empty}</div>;
}

function TaskForm({workspace, onCancel, onSubmit}: {workspace: string; onCancel: () => void; onSubmit: (body: unknown) => void}) {
  function submit(event: FormEvent<HTMLFormElement>) { event.preventDefault(); const form = new FormData(event.currentTarget); onSubmit({title: form.get("title"), description: form.get("description") || null, priority: form.get("priority"), owner_team: workspace || null, due_at: form.get("due_at") || null}); }
  return <form className="grid gap-4 border-y border-border py-5 sm:grid-cols-2" onSubmit={submit}><label className="field-label sm:col-span-2">Title<input className="field" name="title" required maxLength={200}/></label><label className="field-label">Priority<select className="field" name="priority" defaultValue="NORMAL"><option>NORMAL</option><option>HIGH</option><option>URGENT</option><option>LOW</option></select></label><label className="field-label">Due date<input className="field" type="datetime-local" name="due_at"/></label><label className="field-label sm:col-span-2">Description<textarea className="field" name="description" maxLength={4000}/></label><div className="flex gap-2 sm:col-span-2"><button className="command primary" type="submit">Create task</button><button className="command" type="button" onClick={onCancel}>Cancel</button></div></form>;
}

function HandoffForm({workspace, workspaces, onCancel, onSubmit}: {workspace: string; workspaces: string[]; onCancel: () => void; onSubmit: (body: unknown) => void}) {
  function submit(event: FormEvent<HTMLFormElement>) { event.preventDefault(); const form = new FormData(event.currentTarget); onSubmit({from_workstream: workspace, to_workstream: form.get("to_workstream"), entity_type: form.get("entity_type"), entity_id: form.get("entity_id"), reason: form.get("reason")}); }
  return <form className="grid gap-4 border-y border-border py-5 sm:grid-cols-2" onSubmit={submit}><label className="field-label">To workspace<select className="field" name="to_workstream" required>{workspaces.filter((item) => item !== workspace).map((item) => <option key={item}>{item}</option>)}</select></label><label className="field-label">Record type<input className="field" name="entity_type" pattern="[A-Z][A-Z0-9_]*" required/></label><label className="field-label sm:col-span-2">Record ID<input className="field" name="entity_id" required/></label><label className="field-label sm:col-span-2">Reason<textarea className="field" name="reason" required maxLength={4000}/></label><div className="flex gap-2 sm:col-span-2"><button className="command primary" type="submit">Send handoff</button><button className="command" type="button" onClick={onCancel}>Cancel</button></div></form>;
}
