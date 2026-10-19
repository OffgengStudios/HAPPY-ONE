"use client";

import {
  QueryClient,
  QueryClientProvider,
  useQuery,
  useQueryClient,
} from "@tanstack/react-query";
import {
  ClipboardList,
  FileClock,
  LoaderCircle,
  ListTodo,
  LogIn,
  ShieldCheck,
  Users,
  KeyRound,
  LayoutDashboard,
  Building2,
  BriefcaseBusiness,
  CalendarDays,
  Columns3,
  CircleDollarSign,
  MapPinCheck,
  Activity,
  BarChart3,
  ShieldAlert,
  Megaphone,
  Send,
  Sparkles,
  FileChartColumn,
  Target,
  Inbox,
  GraduationCap,
} from "lucide-react";
import { FormEvent, useEffect, useRef, useState } from "react";
import { api, ApiError, Me } from "@/lib/api";
import { env } from "@/lib/env";
import { IamAdmin } from "./iam-admin";
import { IntakeOperations } from "./intake-operations";
import { SecuritySettings } from "./security-settings";
import { DemandWorkspace } from "./demand-workspace";
import { SupplyWorkspace } from "./supply-workspace";
import { AccountNavigation } from "./account-navigation";
import { ProfileMenu } from "./profile-menu";
import { GlobalSearch } from "./global-search";
import { SearchItem } from "@/lib/search";
import { QuickAdd, QuickAddKind } from "./quick-add";
import { MatchingWorkspace } from "./matching-workspace";
import { PlacementWorkspace } from "./placement-workspace";
import { MerlWorkspace } from "./merl-workspace";
import { MarketingWorkspace } from "./marketing-workspace";
import { ReportingWorkspace } from "./reporting-workspace";
import { EmployerSubmissionWorkspace } from "./employer-submission-workspace";
import { TrainingWorkspace } from "./training-workspace";
import { WorkWorkspace } from "./work-workspace";

export function AuthExperience() {
  const [client] = useState(
    () => new QueryClient({ defaultOptions: { queries: { retry: false } } }),
  );
  return (
    <QueryClientProvider client={client}>
      <Experience />
    </QueryClientProvider>
  );
}

function Header({
  children,
  compact = false,
}: {
  children?: React.ReactNode;
  compact?: boolean;
}) {
  return (
    <header
      className={
        compact
          ? "sticky top-0 z-10 border-b border-border bg-white/95 backdrop-blur-md"
          : "border-b border-t-2 border-border border-t-primary bg-white"
      }
    >
      <div className="flex min-h-16 items-center justify-between gap-3 px-5 py-3 md:min-h-[70px] md:px-7">
        <div className={"min-w-0 " + (compact ? "md:hidden" : "")}>
          <h1
            aria-label="HAPPY Management Platform"
            className="text-lg font-semibold text-primary sm:text-xl"
          >
            HAPPY
            {compact ? (
              <span className="hidden md:inline"> Management Platform</span>
            ) : (
              " Management Platform"
            )}
          </h1>
          <span className="text-xs capitalize text-muted">
            {env.environment} · v{env.releaseVersion}
          </span>
        </div>
        {children}
      </div>
    </header>
  );
}

