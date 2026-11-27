import React, { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import {
  AlertTriangle,
  CheckCircle2,
  Copy,
  Key,
  Plus,
  RefreshCw,
  RotateCcw,
  Server,
  Shield,
  Trash2,
  Zap,
} from "lucide-react";
import { integrationsApi } from "@/api/integrations";
import { useToast } from "@/context/ToastContext";

export const IntegrationDashboardPage: React.FC<{
  initialTab?: "overview" | "connections" | "webhooks" | "outbox" | "dlq";
}> = ({ initialTab = "overview" }) => {
  const queryClient = useQueryClient();
  const { toast } = useToast();

  const [activeTab, setActiveTab] = useState<"overview" | "connections" | "webhooks" | "outbox" | "dlq">(initialTab);

  React.useEffect(() => {
    setActiveTab(initialTab);
  }, [initialTab]);
  const [isCreateModalOpen, setIsCreateModalOpen] = useState(false);
  const [secretModalData, setSecretModalData] = useState<{ secret: string; name: string } | null>(null);
  const [selectedPayload, setSelectedPayload] = useState<{ title: string; data: any } | null>(null);

  // Connection form state
  const [name, setName] = useState("");
  const [slug, setSlug] = useState("");
  const [integrationType, setIntegrationType] = useState("TELEMATICS");
  const [adapterType, setAdapterType] = useState("GENERIC");
  const [baseUrl, setBaseUrl] = useState("");
  const [apiKey, setApiKey] = useState("");

  // Queries
  const { data: metrics, refetch: refetchMetrics } = useQuery({
    queryKey: ["integration-metrics"],
    queryFn: integrationsApi.getDashboardMetrics,
    refetchInterval: 10000,
  });

  const { data: connections, refetch: refetchConns } = useQuery({
    queryKey: ["integration-connections"],
    queryFn: integrationsApi.listConnections,
  });

  const { data: webhooks, refetch: refetchWebhooks } = useQuery({
    queryKey: ["integration-webhooks"],
    queryFn: () => integrationsApi.listWebhooks({ limit: 50 }),
    enabled: activeTab === "webhooks" || activeTab === "overview",
  });

  const { data: outboxEvents, refetch: refetchOutbox } = useQuery({
    queryKey: ["integration-outbox"],
    queryFn: () => integrationsApi.listOutbox({ limit: 50 }),
    enabled: activeTab === "outbox" || activeTab === "overview",
  });

  const { data: dlqEvents, refetch: refetchDLQ } = useQuery({
    queryKey: ["integration-dlq"],
    queryFn: () => integrationsApi.listDLQ("webhook", 50),
    enabled: activeTab === "dlq",
  });

  // Mutations
  const createConnMutation = useMutation({
    mutationFn: integrationsApi.createConnection,
    onSuccess: (newConn) => {
      toast.success("Integration Created", `Connection '${newConn.name}' registered successfully.`);
      setIsCreateModalOpen(false);
      resetForm();
      queryClient.invalidateQueries({ queryKey: ["integration-connections"] });
      queryClient.invalidateQueries({ queryKey: ["integration-metrics"] });
    },
    onError: (err: any) => {
      toast.error("Registration Failed", err.response?.data?.detail || err.message);
    },
  });

  const deleteConnMutation = useMutation({
    mutationFn: integrationsApi.deleteConnection,
    onSuccess: () => {
      toast.info("Connection Deleted", "Integration removed.");
      queryClient.invalidateQueries({ queryKey: ["integration-connections"] });
      queryClient.invalidateQueries({ queryKey: ["integration-metrics"] });
    },
  });

  const regenSecretMutation = useMutation({
    mutationFn: (id: string) => integrationsApi.regenerateSecret(id),
    onSuccess: (res, id) => {
      const conn = connections?.find((c) => c.id === id);
      setSecretModalData({ secret: res.webhook_secret, name: conn?.name || "Integration" });
      queryClient.invalidateQueries({ queryKey: ["integration-connections"] });
    },
  });

  const replayEventMutation = useMutation({
    mutationFn: ({ source, id }: { source: "webhook" | "outbox"; id: string }) =>
      integrationsApi.replayEvent(source, id),
    onSuccess: () => {
      toast.success("Replay Triggered", "Event queued for immediate reprocessing.");
      queryClient.invalidateQueries({ queryKey: ["integration-dlq"] });
      queryClient.invalidateQueries({ queryKey: ["integration-metrics"] });
      queryClient.invalidateQueries({ queryKey: ["integration-webhooks"] });
      queryClient.invalidateQueries({ queryKey: ["integration-outbox"] });
    },
    onError: (err: any) => {
      toast.error("Replay Failed", err.response?.data?.detail || err.message);
    },
  });

  const sweepOutboxMutation = useMutation({
    mutationFn: integrationsApi.triggerOutboxProcess,
    onSuccess: (res) => {
      toast.info("Outbox Sweep Complete", `Processed: ${res.processed}, Published: ${res.published}`);
      queryClient.invalidateQueries({ queryKey: ["integration-outbox"] });
      queryClient.invalidateQueries({ queryKey: ["integration-metrics"] });
    },
  });

  const sweepWebhooksMutation = useMutation({
    mutationFn: integrationsApi.triggerWebhooksProcess,
    onSuccess: (res) => {
      toast.info("Webhook Sweep Complete", `Processed: ${res.processed}, Succeeded: ${res.succeeded}`);
      queryClient.invalidateQueries({ queryKey: ["integration-webhooks"] });
      queryClient.invalidateQueries({ queryKey: ["integration-metrics"] });
    },
  });

  const recoverHungMutation = useMutation({
    mutationFn: integrationsApi.triggerRecoverHung,
    onSuccess: (res) => {
      toast.success(
        "Hung Worker Recovery",
        `Recovered: ${res.recovered_outbox_events} outbox, ${res.recovered_webhook_events} webhooks`
      );
      queryClient.invalidateQueries({ queryKey: ["integration-metrics"] });
    },
  });

  const resetForm = () => {
    setName("");
    setSlug("");
    setIntegrationType("TELEMATICS");
    setAdapterType("GENERIC");
    setBaseUrl("");
    setApiKey("");
  };

  const handleCopy = (text: string, label: string) => {
    navigator.clipboard.writeText(text);
    toast.info("Copied!", `${label} copied to clipboard.`);
  };

  return (
    <div className="space-y-6">
      {/* Header Bar */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 border-b border-outline-variant pb-5">
        <div>
          <div className="flex items-center gap-3">
            <h1 className="text-2xl font-bold tracking-tight text-on-surface">
              Integration Reliability Engine
            </h1>
            <span
              className={`inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-semibold ${
                metrics?.system_health === "HEALTHY"
                  ? "bg-emerald-100 text-emerald-800"
                  : metrics?.system_health === "DEGRADED"
                  ? "bg-amber-100 text-amber-800"
                  : "bg-rose-100 text-rose-800"
              }`}
            >
              <span
                className={`w-2 h-2 rounded-full ${
                  metrics?.system_health === "HEALTHY"
                    ? "bg-success-container0 animate-pulse"
                    : metrics?.system_health === "DEGRADED"
                    ? "bg-warning-container0"
                    : "bg-critical-container0"
                }`}
              />
              System: {metrics?.system_health || "INITIALIZING"}
            </span>
          </div>
          <p className="mt-1 text-sm text-on-surface-muted">
            Durable webhook ingestion, transporter adapters, transactional outbox & dead-letter queue.
          </p>
        </div>

        {/* Global Action Sweeps */}
        <div className="flex flex-wrap items-center gap-2">
          <button
            onClick={() => {
              refetchMetrics();
              refetchConns();
              refetchWebhooks();
              refetchOutbox();
              refetchDLQ();
            }}
            className="inline-flex items-center gap-1.5 px-3 py-2 text-xs font-medium text-on-surface bg-surface-card border border-outline-strong rounded-lg shadow-sm hover:bg-surface-container-low"
          >
            <RefreshCw className="w-3.5 h-3.5" />
            Refresh
          </button>
          <button
            onClick={() => sweepWebhooksMutation.mutate()}
            disabled={sweepWebhooksMutation.isPending}
            className="inline-flex items-center gap-1.5 px-3 py-2 text-xs font-medium text-indigo-700 bg-indigo-50 border border-indigo-200 rounded-lg hover:bg-indigo-100"
          >
            <Zap className="w-3.5 h-3.5" />
            Process Webhooks
          </button>
          <button
            onClick={() => sweepOutboxMutation.mutate()}
            disabled={sweepOutboxMutation.isPending}
            className="inline-flex items-center gap-1.5 px-3 py-2 text-xs font-medium text-primary bg-primary-container border border-burnt-orange/30 rounded-lg hover:bg-primary-container"
          >
            <Server className="w-3.5 h-3.5" />
            Publish Outbox
          </button>
          <button
            onClick={() => recoverHungMutation.mutate()}
            disabled={recoverHungMutation.isPending}
            className="inline-flex items-center gap-1.5 px-3 py-2 text-xs font-medium text-on-warning-container bg-warning-container border border-amber-200 rounded-lg hover:bg-amber-100"
          >
            <RotateCcw className="w-3.5 h-3.5" />
            Recover Hung
          </button>
          <button
            onClick={() => setIsCreateModalOpen(true)}
            className="inline-flex items-center gap-1.5 px-4 py-2 text-xs font-semibold text-white bg-indigo-600 rounded-lg shadow-sm hover:bg-indigo-700"
          >
            <Plus className="w-4 h-4" />
            New Connection
          </button>
        </div>
      </div>

      {/* KPI Cards */}
      <div className="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-6 gap-3">
        <div className="bg-surface-card p-4 rounded-xl border border-outline-variant shadow-sm">
          <p className="text-xs font-medium text-on-surface-muted">Total Webhooks</p>
          <p className="text-xl font-bold text-on-surface mt-1">{metrics?.total_webhooks ?? 0}</p>
          <p className="text-[11px] text-success font-medium mt-1">
            {metrics?.successful_webhooks ?? 0} Succeeded
          </p>
        </div>
        <div className="bg-surface-card p-4 rounded-xl border border-outline-variant shadow-sm">
          <p className="text-xs font-medium text-on-surface-muted">Pending Inbound</p>
          <p className="text-xl font-bold text-on-surface mt-1">{metrics?.pending_webhooks ?? 0}</p>
          <p className="text-[11px] text-warning font-medium mt-1">
            {metrics?.retry_webhooks ?? 0} In Retry
          </p>
        </div>
        <div className="bg-surface-card p-4 rounded-xl border border-outline-variant shadow-sm">
          <p className="text-xs font-medium text-on-surface-muted">Outbox Events</p>
          <p className="text-xl font-bold text-on-surface mt-1">{metrics?.total_outbox ?? 0}</p>
          <p className="text-[11px] text-primary font-medium mt-1">
            {metrics?.published_outbox ?? 0} Published
          </p>
        </div>
        <div className="bg-surface-card p-4 rounded-xl border border-outline-variant shadow-sm">
          <p className="text-xs font-medium text-on-surface-muted">Outbox Pending</p>
          <p className="text-xl font-bold text-on-surface mt-1">{metrics?.pending_outbox ?? 0}</p>
          <p className="text-[11px] text-on-surface-muted mt-1">Ready for dispatcher</p>
        </div>
        <div className="bg-surface-card p-4 rounded-xl border border-outline-variant shadow-sm">
          <p className="text-xs font-medium text-on-surface-muted">Dead-Letter Queue</p>
          <p className={`text-xl font-bold mt-1 ${((metrics?.dlq_count ?? 0) > 0) ? "text-critical" : "text-on-surface"}`}>
            {metrics?.dlq_count ?? 0}
          </p>
          <p className="text-[11px] text-rose-500 font-medium mt-1">Requires Replay</p>
        </div>
        <div className="bg-surface-card p-4 rounded-xl border border-outline-variant shadow-sm">
          <p className="text-xs font-medium text-on-surface-muted">Connections</p>
          <p className="text-xl font-bold text-on-surface mt-1">{metrics?.connections_count ?? 0}</p>
          <p className="text-[11px] text-success font-medium mt-1">
            {metrics?.healthy_connections_count ?? 0} Healthy
          </p>
        </div>
      </div>

      {/* Tabs */}
      <div className="border-b border-outline-variant">
        <nav className="flex space-x-6">
          {[
            { id: "overview", label: "Overview & Errors" },
            { id: "connections", label: `Connections (${connections?.length ?? 0})` },
            { id: "webhooks", label: "Inbound Webhooks" },
            { id: "outbox", label: "Transactional Outbox" },
            { id: "dlq", label: `Dead-Letter Queue (${metrics?.dlq_count ?? 0})`, badgeColor: (metrics?.dlq_count ?? 0) > 0 ? "bg-critical-container0 text-white" : "" },
          ].map((tab) => (
            <button
              key={tab.id}
              onClick={() => setActiveTab(tab.id as any)}
              className={`py-3 px-1 border-b-2 font-medium text-sm inline-flex items-center gap-2 ${
                activeTab === tab.id
                  ? "border-indigo-600 text-indigo-600"
                  : "border-transparent text-on-surface-muted hover:text-on-surface hover:border-outline-strong"
              }`}
            >
              {tab.label}
              {tab.badgeColor && (
                <span className={`px-1.5 py-0.5 rounded-full text-[10px] font-bold ${tab.badgeColor}`}>
                  {metrics?.dlq_count}
                </span>
              )}
            </button>
          ))}
        </nav>
      </div>

      {/* TAB 1: OVERVIEW */}
      {activeTab === "overview" && (
        <div className="space-y-6">
          {/* Architecture Resilience Callout */}
          <div className="bg-gradient-to-r from-slate-900 via-indigo-950 to-slate-900 text-white p-5 rounded-2xl shadow">
            <div className="flex items-start gap-4">
              <div className="p-3 bg-indigo-500/20 rounded-xl border border-indigo-400/30">
                <Shield className="w-6 h-6 text-indigo-400" />
              </div>
              <div>
                <h3 className="font-bold text-base text-white">Guaranteed At-Least-Once Delivery & Idempotency</h3>
                <p className="text-xs text-on-surface-muted mt-1 leading-relaxed max-w-4xl">
                  CargoPulse utilizes transactional outbox patterns in PostgreSQL (<code className="text-indigo-300">FOR UPDATE SKIP LOCKED</code>)
                  preventing dual-write hazards. Inbound telematics & ERP webhooks are cryptographically authenticated via constant-time HMAC-SHA256,
                  deduplicated by external event identity, and normalized before executing idempotent business side effects.
                </p>
              </div>
            </div>
          </div>

          {/* Recent Errors Table */}
          <div className="bg-surface-card rounded-xl border border-outline-variant shadow-sm overflow-hidden">
            <div className="px-5 py-4 border-b border-outline-variant flex items-center justify-between">
              <h3 className="font-semibold text-sm text-on-surface">Recent Integration Errors</h3>
              <span className="text-xs text-on-surface-muted">Last 10 failures</span>
            </div>
            {metrics?.recent_errors && metrics.recent_errors.length > 0 ? (
              <div className="divide-y divide-outline-variant">
                {metrics.recent_errors.map((err) => (
                  <div key={err.id} className="p-4 flex items-start justify-between gap-4 hover:bg-surface-container-low">
                    <div className="space-y-1">
                      <div className="flex items-center gap-2">
                        <span className="px-2 py-0.5 bg-critical-container text-on-critical-container text-xs font-semibold rounded">
                          {err.provider.toUpperCase()}
                        </span>
                        <span className="text-xs font-mono text-on-surface-muted">{err.id}</span>
                        {err.is_dead_letter && (
                          <span className="px-2 py-0.5 bg-rose-600 text-white text-[10px] font-bold rounded">
                            DEAD LETTER
                          </span>
                        )}
                      </div>
                      <p className="text-xs font-medium text-on-surface">{err.error_message}</p>
                      <p className="text-[11px] text-on-surface-subtle">
                        Type: {err.error_type} • Retries: {err.retry_count} • {new Date(err.timestamp).toLocaleString()}
                      </p>
                    </div>
                    {err.is_dead_letter && (
                      <button
                        onClick={() => replayEventMutation.mutate({ source: "webhook", id: err.id })}
                        className="px-3 py-1.5 text-xs font-medium text-indigo-700 bg-indigo-50 border border-indigo-200 rounded hover:bg-indigo-100"
                      >
                        Replay
                      </button>
                    )}
                  </div>
                ))}
              </div>
            ) : (
              <div className="p-8 text-center text-on-surface-muted text-sm">
                <CheckCircle2 className="w-8 h-8 text-emerald-500 mx-auto mb-2" />
                No recent integration errors. System running cleanly.
              </div>
            )}
          </div>
        </div>
      )}

      {/* TAB 2: CONNECTIONS */}
      {activeTab === "connections" && (
        <div className="space-y-4">
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            {connections?.map((conn) => (
              <div key={conn.id} className="bg-surface-card p-5 rounded-xl border border-outline-variant shadow-sm space-y-4">
                <div className="flex items-start justify-between">
                  <div>
                    <h4 className="font-bold text-on-surface text-base">{conn.name}</h4>
                    <span className="text-xs font-mono text-on-surface-muted">{conn.slug}</span>
                  </div>
                  <span
                    className={`px-2.5 py-1 text-xs font-semibold rounded-full ${
                      conn.health_status === "HEALTHY"
                        ? "bg-emerald-100 text-emerald-800"
                        : conn.health_status === "DEGRADED"
                        ? "bg-amber-100 text-amber-800"
                        : "bg-rose-100 text-rose-800"
                    }`}
                  >
                    {conn.health_status}
                  </span>
                </div>

                <div className="space-y-1.5 text-xs text-on-surface-muted bg-surface-container-low p-3 rounded-lg border border-outline-variant">
                  <div className="flex justify-between">
                    <span className="text-on-surface-subtle">Adapter:</span>
                    <span className="font-semibold text-on-surface">{conn.adapter_type}</span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-on-surface-subtle">Type:</span>
                    <span className="font-semibold text-on-surface">{conn.integration_type}</span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-on-surface-subtle">Secret Preview:</span>
                    <span className="font-mono text-on-surface">{conn.webhook_secret_preview || "N/A"}</span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-on-surface-subtle">Total Ingested:</span>
                    <span className="font-semibold text-on-surface">{conn.stats?.total_received ?? 0}</span>
                  </div>
                </div>

                {/* Webhook URL with copy */}
                <div>
                  <label className="text-[11px] font-semibold text-on-surface-muted block mb-1">
                    Incoming Webhook Endpoint
                  </label>
                  <div className="flex items-center gap-1.5 bg-surface-container p-2 rounded border border-outline-variant text-xs font-mono text-on-surface">
                    <span className="truncate flex-1">{conn.webhook_url}</span>
                    <button
                      onClick={() => handleCopy(`${window.location.origin}${conn.webhook_url}`, "Webhook URL")}
                      className="p-1 hover:bg-surface-container rounded text-on-surface-muted"
                      title="Copy URL"
                    >
                      <Copy className="w-3.5 h-3.5" />
                    </button>
                  </div>
                </div>

                {/* Actions */}
                <div className="pt-2 border-t border-outline-variant flex items-center justify-between text-xs">
                  <button
                    onClick={() => regenSecretMutation.mutate(conn.id)}
                    className="text-indigo-600 font-medium hover:underline flex items-center gap-1"
                  >
                    <Key className="w-3.5 h-3.5" />
                    Regen Secret
                  </button>
                  <button
                    onClick={() => {
                      if (confirm(`Delete connection '${conn.name}'?`)) {
                        deleteConnMutation.mutate(conn.id);
                      }
                    }}
                    className="text-critical font-medium hover:underline flex items-center gap-1"
                  >
                    <Trash2 className="w-3.5 h-3.5" />
                    Remove
                  </button>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* TAB 3: INBOUND WEBHOOKS */}
      {activeTab === "webhooks" && (
        <div className="bg-surface-card rounded-xl border border-outline-variant shadow-sm overflow-hidden">
          <div className="p-4 border-b border-outline-variant flex items-center justify-between">
            <h3 className="font-semibold text-sm text-on-surface">Ingested Webhook Events</h3>
            <span className="text-xs text-on-surface-muted">Showing last 50 events</span>
          </div>
          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs">
              <thead className="bg-surface-container-low text-on-surface-muted font-semibold border-b border-outline-variant">
                <tr>
                  <th className="py-3 px-4">Time (UTC)</th>
                  <th className="py-3 px-4">Provider</th>
                  <th className="py-3 px-4">Event Type</th>
                  <th className="py-3 px-4">External Event ID</th>
                  <th className="py-3 px-4">Status</th>
                  <th className="py-3 px-4">Retries</th>
                  <th className="py-3 px-4 text-right">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-outline-variant">
                {webhooks?.map((evt) => (
                  <tr key={evt.id} className="hover:bg-surface-container-low">
                    <td className="py-3 px-4 text-on-surface-muted">{new Date(evt.created_at).toLocaleString()}</td>
                    <td className="py-3 px-4 font-semibold text-on-surface">{evt.provider.toUpperCase()}</td>
                    <td className="py-3 px-4 text-on-surface">{evt.event_name}</td>
                    <td className="py-3 px-4 font-mono text-on-surface-muted">{evt.external_event_id || "N/A"}</td>
                    <td className="py-3 px-4">
                      <span
                        className={`px-2 py-0.5 rounded text-[11px] font-semibold ${
                          evt.status === "PROCESSED"
                            ? "bg-emerald-100 text-emerald-800"
                            : evt.status === "RECEIVED"
                            ? "bg-primary-container text-on-primary-container"
                            : evt.is_dead_letter
                            ? "bg-rose-600 text-white"
                            : "bg-amber-100 text-amber-800"
                        }`}
                      >
                        {evt.is_dead_letter ? "DEAD LETTER" : evt.status}
                      </span>
                    </td>
                    <td className="py-3 px-4 text-on-surface-muted">{evt.retry_count} / {evt.max_retries}</td>
                    <td className="py-3 px-4 text-right">
                      <button
                        onClick={() => setSelectedPayload({ title: `Webhook ${evt.id}`, data: evt.normalized_payload || evt.payload })}
                        className="text-indigo-600 hover:underline font-medium"
                      >
                        Payload
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* TAB 4: OUTBOX */}
      {activeTab === "outbox" && (
        <div className="bg-surface-card rounded-xl border border-outline-variant shadow-sm overflow-hidden">
          <div className="p-4 border-b border-outline-variant flex items-center justify-between">
            <h3 className="font-semibold text-sm text-on-surface">Transactional Outbox Queue</h3>
            <span className="text-xs text-on-surface-muted">Atomic business change event distribution</span>
          </div>
          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs">
              <thead className="bg-surface-container-low text-on-surface-muted font-semibold border-b border-outline-variant">
                <tr>
                  <th className="py-3 px-4">Created</th>
                  <th className="py-3 px-4">Aggregate</th>
                  <th className="py-3 px-4">Event Type</th>
                  <th className="py-3 px-4">Status</th>
                  <th className="py-3 px-4">Destination</th>
                  <th className="py-3 px-4">Retries</th>
                  <th className="py-3 px-4 text-right">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-outline-variant">
                {outboxEvents?.map((ob) => (
                  <tr key={ob.id} className="hover:bg-surface-container-low">
                    <td className="py-3 px-4 text-on-surface-muted">{new Date(ob.created_at).toLocaleString()}</td>
                    <td className="py-3 px-4 font-semibold text-on-surface">
                      {ob.aggregate_type}: <span className="font-mono text-on-surface-muted text-[11px]">{ob.aggregate_id.slice(0, 8)}...</span>
                    </td>
                    <td className="py-3 px-4 text-on-surface">{ob.event_type}</td>
                    <td className="py-3 px-4">
                      <span
                        className={`px-2 py-0.5 rounded text-[11px] font-semibold ${
                          ob.status === "PUBLISHED"
                            ? "bg-emerald-100 text-emerald-800"
                            : ob.status === "PENDING"
                            ? "bg-primary-container text-on-primary-container"
                            : ob.status === "DEAD_LETTER" || ob.is_dead_letter
                            ? "bg-rose-600 text-white"
                            : "bg-amber-100 text-amber-800"
                        }`}
                      >
                        {ob.status}
                      </span>
                    </td>
                    <td className="py-3 px-4 text-on-surface-muted font-mono text-[11px] truncate max-w-xs">{ob.destination || "Internal Bus"}</td>
                    <td className="py-3 px-4 text-on-surface-muted">{ob.retry_count} / {ob.max_retries}</td>
                    <td className="py-3 px-4 text-right">
                      <button
                        onClick={() => setSelectedPayload({ title: `Outbox ${ob.id}`, data: ob.payload })}
                        className="text-indigo-600 hover:underline font-medium"
                      >
                        Payload
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* TAB 5: DLQ */}
      {activeTab === "dlq" && (
        <div className="space-y-4">
          <div className="bg-critical-container border border-rose-200 p-4 rounded-xl flex items-center justify-between text-xs text-rose-800">
            <div className="flex items-center gap-2">
              <AlertTriangle className="w-5 h-5 text-critical" />
              <span>
                Dead-Letter Queue holds events that failed after retry exhaustion or permanent validation errors.
                Operators can review the root cause and execute manual replays with a single click.
              </span>
            </div>
            {dlqEvents && dlqEvents.length > 0 && (
              <button
                onClick={() => {
                  const ids = dlqEvents.map((e) => e.id);
                  integrationsApi.replayBatch("webhook", ids).then(() => {
                    toast.success("Batch Replay Triggered", `Replaying ${ids.length} events.`);
                    refetchDLQ();
                    refetchMetrics();
                  });
                }}
                className="px-3 py-1.5 bg-rose-600 hover:bg-rose-700 text-white font-semibold rounded shadow-sm"
              >
                Replay All ({dlqEvents.length})
              </button>
            )}
          </div>

          <div className="bg-surface-card rounded-xl border border-outline-variant shadow-sm overflow-hidden">
            {dlqEvents && dlqEvents.length > 0 ? (
              <div className="divide-y divide-outline-variant">
                {dlqEvents.map((item) => (
                  <div key={item.id} className="p-4 flex items-start justify-between gap-4 hover:bg-surface-container-low">
                    <div className="space-y-1 text-xs">
                      <div className="flex items-center gap-2">
                        <span className="font-bold text-on-surface">{item.provider?.toUpperCase() || "OUTBOX"}</span>
                        <span className="font-mono text-on-surface-subtle">{item.id}</span>
                        <span className="px-2 py-0.5 bg-rose-100 text-rose-800 font-bold rounded">
                          Failed after {item.retry_count} retries
                        </span>
                        {item.replay_count > 0 && (
                          <span className="px-2 py-0.5 bg-indigo-100 text-indigo-800 font-semibold rounded">
                            Replayed {item.replay_count}x
                          </span>
                        )}
                      </div>
                      <p className="text-on-critical-container font-medium">{item.error_message}</p>
                      <p className="text-on-surface-subtle">
                        Received: {new Date(item.created_at).toLocaleString()} • Last Attempt: {item.last_attempt_at ? new Date(item.last_attempt_at).toLocaleString() : "N/A"}
                      </p>
                    </div>
                    <div className="flex items-center gap-2">
                      <button
                        onClick={() => setSelectedPayload({ title: `DLQ ${item.id}`, data: item.payload })}
                        className="px-3 py-1.5 text-xs text-on-surface bg-surface-card border border-outline-strong rounded hover:bg-surface-container-low"
                      >
                        Inspect
                      </button>
                      <button
                        onClick={() => replayEventMutation.mutate({ source: "webhook", id: item.id })}
                        disabled={replayEventMutation.isPending}
                        className="px-3 py-1.5 text-xs font-semibold text-white bg-indigo-600 hover:bg-indigo-700 rounded shadow-sm"
                      >
                        Replay
                      </button>
                    </div>
                  </div>
                ))}
              </div>
            ) : (
              <div className="p-8 text-center text-on-surface-muted text-sm">
                <CheckCircle2 className="w-8 h-8 text-emerald-500 mx-auto mb-2" />
                Dead-Letter Queue is empty. No failed events pending review.
              </div>
            )}
          </div>
        </div>
      )}

      {/* CREATE MODAL */}
      {isCreateModalOpen && (
        <div className="fixed inset-0 z-50 bg-black/50 flex items-center justify-center p-4">
          <div className="bg-surface-card rounded-2xl max-w-lg w-full p-6 shadow-xl space-y-4">
            <h3 className="text-lg font-bold text-on-surface">Register New Integration</h3>
            <div className="space-y-3 text-xs">
              <div>
                <label className="font-semibold text-on-surface block mb-1">Integration Name *</label>
                <input
                  type="text"
                  value={name}
                  onChange={(e) => setName(e.target.value)}
                  placeholder="e.g. Samsara Production Fleet"
                  className="w-full px-3 py-2 border border-outline-strong rounded-lg text-sm"
                />
              </div>
              <div>
                <label className="font-semibold text-on-surface block mb-1">Slug (URL friendly)</label>
                <input
                  type="text"
                  value={slug}
                  onChange={(e) => setSlug(e.target.value)}
                  placeholder="e.g. samsara-fleet-prod"
                  className="w-full px-3 py-2 border border-outline-strong rounded-lg text-sm"
                />
              </div>
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="font-semibold text-on-surface block mb-1">Integration Type</label>
                  <select
                    value={integrationType}
                    onChange={(e) => setIntegrationType(e.target.value)}
                    className="w-full px-3 py-2 border border-outline-strong rounded-lg text-sm"
                  >
                    <option value="TELEMATICS">Telematics</option>
                    <option value="ERP">ERP</option>
                    <option value="TMS">TMS</option>
                    <option value="WMS">WMS</option>
                    <option value="FASTAG">FASTag</option>
                    <option value="CUSTOM_WEBHOOK">Custom Webhook</option>
                  </select>
                </div>
                <div>
                  <label className="font-semibold text-on-surface block mb-1">Adapter</label>
                  <select
                    value={adapterType}
                    onChange={(e) => setAdapterType(e.target.value)}
                    className="w-full px-3 py-2 border border-outline-strong rounded-lg text-sm"
                  >
                    <option value="GENERIC">Generic CargoPulse</option>
                    <option value="SAMSARA">Samsara Telematics</option>
                    <option value="INTANGLES">Intangles IoT</option>
                    <option value="CUSTOM_ERP">Custom ERP (SAP/Oracle)</option>
                  </select>
                </div>
              </div>
              <div>
                <label className="font-semibold text-on-surface block mb-1">Base URL (optional)</label>
                <input
                  type="url"
                  value={baseUrl}
                  onChange={(e) => setBaseUrl(e.target.value)}
                  placeholder="https://api.samsara.com/v1"
                  className="w-full px-3 py-2 border border-outline-strong rounded-lg text-sm"
                />
              </div>
              <div>
                <label className="font-semibold text-on-surface block mb-1">API Key / Token (optional)</label>
                <input
                  type="password"
                  value={apiKey}
                  onChange={(e) => setApiKey(e.target.value)}
                  placeholder="External API Key header"
                  className="w-full px-3 py-2 border border-outline-strong rounded-lg text-sm"
                />
              </div>
            </div>

            <div className="flex justify-end gap-2 pt-3 border-t border-outline-variant">
              <button
                onClick={() => setIsCreateModalOpen(false)}
                className="px-4 py-2 text-xs font-medium text-on-surface bg-surface-container rounded-lg hover:bg-surface-container"
              >
                Cancel
              </button>
              <button
                onClick={() => {
                  if (!name) {
                    toast.error("Validation Error", "Name is required.");
                    return;
                  }
                  createConnMutation.mutate({
                    name,
                    slug: slug || undefined,
                    integration_type: integrationType,
                    adapter_type: adapterType,
                    base_url: baseUrl || undefined,
                    api_key: apiKey || undefined,
                  });
                }}
                disabled={createConnMutation.isPending}
                className="px-4 py-2 text-xs font-semibold text-white bg-indigo-600 rounded-lg hover:bg-indigo-700"
              >
                Create Connection
              </button>
            </div>
          </div>
        </div>
      )}

      {/* SECRET REVEAL MODAL */}
      {secretModalData && (
        <div className="fixed inset-0 z-50 bg-black/50 flex items-center justify-center p-4">
          <div className="bg-surface-card rounded-2xl max-w-md w-full p-6 shadow-xl space-y-4">
            <div className="flex items-center gap-2 text-warning">
              <Key className="w-5 h-5" />
              <h3 className="text-base font-bold text-on-surface">Webhook Secret Generated</h3>
            </div>
            <p className="text-xs text-on-surface-muted">
              New secret for <strong>{secretModalData.name}</strong>. Save this secret in your secure vault.
              It will not be shown in full again:
            </p>
            <div className="p-3 bg-surface-container border border-outline-strong rounded font-mono text-xs break-all select-all text-on-surface">
              {secretModalData.secret}
            </div>
            <div className="flex justify-end gap-2 pt-2">
              <button
                onClick={() => handleCopy(secretModalData.secret, "Webhook Secret")}
                className="px-3 py-2 text-xs font-medium text-on-surface bg-surface-container rounded hover:bg-surface-container"
              >
                Copy Secret
              </button>
              <button
                onClick={() => setSecretModalData(null)}
                className="px-4 py-2 text-xs font-semibold text-white bg-indigo-600 rounded hover:bg-indigo-700"
              >
                Done
              </button>
            </div>
          </div>
        </div>
      )}

      {/* PAYLOAD INSPECTOR MODAL */}
      {selectedPayload && (
        <div className="fixed inset-0 z-50 bg-black/50 flex items-center justify-center p-4">
          <div className="bg-surface-card rounded-2xl max-w-2xl w-full p-6 shadow-xl space-y-4">
            <div className="flex items-center justify-between border-b border-outline-variant pb-3">
              <h3 className="text-base font-bold text-on-surface">{selectedPayload.title}</h3>
              <button
                onClick={() => setSelectedPayload(null)}
                className="text-on-surface-subtle hover:text-on-surface-muted font-bold"
              >
                ✕
              </button>
            </div>
            <div className="p-3 bg-surface text-emerald-400 rounded-lg font-mono text-xs max-h-96 overflow-y-auto">
              <pre>{JSON.stringify(selectedPayload.data, null, 2)}</pre>
            </div>
            <div className="flex justify-end">
              <button
                onClick={() => setSelectedPayload(null)}
                className="px-4 py-2 text-xs font-semibold text-on-surface bg-surface-container rounded-lg hover:bg-surface-container"
              >
                Close
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
