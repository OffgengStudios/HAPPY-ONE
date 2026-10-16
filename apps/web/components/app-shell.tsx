import {
  Activity,
  BriefcaseBusiness,
  ClipboardList,
  Gauge,
  Megaphone,
  Users,
} from "lucide-react";
import { env } from "@/lib/env";

const workstreams = [
  { name: "Demand", icon: BriefcaseBusiness },
  { name: "Supply", icon: Users },
  { name: "Matching", icon: ClipboardList },
  { name: "M&E / MERL", icon: Activity },
  { name: "Marketing", icon: Megaphone },
  { name: "Management", icon: Gauge },
];

export function AppShell() {
  return (
    <main className="min-h-screen font-sans">
      <header className="border-b border-border bg-white">
        <div className="mx-auto flex max-w-7xl flex-wrap items-center justify-between gap-4 px-6 py-4">
          <h1 className="text-xl font-semibold text-foreground">
            HAPPY Management Platform
          </h1>
          <span className="text-sm capitalize text-muted">
            {env.environment}
          </span>
        </div>
      </header>

      <section className="mx-auto max-w-7xl px-6 py-8">
        <h2 className="text-lg font-semibold">My Work</h2>
        <div className="my-6 flex min-h-40 flex-col items-center justify-center gap-3 border-y border-border text-muted">
          <ClipboardList aria-hidden="true" className="h-6 w-6" />
          <p className="text-sm">No assigned tasks</p>
        </div>
        <h2 className="mb-4 text-lg font-semibold">Workstreams</h2>
        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
          {workstreams.map((item) => {
            const Icon = item.icon;
            return (
              <article
                key={item.name}
                className="flex items-center gap-3 rounded-md border border-border bg-white p-4"
              >
                <Icon
                  aria-hidden="true"
                  className="h-5 w-5 shrink-0 text-primary"
                />
                <h3 className="text-base font-medium">{item.name}</h3>
              </article>
            );
          })}
        </div>
      </section>
    </main>
  );
}