function SignIn({ onSuccess }: { onSuccess: () => Promise<unknown> }) {
  const sso = useQuery({
    queryKey: ["sso-config"],
    queryFn: () =>
      api<{ enabled: boolean; provider_name: string }>("/auth/sso/config"),
  });
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [code, setCode] = useState("");
  const [mfa, setMfa] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  async function submit(event: FormEvent) {
    event.preventDefault();
    setBusy(true);
    setError("");
    try {
      const result = await api<{ mfa_required: boolean }>(
        mfa ? "/auth/mfa/verify" : "/auth/login",
        "POST",
        mfa ? { code } : { email, password },
      );
      setPassword("");
      if (result.mfa_required) setMfa(true);
      else await onSuccess();
    } catch (error) {
      setError(error instanceof Error ? error.message : "Sign-in failed.");
    } finally {
      setBusy(false);
    }
  }
  async function startSso() {
    setBusy(true);
    setError("");
    try {
      const result = await api<{ authorization_url: string }>(
        "/auth/sso/start",
        "POST",
      );
      window.location.assign(result.authorization_url);
    } catch (error) {
      setError(
        error instanceof Error ? error.message : "Single sign-on failed.",
      );
      setBusy(false);
    }
  }
  return (
    <main className="min-h-screen">
      <Header />
      <section className="sign-in-surface mx-auto max-w-sm px-5 py-16">
        <KeyRound aria-hidden="true" className="mb-5 h-7 w-7 text-primary" />
        <h2 className="mb-7 text-2xl font-semibold">
          {mfa ? "Verify your account" : "Sign in"}
        </h2>
        <form className="space-y-5" onSubmit={submit}>
          {mfa ? (
            <label className="field-label">
              Verification code
              <input
                className="field"
                autoComplete="one-time-code"
                inputMode="numeric"
                required
                maxLength={128}
                value={code}
                onChange={(event) => setCode(event.target.value)}
                autoFocus
              />
            </label>
          ) : (
            <>
              <label className="field-label">
                Email
                <input
                  className="field"
                  type="email"
                  autoComplete="username"
                  required
                  maxLength={254}
                  value={email}
                  onChange={(event) => setEmail(event.target.value)}
                />
              </label>
              <label className="field-label">
                Password
                <input
                  className="field"
                  type="password"
                  autoComplete="current-password"
                  required
                  maxLength={128}
                  value={password}
                  onChange={(event) => setPassword(event.target.value)}
                />
              </label>
            </>
          )}
          {error && (
            <p role="alert" className="text-sm text-red-700">
              {error}
            </p>
          )}
          <button
            disabled={busy}
            className="command primary w-full"
            type="submit"
          >
            {busy ? (
              <LoaderCircle className="h-4 w-4 animate-spin" />
            ) : (
              <LogIn className="h-4 w-4" />
            )}
            {busy ? "Signing in..." : mfa ? "Verify" : "Sign in"}
          </button>
          {mfa && (
            <button
              className="command w-full"
              type="button"
              onClick={() => {
                setMfa(false);
                setCode("");
                setError("");
              }}
            >
              Back to sign in
            </button>
          )}
        </form>
        {!mfa && sso.data?.enabled && (
          <div className="mt-6 border-t border-border pt-6">
            <button
              className="command w-full"
              disabled={busy}
              type="button"
              onClick={() => void startSso()}
            >
              <ShieldCheck className="h-4 w-4" />
              Sign in with {sso.data.provider_name}
            </button>
          </div>
        )}
      </section>
    </main>
  );
}

