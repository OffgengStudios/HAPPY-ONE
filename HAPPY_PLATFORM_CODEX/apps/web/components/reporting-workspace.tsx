"use client";

import { useQuery, useQueryClient } from "@tanstack/react-query";
import { Clock3, Download, RefreshCw, Save, TrendingUp } from "lucide-react";
import { FormEvent, useMemo, useState } from "react";
import { api, download, downloadGet, Me } from "@/lib/api";
import {
  DrilldownRow,
  Kpi,
  ReportExportJob,
  ReportingDashboard,
  ReportTarget,
} from "@/lib/reporting";

const today = new Date();
const initialFrom = `${today.getFullYear()}-01-01`;
const initialTo = today.toISOString().slice(0, 10);

function shown(value: string | number | boolean | null | undefined) {
  if (value === null || value === undefined || value === "")
    return "Not available";
  return typeof value === "boolean" ? (value ? "Yes" : "No") : String(value);
}

function Metric({ row, open }: { row: Kpi; open: () => void }) {
  return (
    <button
      type="button"
      className="metric-card min-h-36 text-left transition-transform hover:-translate-y-0.5 disabled:cursor-default disabled:hover:translate-y-0"
      disabled={!row.has_drilldown}
      onClick={open}
    >
      <span className="block text-xs font-semibold text-muted">{row.code}</span>
      <strong className="mt-3 block text-2xl font-semibold">
        {row.available ? shown(row.value) : "Unavailable"}
      </strong>
      <span className="mt-1 block text-sm">{row.label}</span>
      {row.target !== null && (
        <span className="mt-3 block text-xs text-muted">
          Target {row.target} | Gap {row.gap ?? "0"} | Forecast{" "}
          {row.forecast ?? "Not set"}
        </span>
      )}
      {!row.available && (
        <span className="mt-3 block text-xs text-muted">
          {row.unavailable_reason}
        </span>
      )}
    </button>
  );
}

