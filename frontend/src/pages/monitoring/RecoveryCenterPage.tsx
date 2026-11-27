import React, { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { pickupMonitoringApi, RecoveryCase } from "@/api/pickupMonitoring";
import { PageHeader } from "@/components/common/PageHeader";
import { MetricCard } from "@/components/common/MetricCard";
import { StatusBadge } from "@/components/common/StatusBadge";
import { EmptyState } from "@/components/common/EmptyState";
import { ErrorState } from "@/components/common/ErrorState";
import { LoadingState } from "@/components/common/LoadingState";
import { ConfirmationDialog } from "@/components/common/ConfirmationDialog";
import { Button } from "@/components/ui/button";
import { useToast } from "@/context/ToastContext";
import { RefreshCw, CheckCircle2, AlertTriangle, ShieldAlert, Bot } from "lucide-react";

const RECOVERY_STEPS = [
  { key: "booked", label: "1. Booked", desc: "Primary commitment" },
  { key: "missed", label: "2. Missed", desc: "Pickup window passed" },
  { key: "detected", label: "3. Detected", desc: "Accountability scan" },
  { key: "exception", label: "4. Exception", desc: "Incident logged" },
  { key: "ai_audit", label: "5. AI Audit", desc: "Telemetry & log check" },
  { key: "evaluated", label: "6. Evaluated", desc: "Backups scored" },
  { key: "approval", label: "7. Approval", desc: "Manager sign-off" },
  { key: "reassigned", label: "8. Reassigned", desc: "Replacement booked" },
];

export const RecoveryCenterPage: React.FC = () => {
  const queryClient = useQueryClient();
  const { addToast } = useToast();
  const [statusFilter, setStatusFilter] = useState<string>("");
  const [selectedCase, setSelectedCase] = useState<RecoveryCase | null>(null);
  const [selectedTransporterId, setSelectedTransporterId] = useState<string>("");
  const [approvalNotes, setApprovalNotes] = useState<string>("");
  const [confirmOpen, setConfirmOpen] = useState<boolean>(false);

  const { data, isLoading, isError, refetch } = useQuery({
    queryKey: ["recovery-cases", statusFilter],
    queryFn: () =>
      pickupMonitoringApi.listRecoveryCases({
        page: 1,
        page_size: 25,
        status: statusFilter || undefined,
      }),
  });

  const cases = data?.items || [];
  const activeCase = selectedCase || cases[0] || null;

  const approveMutation = useMutation({
    mutationFn: ({
      caseId,
      transporterId,
      notes,
    }: {
      caseId: string;
      transporterId: string;
      notes?: string;
    }) =>
      pickupMonitoringApi.approveRecovery(caseId, {
        replacement_transporter_id: transporterId,
        notes,
      }),
    onSuccess: (updated) => {
      addToast({
        title: "Replacement Approved",
        description: `Case ${updated.case_number} approved and replacement dispatch initiated.`,
        type: "success",
      });
      setConfirmOpen(false);
      setApprovalNotes("");
      setSelectedCase(updated);
      queryClient.invalidateQueries({ queryKey: ["recovery-cases"] });
    },
    onError: (err: any) => {
      addToast({
        title: "Approval Failed",
        description: err?.message || "Unable to approve recovery case.",
        type: "error",
      });
    },
  });

  const scanMutation = useMutation({
    mutationFn: () => pickupMonitoringApi.scanCommitments(),
    onSuccess: (res) => {
      addToast({
        title: "Accountability Scan Complete",
        description: `Scanned ${res.scanned_count} commitments; ${res.recovery_cases_opened} recovery cases opened.`,
        type: "info",
      });
      queryClient.invalidateQueries({ queryKey: ["recovery-cases"] });
    },
    onError: (err: any) => {
      addToast({
        title: "Scan Failed",
        description: err?.message || "Failed to trigger pickup accountability scan.",
        type: "error",
      });
    },
  });

  const pendingApprovalCount = cases.filter(
    (c) => c.status === "PROPOSED" || c.approval_status === "PENDING"
  ).length;
  const resolvedCount = cases.filter((c) => c.status === "RESOLVED").length;

  return (
    <div className="space-y-6">
      <PageHeader
        title="Missed Pickup Recovery Center"
        subtitle="Accountable recovery workflow for breached pickup SLAs, AI-evaluated replacement transporters, and manager sign-off."
        breadcrumbs={[
          { label: "Console", href: "/overview" },
          { label: "Monitoring", href: "/pickup-monitoring" },
          { label: "Recovery Center" },
        ]}
        actions={
          <div className="flex items-center gap-2">
            <select
              value={statusFilter}
              onChange={(e) => setStatusFilter(e.target.value)}
              className="font-label text-label-md text-on-surface bg-surface-card border border-outline-strong rounded-sm px-3 py-1.5 outline-none focus:border-burnt-orange"
            >
              <option value="">All Recovery Cases</option>
              <option value="OPEN">Open</option>
              <option value="PROPOSED">Proposed (Needs Approval)</option>
              <option value="APPROVED">Approved</option>
              <option value="RESOLVED">Resolved</option>
              <option value="FAILED">Failed</option>
            </select>
            <Button
              variant="outline"
              size="sm"
              onClick={() => refetch()}
              className="gap-1.5"
            >
              <RefreshCw className="h-4 w-4" />
              Refresh
            </Button>
            <Button
              variant="default"
              size="sm"
              onClick={() => scanMutation.mutate()}
              disabled={scanMutation.isPending}
              className="gap-1.5"
            >
              <Bot className="h-4 w-4" />
              {scanMutation.isPending ? "Scanning..." : "Run Accountability Scan"}
            </Button>
          </div>
        }
      />

      {/* Summary KPIs */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        <MetricCard
          title="Total Recovery Cases"
          value={data?.total ?? cases.length}
          loading={isLoading}
          icon={<AlertTriangle className="h-4 w-4" />}
          accentColor="orange"
        />
        <MetricCard
          title="Awaiting Manager Approval"
          value={pendingApprovalCount}
          loading={isLoading}
          icon={<ShieldAlert className="h-4 w-4" />}
          accentColor="amber"
        />
        <MetricCard
          title="Resolved Recoveries"
          value={resolvedCount}
          loading={isLoading}
          icon={<CheckCircle2 className="h-4 w-4" />}
          accentColor="teal"
        />
        <MetricCard
          title="AI-Generated Proposals"
          value={cases.filter((c) => c.ai_generated).length}
          loading={isLoading}
          icon={<Bot className="h-4 w-4" />}
          accentColor="blue"
        />
      </div>

      {isLoading ? (
        <LoadingState type="card" />
      ) : isError ? (
        <ErrorState
          title="Unable to load recovery cases"
          message="Failed to fetch recovery cases from the backend."
          onRetry={() => refetch()}
        />
      ) : cases.length === 0 ? (
        <EmptyState
          title="No active missed pickup recovery cases"
          description="All pickup commitments are currently within SLA or already resolved."
          actionLabel="Run Accountability Scan"
          onAction={() => scanMutation.mutate()}
        />
      ) : (
        <div className="grid grid-cols-1 lg:grid-cols-12 gap-5">
          {/* Case Queue List */}
          <div className="lg:col-span-4 bg-surface-card border border-outline-variant rounded-DEFAULT overflow-hidden flex flex-col">
            <div className="px-4 py-3 border-b border-outline-variant bg-surface-container-low flex items-center justify-between">
              <h2 className="font-title text-title-md text-on-surface">Recovery Queue</h2>
              <span className="font-mono text-mono-sm text-on-surface-muted tabular-nums">
                {cases.length} cases
              </span>
            </div>
            <div className="divide-y divide-outline-variant max-h-[600px] overflow-y-auto">
              {cases.map((rc) => {
                const isSelected = activeCase?.id === rc.id;
                return (
                  <button
                    key={rc.id}
                    type="button"
                    onClick={() => {
                      setSelectedCase(rc);
                      setSelectedTransporterId(
                        rc.replacement_transporter_id ||
                          rc.alternatives_data?.[0]?.transporter_id ||
                          ""
                      );
                    }}
                    className={`w-full text-left p-4 transition-colors duration-state-change ${
                      isSelected
                        ? "bg-primary-container/60 border-l-4 border-l-primary"
                        : "hover:bg-surface-container-low"
                    }`}
                  >
                    <div className="flex items-center justify-between gap-2 mb-1">
                      <span className="font-mono text-mono-sm font-semibold text-primary">
                        {rc.case_number}
                      </span>
                      <StatusBadge status={rc.status} size="sm" />
                    </div>
                    <p className="font-body text-body-sm text-on-surface line-clamp-2 mb-2">
                      {rc.proposed_solution}
                    </p>
                    <div className="flex items-center justify-between font-label text-label-sm text-on-surface-subtle tabular-nums">
                      <span>{rc.strategy.replace(/_/g, " ")}</span>
                      <span>
                        Impact: ₹{Number(rc.estimated_cost_impact || 0).toLocaleString("en-IN")}
                      </span>
                    </div>
                  </button>
                );
              })}
            </div>
          </div>

          {/* Active Recovery Case Workbench */}
          {activeCase && (
            <div className="lg:col-span-8 space-y-5">
              {/* 8-Step Accountability Recovery Timeline */}
              <section className="bg-surface-card border border-outline-variant rounded-DEFAULT p-5">
                <div className="flex flex-wrap items-center justify-between gap-3 mb-4">
                  <div>
                    <div className="flex items-center gap-2.5">
                      <h2 className="font-headline text-headline-md text-on-surface">
                        {activeCase.case_number}
                      </h2>
                      <StatusBadge status={activeCase.status} size="sm" />
                    </div>
                    <p className="font-body text-body-sm text-on-surface-muted mt-0.5">
                      Strategy: {activeCase.strategy.replace(/_/g, " ")} · Approval:{" "}
                      {activeCase.approval_status}
                    </p>
                  </div>
                  <div className="text-right tabular-nums">
                    <span className="font-label text-label-sm text-on-surface-subtle block">
                      Estimated Cost Impact
                    </span>
                    <span className="font-headline text-headline-md text-on-surface">
                      ₹{Number(activeCase.estimated_cost_impact || 0).toLocaleString("en-IN")}
                    </span>
                  </div>
                </div>

                <div className="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-8 gap-2">
                  {RECOVERY_STEPS.map((step, idx) => {
                    const isCritical = idx === 1 || idx === 2;
                    const isAI = idx === 4 || idx === 5;
                    const isDone =
                      activeCase.status === "RESOLVED" ||
                      activeCase.status === "APPROVED" ||
                      idx < 6;
                    return (
                      <div
                        key={step.key}
                        className={`p-2.5 rounded-sm border border-outline-variant ${
                          isCritical
                            ? "bg-critical-container"
                            : isAI
                            ? "bg-primary-container"
                            : isDone
                            ? "bg-surface-container-low"
                            : "bg-surface-card"
                        }`}
                      >
                        <span
                          className={`font-label text-label-sm block ${
                            isCritical
                              ? "text-critical"
                              : isAI
                              ? "text-on-primary-container"
                              : "text-on-surface"
                          }`}
                        >
                          {step.label}
                        </span>
                        <span className="font-body text-body-sm text-on-surface-muted block truncate">
                          {step.desc}
                        </span>
                      </div>
                    );
                  })}
                </div>
              </section>

              {/* Proposed Solution & Alternative Transporter Comparison */}
              <section className="bg-surface-card border border-outline-variant rounded-DEFAULT p-5 space-y-4">
                <h3 className="font-title text-title-md text-on-surface">
                  AI Recommendation &amp; Alternative Transporters
                </h3>
                <p className="font-body text-body-md text-on-surface-muted bg-surface-container-low p-3.5 rounded-sm border border-outline-variant">
                  {activeCase.proposed_solution}
                </p>

                {activeCase.alternatives_data && activeCase.alternatives_data.length > 0 ? (
                  <div className="space-y-2.5">
                    {activeCase.alternatives_data.map((alt) => {
                      const chosen =
                        (selectedTransporterId ||
                          activeCase.replacement_transporter_id ||
                          activeCase.alternatives_data?.[0]?.transporter_id) ===
                        alt.transporter_id;
                      return (
                        <label
                          key={alt.transporter_id}
                          className={`flex items-center justify-between gap-4 p-3.5 rounded-sm border cursor-pointer transition-colors duration-state-change ${
                            chosen
                              ? "bg-primary-container/50 border-burnt-orange"
                              : "bg-surface-card border-outline-variant hover:bg-surface-container-low"
                          }`}
                        >
                          <div className="flex items-start gap-3">
                            <input
                              type="radio"
                              name="replacementTransporter"
                              checked={chosen}
                              onChange={() => setSelectedTransporterId(alt.transporter_id)}
                              className="mt-1 text-primary focus:ring-burnt-orange"
                            />
                            <div>
                              <p className="font-label text-label-lg text-on-surface">
                                {alt.transporter_name}
                              </p>
                              <p className="font-body text-body-sm text-on-surface-muted">
                                {alt.fit_reason}
                              </p>
                            </div>
                          </div>

                          <div className="text-right shrink-0 tabular-nums">
                            <span className="inline-block px-2 py-0.5 rounded-full bg-success-container text-on-success-container font-label text-label-sm mb-1">
                              {alt.match_score}% Fit · {alt.reliability_score}% SLA
                            </span>
                            <p className="font-mono text-mono-sm text-on-surface">
                              Est. ₹{Number(alt.estimated_cost || 0).toLocaleString("en-IN")}
                            </p>
                          </div>
                        </label>
                      );
                    })}
                  </div>
                ) : (
                  <p className="font-body text-body-sm text-on-surface-subtle">
                    No pre-scored alternative transporters attached to this case yet.
                  </p>
                )}

                {activeCase.status !== "RESOLVED" && activeCase.status !== "APPROVED" && (
                  <div className="pt-3 border-t border-outline-variant flex flex-col sm:flex-row sm:items-center justify-between gap-3">
                    <input
                      type="text"
                      value={approvalNotes}
                      onChange={(e) => setApprovalNotes(e.target.value)}
                      placeholder="Optional manager approval notes..."
                      className="flex-1 px-3 py-2 rounded-sm bg-surface-card border border-outline-strong font-body text-body-sm text-on-surface focus:outline-none focus:border-burnt-orange"
                    />
                    <Button
                      variant="default"
                      onClick={() => setConfirmOpen(true)}
                      disabled={
                        !(
                          selectedTransporterId ||
                          activeCase.replacement_transporter_id ||
                          activeCase.alternatives_data?.[0]?.transporter_id
                        ) || approveMutation.isPending
                      }
                    >
                      Approve Replacement Dispatch
                    </Button>
                  </div>
                )}
              </section>
            </div>
          )}
        </div>
      )}

      <ConfirmationDialog
        isOpen={confirmOpen}
        onClose={() => setConfirmOpen(false)}
        onConfirm={() => {
          if (!activeCase) return;
          const tId =
            selectedTransporterId ||
            activeCase.replacement_transporter_id ||
            activeCase.alternatives_data?.[0]?.transporter_id;
          if (!tId) return;
          approveMutation.mutate({
            caseId: activeCase.id,
            transporterId: tId,
            notes: approvalNotes || undefined,
          });
        }}
        title="Approve Replacement Transporter?"
        description={`Confirm replacement dispatch for recovery case ${activeCase?.case_number || ""}. This action is logged to the immutable audit trail.`}
        confirmLabel="Approve & Dispatch"
        isLoading={approveMutation.isPending}
      />
    </div>
  );
};