function Experience() {
  const client = useQueryClient();
  const me = useQuery({
    queryKey: ["me"],
    queryFn: () => api<Me>("/auth/me"),
    staleTime: 0,
  });
  const [view, setView] = useState("work");
  const [navigationVersion, setNavigationVersion] = useState(0);
  const [workspace, setWorkspace] = useState("");
  const [error, setError] = useState("");
  const [record, setRecord] = useState<SearchItem | null>(null);
  const [create, setCreate] = useState<QuickAddKind | null>(null);
  const content = useRef<HTMLElement>(null);
  useEffect(() => {
    if (window.matchMedia("(prefers-reduced-motion: reduce)").matches) return;
    const animation = content.current?.animate(
      [
        { opacity: 0, transform: "translateY(6px)" },
        { opacity: 1, transform: "translateY(0)" },
      ],
      { duration: 260, easing: "cubic-bezier(0.22, 1, 0.36, 1)" },
    );
    const preference = window.matchMedia("(prefers-reduced-motion: reduce)");
    const stop = () => {
      if (preference.matches) animation?.cancel();
    };
    preference.addEventListener("change", stop);
    return () => {
      animation?.cancel();
      preference.removeEventListener("change", stop);
    };
  }, [view, workspace, navigationVersion, me.data?.id]);
  useEffect(() => {
    if (record) content.current?.focus({ preventScroll: true });
  }, [record]);
  useEffect(() => {
    const expired = () => {
      void client.invalidateQueries({ queryKey: ["me"] });
    };
    window.addEventListener("happy:auth-expired", expired);
    return () => window.removeEventListener("happy:auth-expired", expired);
  }, [client]);
  if (me.isPending)
    return (
      <main>
        <Header />
        <div
          role="status"
          className="flex justify-center gap-2 p-16 text-sm text-muted"
        >
          <LoaderCircle className="h-4 w-4 animate-spin" />
          Loading account...
        </div>
      </main>
    );
  if (!me.data || (me.error instanceof ApiError && me.error.status === 401)) {
    if (me.error instanceof ApiError && me.error.status === 401) {
      return (
        <SignIn
          onSuccess={async () => {
            client.removeQueries();
            setView("work");
            setWorkspace("");
            setRecord(null);
            setCreate(null);
            await me.refetch();
          }}
        />
      );
    }
    return (
      <main>
        <Header />
        <section className="mx-auto max-w-md space-y-5 p-8">
          <p role="alert">Unable to reach your account.</p>
          <button className="command" onClick={() => void me.refetch()}>
            Retry
          </button>
        </section>
      </main>
    );
  }
  const user = me.data;
  const selected =
    user.workspaces.find((item) => item.code === workspace) ??
    user.workspaces[0];
  const navigation = [
    {
      id: "work",
      name:
        selected?.code === "MANAGEMENT" ? "Attention & Approvals" : "My Work",
      icon: ClipboardList,
      allowed: true,
    },
    {
      id: "tasks",
      name: "Tasks & Handoffs",
      icon: ListTodo,
      allowed: user.permissions.includes("task:view"),
    },
    {
      id: "dashboard",
      name: "Dashboard",
      icon: LayoutDashboard,
      allowed: [
        "DEMAND",
        "SUPPLY",
        "MATCHING",
        "MERL",
        "MARKETING",
        "MANAGEMENT",
      ].includes(selected?.code ?? ""),
    },
    {
      id: "performance",
      name: "Performance",
      icon: Target,
      allowed:
        selected?.code === "MANAGEMENT" &&
        user.permissions.includes("report:view"),
    },
    {
      id: "reports",
      name: "Reports & Targets",
      icon: FileChartColumn,
      allowed:
        selected?.code === "MANAGEMENT" &&
        user.permissions.includes("report:view"),
    },
    {
      id: "requests",
      name: "Marketing Requests",
      icon: Send,
      allowed: user.permissions.includes("marketing_request:view"),
    },
    {
      id: "campaigns",
      name: "Campaigns",
      icon: Megaphone,
      allowed: user.permissions.includes("campaign:view"),
    },
    {
      id: "impact-stories",
      name: "Impact Stories",
      icon: Sparkles,
      allowed: user.permissions.includes("impact_story:view"),
    },
    {
      id: "follow-ups",
      name: "Follow-ups",
      icon: Activity,
      allowed: user.permissions.includes("follow_up:view"),
    },
    {
      id: "outcomes",
      name: "Outcomes",
      icon: BarChart3,
      allowed: user.permissions.includes("outcome:view"),
    },
    {
      id: "data-quality",
      name: "Data Quality",
      icon: ShieldAlert,
      allowed: user.permissions.includes("data_quality:view"),
    },
    {
      id: "pipeline",
      name: "Pipeline",
      icon: Columns3,
      allowed: user.permissions.includes("candidate_pipeline:view"),
    },
    {
      id: "interviews",
      name: "Interviews",
      icon: CalendarDays,
      allowed: user.permissions.includes("interview:view"),
    },
    {
      id: "placements",
      name: "Placements",
      icon: MapPinCheck,
      allowed: user.permissions.includes("placement:view"),
    },
    {
      id: "first-income",
      name: "First Income",
      icon: CircleDollarSign,
      allowed: user.permissions.includes("first_income:view"),
    },
    {
      id: "employer-submissions",
      name: "Employer Submissions",
      icon: Inbox,
      allowed: user.permissions.includes("employer_submission:view"),
    },
    {
      id: "employers",
      name: "Employers",
      icon: Building2,
      allowed: user.permissions.includes("organization:view"),
    },
    {
      id: "vacancies",
      name: "Vacancies",
      icon: BriefcaseBusiness,
      allowed: user.permissions.includes("vacancy:view"),
    },
    {
      id: "training",
      name: "Training",
      icon: GraduationCap,
      allowed: user.permissions.includes("training:view"),
    },
    {
      id: "participants",
      name: "Participants",
      icon: Users,
      allowed: user.permissions.includes("participant:view"),
    },
    {
      id: "security",
      name: "Account security",
      icon: ShieldCheck,
      allowed: true,
    },
    {
      id: "users",
      name: "Accounts",
      icon: Users,
      allowed: user.permissions.includes("user:manage"),
    },
    {
      id: "roles",
      name: "Roles",
      icon: KeyRound,
      allowed: user.permissions.includes("role:manage"),
    },
    {
      id: "intake-operations",
      name: "Integration operations",
      icon: Inbox,
      allowed: user.permissions.includes("integration_event:view"),
    },
    {
      id: "audit",
      name: "Audit history",
      icon: FileClock,
      allowed: user.permissions.includes("audit:view"),
    },
  ].filter((item) => item.allowed);
  const active = navigation.some((item) => item.id === view) ? view : "work";
  async function logout() {
    try {
      await api("/auth/logout", "POST");
      setRecord(null);
      setCreate(null);
      client.removeQueries();
      await me.refetch();
      return true;
    } catch (error) {
      setError(error instanceof Error ? error.message : "Sign-out failed.");
      return false;
    }
  }
  return (
    <main className="authenticated-shell min-h-screen pb-[calc(80px+env(safe-area-inset-bottom))] md:pb-0">
      <Header compact>
        <div className="flex min-w-0 flex-1 items-center justify-end gap-3">
          <GlobalSearch
            user={user}
            onOpen={(item) => {
              setView(
                item.entity_type === "PARTICIPANT"
                  ? "participants"
                  : item.entity_type === "CAMPAIGN"
                    ? "campaigns"
                    : item.entity_type === "PLACEMENT"
                      ? "placements"
                      : item.entity_type === "ORGANIZATION"
                        ? "employers"
                        : "vacancies",
              );
              setRecord(item);
              setCreate(null);
              setNavigationVersion((value) => value + 1);
              setError("");
            }}
          />
          <ProfileMenu
            user={user}
            workspace={selected?.name ?? "No assigned workspace"}
            onLogout={logout}
            onSecurity={() => {
              setView("security");
              setRecord(null);
              setCreate(null);
              setError("");
            }}
          />
        </div>
      </Header>
      <div className="grid min-h-[calc(100vh-70px)] grid-rows-[auto_1fr] md:grid-rows-1">
        <aside className="account-sidebar contents md:fixed md:inset-y-0 md:left-0 md:z-20 md:block md:w-[260px] md:overflow-y-auto md:p-4">
          <div className="mb-6 mt-2 hidden px-1 md:block">
            <h1
              aria-label="HAPPY Management Platform"
              className="text-xl font-bold text-white"
            >
              HAPPY
              <span className="mt-1 block text-xs font-medium">
                Management Platform
              </span>
            </h1>
            <p className="mt-2 text-xs capitalize">
              {env.environment} · v{env.releaseVersion}
            </p>
          </div>
          <div className="border-b border-border bg-white px-5 py-3 md:mb-5 md:rounded-md md:border md:border-white/15 md:bg-white/5 md:p-3">
            {user.workspaces.length > 1 ? (
              <label className="field-label flex-row items-center gap-3 md:flex-col md:items-stretch md:gap-2">
                Workspace
                <select
                  className="field max-w-48 md:max-w-none"
                  value={selected?.code ?? ""}
                  onChange={(event) => {
                    setRecord(null);
                    setCreate(null);
                    setWorkspace(event.target.value);
                  }}
                >
                  {user.workspaces.map((item) => (
                    <option key={item.code} value={item.code}>
                      {item.name}
                    </option>
                  ))}
                </select>
              </label>
            ) : (
              <p className="text-sm font-medium text-primary md:text-white">
                {selected?.name ?? "No assigned workspace"}
              </p>
            )}
          </div>
          <AccountNavigation
            items={navigation}
            active={active}
            workspace={selected?.code ?? ""}
            onNavigate={(id) => {
              setView(id);
              setRecord(null);
              setCreate(null);
              setNavigationVersion((value) => value + 1);
              setError("");
            }}
          />
        </aside>
        <section
          ref={content}
          tabIndex={-1}
          aria-label="Workspace content"
          className="min-w-0 px-5 pb-24 pt-7 focus:outline-none md:pb-7 lg:px-8"
        >
          {error && (
            <p role="alert" className="mb-4 text-sm text-red-700">
              {error}
            </p>
          )}
          {active === "tasks" && user.permissions.includes("task:view") && (
            <WorkWorkspace user={user} workspace={selected?.code ?? ""} />
          )}
          {active === "work" &&
            ![
              "DEMAND",
              "SUPPLY",
              "MATCHING",
              "MERL",
              "MARKETING",
              "MANAGEMENT",
            ].includes(selected?.code ?? "") && (
              <>
                <h2 className="text-xl font-semibold">{navigation[0].name}</h2>
                <div className="mt-6 flex min-h-48 flex-col items-center justify-center gap-3 border-y border-border text-muted">
                  <ClipboardList className="h-7 w-7" aria-hidden="true" />
                  <p className="text-sm">No assigned tasks</p>
                </div>
              </>
            )}
          {(["employers", "vacancies"].includes(active) ||
            (active === "work" && selected?.code === "DEMAND") ||
            (active === "dashboard" && selected?.code === "DEMAND") ||
            false) && (
            <DemandWorkspace
              key={active + selected?.code + navigationVersion}
              view={active}
              user={user}
              initialCreate={create === active}
              initialSelection={
                record && record.entity_type !== "PARTICIPANT"
                  ? {
                      kind:
                        record.entity_type === "ORGANIZATION"
                          ? "employers"
                          : "vacancies",
                      id: record.id,
                    }
                  : null
              }
            />
          )}
          {active === "employer-submissions" &&
            user.permissions.includes("employer_submission:view") && (
              <EmployerSubmissionWorkspace />
            )}
          {active === "training" &&
            user.permissions.includes("training:view") && (
              <TrainingWorkspace user={user} />
            )}
          {(active === "participants" ||
            (active === "work" && selected?.code === "SUPPLY") ||
            (active === "dashboard" && selected?.code === "SUPPLY")) &&
            (user.permissions.includes("participant:view") ? (
              <SupplyWorkspace
                key={active + selected?.code + navigationVersion}
                view={active}
                user={user}
                initialCreate={create === "participants"}
                initialIdentifier={
                  record?.entity_type === "PARTICIPANT" ? record.id : null
                }
              />
            ) : (
              <p role="alert" className="text-sm text-red-700">
                Participant access is not permitted. Contact an administrator.
              </p>
            ))}
          {(["pipeline", "interviews"].includes(active) ||
            (active === "work" && selected?.code === "MATCHING") ||
            (active === "dashboard" && selected?.code === "MATCHING")) &&
            (user.permissions.includes("candidate_pipeline:view") ? (
              <MatchingWorkspace
                key={active + selected?.code + navigationVersion}
                view={active}
                user={user}
              />
            ) : (
              <p role="alert" className="text-sm text-red-700">
                Matching access is not permitted. Contact an administrator.
              </p>
            ))}
          {["placements", "first-income"].includes(active) &&
            (user.permissions.includes("placement:view") ? (
              <PlacementWorkspace
                key={active + selected?.code + navigationVersion}
                view={active}
                user={user}
                initialIdentifier={
                  record?.entity_type === "PLACEMENT" ? record.id : null
                }
              />
            ) : (
              <p role="alert" className="text-sm text-red-700">
                Placement access is not permitted. Contact an administrator.
              </p>
            ))}
          {(["follow-ups", "outcomes", "data-quality"].includes(active) ||
            (active === "work" && selected?.code === "MERL") ||
            (active === "dashboard" && selected?.code === "MERL")) &&
            (user.permissions.includes("follow_up:view") ? (
              <MerlWorkspace
                key={active + selected?.code + navigationVersion}
                view={active}
                user={user}
              />
            ) : (
              <p role="alert" className="text-sm text-red-700">
                M&amp;E access is not permitted. Contact an administrator.
              </p>
            ))}
          {(["requests", "campaigns", "impact-stories"].includes(active) ||
            (active === "work" && selected?.code === "MARKETING") ||
            (active === "dashboard" && selected?.code === "MARKETING")) &&
            (user.permissions.includes("marketing_request:view") ||
            user.permissions.includes("campaign:view") ? (
              <MarketingWorkspace
                key={active + selected?.code + navigationVersion}
                view={active}
                user={user}
                initialIdentifier={
                  record?.entity_type === "CAMPAIGN" ? record.id : null
                }
              />
            ) : (
              <p role="alert" className="text-sm text-red-700">
                Marketing access is not permitted. Contact an administrator.
              </p>
            ))}
          {(["performance", "reports"].includes(active) ||
            (active === "work" && selected?.code === "MANAGEMENT") ||
            (active === "dashboard" && selected?.code === "MANAGEMENT")) &&
            (user.permissions.includes("report:view") ? (
              <ReportingWorkspace
                key={active + selected?.code + navigationVersion}
                view={active}
                user={user}
              />
            ) : (
              <p role="alert" className="text-sm text-red-700">
                Reporting access is not permitted. Contact an administrator.
              </p>
            ))}
          {active === "security" && (
            <SecuritySettings user={user} onRefresh={() => me.refetch()} />
          )}
          {active === "intake-operations" &&
            user.permissions.includes("integration_event:view") && (
              <IntakeOperations user={user} />
            )}
          {["users", "roles", "audit"].includes(active) && (
            <IamAdmin key={active} view={active} user={user} />
          )}
        </section>
      </div>
      <QuickAdd
        user={user}
        workspace={selected?.code ?? ""}
        onDesktop={() => content.current?.focus({ preventScroll: true })}
        onCreate={(kind) => {
          setView(kind);
          setRecord(null);
          setCreate(kind);
          setNavigationVersion((value) => value + 1);
          setError("");
        }}
      />
    </main>
  );
}