export function ReportingWorkspace({ view, user }: { view: string; user: Me }) {
  const client = useQueryClient();
  const [dateFrom, setDateFrom] = useState(initialFrom);
  const [dateTo, setDateTo] = useState(initialTo);
  const [selected, setSelected] = useState<string | null>(null);
  const [message, setMessage] = useState("");
  const [retrying, setRetrying] = useState<string | null>(null);
  const period = `date_from=${dateFrom}&date_to=${dateTo}`;
  const section = view === "work" ? "dashboard" : view;
  const dashboard = useQuery({
    queryKey: ["reporting", "dashboard", dateFrom, dateTo],
    queryFn: () => api<ReportingDashboard>(`/reports/dashboard?${period}`),
    enabled: section === "dashboard",
  });
  const kpis = useQuery({
    queryKey: ["reporting", "kpis", dateFrom, dateTo],
    queryFn: () => api<{ items: Kpi[] }>(`/reports/kpis?${period}`),
    enabled: ["performance", "reports"].includes(section),
  });
  const quality = useQuery({
    queryKey: ["reporting", "quality"],
    queryFn: () =>
      api<{ items: { status: string; severity: string; count: number }[] }>(
        "/reports/data-quality",
      ),
    enabled: section === "reports",
  });
  const targets = useQuery({
    queryKey: ["reporting", "targets"],
    queryFn: () => api<{ items: ReportTarget[] }>("/reports/targets"),
    enabled: section === "reports",
  });
  const exportJobs = useQuery({
    queryKey: ["reporting", "export-jobs"],
    queryFn: () => api<{ items: ReportExportJob[] }>("/reports/export-jobs"),
    enabled: section === "reports",
    refetchInterval: (query) =>
      query.state.data?.items.some((row) =>
        ["PENDING", "RUNNING"].includes(row.status),
      )
        ? 1000
        : false,
  });
  const drilldown = useQuery({
    queryKey: ["reporting", "drilldown", selected, dateFrom, dateTo],
    queryFn: () =>
      api<{ items: DrilldownRow[] }>(
        `/reports/kpis/${selected}/drilldown?${period}`,
      ),
    enabled: Boolean(selected),
  });
  const metrics =
    section === "dashboard" ? dashboard.data?.metrics : kpis.data?.items;
  const activeMetric = metrics?.find((row) => row.code === selected);
  const columns = useMemo(
    () =>
      Array.from(
        new Set(
          (drilldown.data?.items ?? []).flatMap((row) => Object.keys(row)),
        ),
      ),
    [drilldown.data],
  );
  const pending = dashboard.isPending || kpis.isPending || quality.isPending;
  const error = dashboard.error || kpis.error || quality.error || targets.error;

  async function exportMetric(code: string) {
    setMessage("");
    try {
      await download("/reports/export", {
        kpi_code: code,
        date_from: dateFrom,
        date_to: dateTo,
        format: "CSV",
      });
      setMessage("Report downloaded.");
    } catch (reason) {
      setMessage(reason instanceof Error ? reason.message : "Export failed.");
    }
  }

  async function queueExport(code: string) {
    setMessage("");
    try {
      await api("/reports/export-jobs", "POST", {
        kpi_code: code,
        date_from: dateFrom,
        date_to: dateTo,
        format: "CSV",
      });
      await exportJobs.refetch();
      setMessage("Full export requested.");
    } catch (reason) {
      setMessage(
        reason instanceof Error ? reason.message : "Export request failed.",
      );
    }
  }

  async function retryExport(
    job: ReportExportJob,
    event: FormEvent<HTMLFormElement>,
  ) {
    event.preventDefault();
    const values = new FormData(event.currentTarget);
    setRetrying(job.id);
    setMessage("");
    try {
      await api(`/reports/export-jobs/${job.id}/retry`, "POST", {
        version: job.version,
        reason: values.get("reason"),
        privacy_acknowledged: values.get("privacy_acknowledged") === "on",
      });
      await exportJobs.refetch();
      setMessage("Export retry requested.");
    } catch (reason) {
      setMessage(
        reason instanceof Error ? reason.message : "Export retry failed.",
      );
    } finally {
      setRetrying(null);
    }
  }

  async function createTarget(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const values = new FormData(event.currentTarget);
    setMessage("");
    try {
      await api("/reports/targets", "POST", {
        kpi_code: values.get("kpi_code"),
        period_start: dateFrom,
        period_end: dateTo,
        target_value: values.get("target_value"),
        forecast_value: values.get("forecast_value") || null,
        notes: values.get("notes") || null,
      });
      event.currentTarget.reset();
      await client.invalidateQueries({ queryKey: ["reporting"] });
      setMessage("Global target saved.");
    } catch (reason) {
      setMessage(
        reason instanceof Error ? reason.message : "Target could not be saved.",
      );
    }
  }

  return (
    <div className="min-w-0">
      <div className="mb-6 flex flex-wrap items-end justify-between gap-4">
        <div>
          <p className="text-xs font-semibold uppercase text-primary">
            Management
          </p>
          <h2 className="mt-1 text-xl font-semibold">
            {section === "dashboard"
              ? "Performance overview"
              : section === "performance"
                ? "KPI performance"
                : "Reports & targets"}
          </h2>
        </div>
        <div className="flex flex-wrap items-end gap-2">
          <label className="field-label">
            From
            <input
              className="field"
              type="date"
              value={dateFrom}
              max={dateTo}
              onChange={(event) => {
                setDateFrom(event.target.value);
                setSelected(null);
              }}
            />
          </label>
          <label className="field-label">
            To
            <input
              className="field"
              type="date"
              value={dateTo}
              min={dateFrom}
              onChange={(event) => {
                setDateTo(event.target.value);
                setSelected(null);
              }}
            />
          </label>
          <button
            className="icon-button"
            title="Refresh"
            aria-label="Refresh"
            onClick={() =>
              void client.invalidateQueries({ queryKey: ["reporting"] })
            }
          >
            <RefreshCw className="h-4 w-4" />
          </button>
        </div>
      </div>
      {pending && (
        <p role="status" className="py-6 text-sm text-muted">
          Loading reports...
        </p>
      )}
      {error && (
        <p role="alert" className="py-4 text-sm text-red-700">
          {error.message}
        </p>
      )}
      {message && (
        <p role="status" className="mb-4 text-sm text-primary">
          {message}
        </p>
      )}

      {section === "dashboard" && dashboard.data && (
        <>
          <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
            {Object.entries(dashboard.data.attention).map(([key, value]) => (
              <div
                key={key}
                className="border-l-4 border-primary bg-white px-4 py-3 shadow-sm"
              >
                <strong className="text-xl">{value}</strong>
                <span className="mt-1 block text-xs text-muted">
                  {key.replaceAll("_", " ")}
                </span>
              </div>
            ))}
          </div>
          <div className="mt-7 grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
            {dashboard.data.metrics.map((row) => (
              <Metric
                key={row.code}
                row={row}
                open={() => setSelected(row.code)}
              />
            ))}
          </div>
          <section className="mt-8 border-t border-border pt-6">
            <h3 className="flex items-center gap-2 text-base font-semibold">
              <TrendingUp className="h-4 w-4" />
              Confirmed placement trend
            </h3>
            <div className="mt-4 flex min-h-28 items-end gap-3 overflow-x-auto border-b border-border pb-1">
              {dashboard.data.placement_trend.length ? (
                dashboard.data.placement_trend.map((row) => (
                  <div
                    key={row.month}
                    className="flex min-w-16 flex-col items-center gap-2 text-xs text-muted"
                  >
                    <span>{row.confirmed_placements}</span>
                    <span
                      className="w-8 bg-primary"
                      style={{
                        height: `${Math.max(8, row.confirmed_placements * 16)}px`,
                      }}
                    />
                    <span>{row.month}</span>
                  </div>
                ))
              ) : (
                <p className="self-center text-sm text-muted">
                  No confirmed placements in this period.
                </p>
              )}
            </div>
          </section>
        </>
      )}

      {section === "performance" && kpis.data && (
        <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
          {kpis.data.items.map((row) => (
            <Metric
              key={row.code}
              row={row}
              open={() => setSelected(row.code)}
            />
          ))}
        </div>
      )}

      {section === "reports" && (
        <div className="space-y-8">
          <section>
            <h3 className="text-base font-semibold">Exportable reports</h3>
            <div className="mt-3 divide-y divide-border border-y border-border">
              {(kpis.data?.items ?? [])
                .filter((row) => row.available)
                .map((row) => (
                  <div
                    key={row.code}
                    className="data-row flex flex-wrap items-center justify-between gap-3"
                  >
                    <button
                      className="text-left"
                      onClick={() => setSelected(row.code)}
                    >
                      <strong className="block text-sm">{row.label}</strong>
                      <span className="text-xs text-muted">
                        {row.code} | {shown(row.value)}
                      </span>
                    </button>
                    <div className="flex gap-1">
                      <button
                        className="icon-button"
                        title={`Download bounded ${row.label}`}
                        aria-label={`Download bounded ${row.label}`}
                        onClick={() => void exportMetric(row.code)}
                      >
                        <Download className="h-4 w-4" />
                      </button>
                      <button
                        className="icon-button"
                        title={`Prepare full ${row.label}`}
                        aria-label={`Prepare full ${row.label}`}
                        onClick={() => void queueExport(row.code)}
                      >
                        <Clock3 className="h-4 w-4" />
                      </button>
                    </div>
                  </div>
                ))}
            </div>
          </section>
          <section>
            <h3 className="text-base font-semibold">Prepared exports</h3>
            <div className="mt-3 divide-y divide-border border-y border-border">
              {(exportJobs.data?.items ?? []).map((job) => (
                <div
                  key={job.id}
                  className="data-row flex flex-wrap items-center justify-between gap-3"
                >
                  <span>
                    <strong className="block text-sm">{job.kpi_code}</strong>
                    <span className="text-xs text-muted">
                      {job.period_start} to {job.period_end} ·{" "}
                      {job.status.toLowerCase()}
                      {job.row_count !== null ? ` · ${job.row_count} rows` : ""}
                    </span>
                    {job.error_message && (
                      <span className="block text-xs text-red-700">
                        {job.error_message}
                      </span>
                    )}
                  </span>
                  {job.status === "FAILED" &&
                    user.permissions.includes("report:export") && (
                      <form
                        onSubmit={(event) => void retryExport(job, event)}
                        className="flex flex-wrap items-end gap-2"
                      >
                        <label className="text-xs">
                          Retry reason
                          <input
                            className="field block"
                            name="reason"
                            required
                            maxLength={5000}
                          />
                        </label>
                        {job.include_sensitive && (
                          <label className="text-xs">
                            <input
                              type="checkbox"
                              name="privacy_acknowledged"
                              required
                            />{" "}
                            I acknowledge this export contains sensitive
                            information.
                          </label>
                        )}
                        <button
                          className="secondary-button"
                          disabled={retrying === job.id}
                          type="submit"
                        >
                          {retrying === job.id
                            ? "Requesting retry…"
                            : "Retry export"}
                        </button>
                      </form>
                    )}
                  {job.status === "SUCCEEDED" && (
                    <button
                      className="icon-button"
                      title={`Download prepared ${job.kpi_code}`}
                      aria-label={`Download prepared ${job.kpi_code}`}
                      onClick={() =>
                        void downloadGet(
                          `/reports/export-jobs/${job.id}/download`,
                        )
                      }
                    >
                      <Download className="h-4 w-4" />
                    </button>
                  )}
                </div>
              ))}
              {!exportJobs.isPending && !exportJobs.data?.items.length && (
                <p className="py-4 text-sm text-muted">No prepared exports</p>
              )}
            </div>
          </section>
          <section>
            <h3 className="text-base font-semibold">Data-quality summary</h3>
            <div className="mt-3 grid gap-3 sm:grid-cols-3">
              {(quality.data?.items ?? []).map((row) => (
                <div
                  key={`${row.status}-${row.severity}`}
                  className="border-l-4 border-primary bg-white px-4 py-3"
                >
                  <strong>{row.count}</strong>
                  <span className="ml-2 text-sm text-muted">
                    {row.severity} | {row.status}
                  </span>
                </div>
              ))}
              {!quality.data?.items.length && (
                <p className="text-sm text-muted">
                  No open data-quality summary records.
                </p>
              )}
            </div>
          </section>
          {user.permissions.includes("report_target:manage") && (
            <section className="border-t border-border pt-6">
              <h3 className="text-base font-semibold">
                Configure global target
              </h3>
              <form
                className="mt-4 grid gap-3 md:grid-cols-2 xl:grid-cols-5"
                onSubmit={(event) => void createTarget(event)}
              >
                <label className="field-label">
                  KPI
                  <select className="field" name="kpi_code" required>
                    {(kpis.data?.items ?? []).map((row) => (
                      <option key={row.code} value={row.code}>
                        {row.code} | {row.label}
                      </option>
                    ))}
                  </select>
                </label>
                <label className="field-label">
                  Target
                  <input
                    className="field"
                    name="target_value"
                    type="number"
                    min="0"
                    step="0.01"
                    required
                  />
                </label>
                <label className="field-label">
                  Forecast
                  <input
                    className="field"
                    name="forecast_value"
                    type="number"
                    min="0"
                    step="0.01"
                  />
                </label>
                <label className="field-label">
                  Notes
                  <input className="field" name="notes" maxLength={5000} />
                </label>
                <button className="command primary self-end" type="submit">
                  <Save className="h-4 w-4" />
                  Save target
                </button>
              </form>
              <div className="mt-4 text-xs text-muted">
                {targets.data?.items.length ?? 0} configured global targets
              </div>
            </section>
          )}
        </div>
      )}

      {selected && (
        <section className="mt-8 border-t border-border pt-6">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <div>
              <p className="text-xs font-semibold text-primary">{selected}</p>
              <h3 className="text-base font-semibold">
                {activeMetric?.label ?? "KPI drilldown"}
              </h3>
            </div>
            <button className="command" onClick={() => setSelected(null)}>
              Close
            </button>
          </div>
          {drilldown.isPending && (
            <p role="status" className="py-5 text-sm text-muted">
              Loading drilldown...
            </p>
          )}
          {drilldown.error && (
            <p role="alert" className="py-4 text-sm text-red-700">
              {drilldown.error.message}
            </p>
          )}
          {drilldown.data && (
            <div className="mt-4 overflow-x-auto border-y border-border">
              <table className="w-full min-w-[680px] text-left text-sm">
                <thead>
                  <tr>
                    {columns.map((column) => (
                      <th
                        key={column}
                        className="px-3 py-3 text-xs font-semibold uppercase text-muted"
                      >
                        {column.replaceAll("_", " ")}
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {drilldown.data.items.map((row, index) => (
                    <tr
                      key={String(row.id ?? index)}
                      className="border-t border-border"
                    >
                      {columns.map((column) => (
                        <td key={column} className="px-3 py-3">
                          {shown(row[column])}
                        </td>
                      ))}
                    </tr>
                  ))}
                </tbody>
              </table>
              {!drilldown.data.items.length && (
                <p className="py-8 text-center text-sm text-muted">
                  No records for this KPI and period.
                </p>
              )}
            </div>
          )}
        </section>
      )}
    </div>
  );
}
