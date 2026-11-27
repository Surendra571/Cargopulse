import React, { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import {
  Clock,
  AlertTriangle,
  CheckCircle2,
  Truck,
  RotateCw,
  ShieldAlert,
  ArrowRight,
  UserCheck,
  Building2,
  Calendar,
  Sparkles,
  Zap,
} from "lucide-react";
import {
  pickupMonitoringApi,
  PickupCommitment,
  RecoveryCase,
  SimulateScenarioResponse,
} from "@/api/pickupMonitoring";
import { PageHeader } from "@/components/common/PageHeader";
import { DataTable, ColumnDef } from "@/components/common/DataTable";
import { StatusBadge } from "@/components/common/StatusBadge";
import { MetricCard } from "@/components/common/MetricCard";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Card } from "@/components/ui/card";
import { ConfirmationDialog } from "@/components/common/ConfirmationDialog";
import { useToast } from "@/context/ToastContext";

const STATUS_TABS = [
  { label: "All Commitments", value: "ALL" },
  { label: "Pending", value: "PENDING" },
  { label: "Reminder Sent (30m)", value: "REMINDER_SENT" },
  { label: "At Risk (10m)", value: "AT_RISK" },
  { label: "Arrived at Dock", value: "ARRIVED" },
  { label: "Loading (Started)", value: "STARTED" },
  { label: "Completed", value: "COMPLETED" },
  { label: "Missed / Breached", value: "MISSED" },
];

export const PickupMonitoringPage: React.FC = () => {
  const queryClient = useQueryClient();
  const { toast } = useToast();

  const [activeTab, setActiveTab] = useState<"commitments" | "recovery">("commitments");
  const [statusFilter, setStatusFilter] = useState("ALL");
  const [page, setPage] = useState(1);
  const [pageSize] = useState(10);

  // Arrival Dialog State
  const [arrivalModalOpen, setArrivalModalOpen] = useState(false);
  const [selectedCommitment, setSelectedCommitment] = useState<PickupCommitment | null>(null);
  const [dockNumber, setDockNumber] = useState("");
  const [arrivalNotes, setArrivalNotes] = useState("");

  // Start Loading Dialog State
  const [startModalOpen, setStartModalOpen] = useState(false);
  const [bayNumber, setBayNumber] = useState("");

  // Complete Dialog State
  const [completeModalOpen, setCompleteModalOpen] = useState(false);
  const [bolNumber, setBolNumber] = useState("");
  const [sealNumber, setSealNumber] = useState("");
  const [loadedWeight, setLoadedWeight] = useState("");

  // Fail Dialog State
  const [failModalOpen, setFailModalOpen] = useState(false);
  const [failureReason, setFailureReason] = useState("");
  const [penaltyAmount, setPenaltyAmount] = useState("");

  // Recovery Approval State
  const [approveRecoveryModalOpen, setApproveRecoveryModalOpen] = useState(false);
  const [selectedRecoveryCase, setSelectedRecoveryCase] = useState<RecoveryCase | null>(null);
  const [selectedReplacementTransporterId, setSelectedReplacementTransporterId] = useState("");

  // Demo Simulation Modal State
  const [simModalOpen, setSimModalOpen] = useState(false);
  const [simResult, setSimResult] = useState<SimulateScenarioResponse | null>(null);

  // Commitments query
  const { data: commitmentsData, isLoading: isLoadingCommitments } = useQuery({
    queryKey: ["pickup-commitments", page, pageSize, statusFilter],
    queryFn: () =>
      pickupMonitoringApi.listCommitments({
        page,
        page_size: pageSize,
        status: statusFilter !== "ALL" ? statusFilter : undefined,
      }),
    refetchInterval: 15000,
  });

  // Recovery cases query
  const { data: recoveryData } = useQuery({
    queryKey: ["recovery-cases"],
    queryFn: () => pickupMonitoringApi.listRecoveryCases({ page: 1, page_size: 20 }),
    refetchInterval: 15000,
  });

  // SLA Scan mutation
  const scanMutation = useMutation({
    mutationFn: () => pickupMonitoringApi.scanCommitments(),
    onSuccess: (data) => {
      toast.success(
        "SLA Scan Complete",
        `Scanned: ${data.scanned_count} | Reminders: ${data.reminders_sent} | At Risk: ${data.at_risk_flagged} | Missed: ${data.missed_detected}`
      );
      queryClient.invalidateQueries({ queryKey: ["pickup-commitments"] });
      queryClient.invalidateQueries({ queryKey: ["recovery-cases"] });
      queryClient.invalidateQueries({ queryKey: ["exceptions"] });
    },
    onError: (err: any) => {
      toast.error("Scan Failed", err.response?.data?.detail || "Could not complete background SLA scan");
    },
  });

  // Action mutations
  const reportArrivalMutation = useMutation({
    mutationFn: () =>
      pickupMonitoringApi.reportArrival(selectedCommitment!.id, {
        dock_number: dockNumber || undefined,
        notes: arrivalNotes || undefined,
      }),
    onSuccess: () => {
      toast.success("Arrival Confirmed", "Vehicle arrival at origin dock recorded.");
      setArrivalModalOpen(false);
      queryClient.invalidateQueries({ queryKey: ["pickup-commitments"] });
    },
    onError: (err: any) => {
      toast.error("Arrival Failed", err.response?.data?.detail || "Could not report arrival");
    },
  });

  const startPickupMutation = useMutation({
    mutationFn: () =>
      pickupMonitoringApi.startPickup(selectedCommitment!.id, {
        bay_number: bayNumber || undefined,
      }),
    onSuccess: () => {
      toast.success("Loading Started", "Pickup loading progress initiated.");
      setStartModalOpen(false);
      queryClient.invalidateQueries({ queryKey: ["pickup-commitments"] });
    },
    onError: (err: any) => {
      toast.error("Action Failed", err.response?.data?.detail || "Could not start pickup");
    },
  });

  const completePickupMutation = useMutation({
    mutationFn: () =>
      pickupMonitoringApi.completePickup(selectedCommitment!.id, {
        bill_of_lading_number: bolNumber || undefined,
        seal_number: sealNumber || undefined,
        loaded_weight_kg: loadedWeight ? parseFloat(loadedWeight) : undefined,
      }),
    onSuccess: () => {
      toast.success("Pickup Completed", "Consignment securely loaded and dispatched.");
      setCompleteModalOpen(false);
      queryClient.invalidateQueries({ queryKey: ["pickup-commitments"] });
    },
    onError: (err: any) => {
      toast.error("Completion Failed", err.response?.data?.detail || "Could not complete pickup");
    },
  });

  const failPickupMutation = useMutation({
    mutationFn: () =>
      pickupMonitoringApi.failPickup(selectedCommitment!.id, {
        failure_reason: failureReason,
        penalty_amount: penaltyAmount ? parseFloat(penaltyAmount) : undefined,
      }),
    onSuccess: () => {
      toast.warning("Pickup Failed", "Commitment marked breached and recovery triggered.");
      setFailModalOpen(false);
      queryClient.invalidateQueries({ queryKey: ["pickup-commitments"] });
      queryClient.invalidateQueries({ queryKey: ["recovery-cases"] });
    },
    onError: (err: any) => {
      toast.error("Action Failed", err.response?.data?.detail || "Could not fail pickup");
    },
  });

  const approveRecoveryMutation = useMutation({
    mutationFn: () =>
      pickupMonitoringApi.approveRecovery(selectedRecoveryCase!.id, {
        replacement_transporter_id: selectedReplacementTransporterId,
        notes: "Approved via Operations Control Tower",
      }),
    onSuccess: () => {
      toast.success("Recovery Executed", "Replacement transporter dispatched and reassignment confirmed.");
      setApproveRecoveryModalOpen(false);
      queryClient.invalidateQueries({ queryKey: ["recovery-cases"] });
      queryClient.invalidateQueries({ queryKey: ["pickup-commitments"] });
      queryClient.invalidateQueries({ queryKey: ["exceptions"] });
    },
    onError: (err: any) => {
      toast.error("Approval Failed", err.response?.data?.detail || "Could not execute recovery tender");
    },
  });

  const runSimulationMutation = useMutation({
    mutationFn: () => pickupMonitoringApi.simulateScenario(),
    onSuccess: (data) => {
      setSimResult(data);
      setSimModalOpen(true);
      toast.success("Simulation Complete", "10:00 AM Missed Pickup scenario generated.");
      queryClient.invalidateQueries({ queryKey: ["pickup-commitments"] });
      queryClient.invalidateQueries({ queryKey: ["recovery-cases"] });
      queryClient.invalidateQueries({ queryKey: ["exceptions"] });
    },
    onError: (err: any) => {
      toast.error("Simulation Error", err.response?.data?.detail || "Failed to run scenario");
    },
  });

  const commitments = commitmentsData?.items || [];
  const totalCommitments = commitmentsData?.total || 0;
  const totalPages = commitmentsData?.pages || 1;
  const atRiskCount = commitments.filter((c) => c.status === "AT_RISK").length;
  const reminderCount = commitments.filter((c) => c.status === "REMINDER_SENT").length;
  const missedCount = commitments.filter((c) => c.status === "MISSED" || c.is_breached).length;

  const recoveryCases = recoveryData?.items || [];
  const openRecoveryCount = recoveryCases.filter((r) => r.status === "OPEN" || r.status === "PROPOSED").length;

  const columns: ColumnDef<PickupCommitment>[] = [
    {
      id: "shipment",
      header: "Shipment / Ref",
      cell: (commitment) => (
        <div className="flex flex-col">
          <Link
            to={`/shipments/${commitment.shipment_id}`}
            className="font-semibold text-primary hover:text-burnt-orange hover:underline flex items-center gap-1"
          >
            {commitment.shipment?.tracking_number || commitment.shipment_id.slice(0, 8)}
            <ArrowRight className="h-3 w-3 text-on-surface-subtle" />
          </Link>
          <span className="text-xs text-on-surface-muted font-mono">
            {commitment.shipment?.origin_city} &rarr; {commitment.shipment?.destination_city}
          </span>
          {commitment.shipment?.customer_name && (
            <span className="text-[11px] text-on-surface-subtle">Cust: {commitment.shipment.customer_name}</span>
          )}
        </div>
      ),
    },
    {
      id: "transporter",
      header: "Transporter",
      cell: (commitment) => (
        <div className="flex flex-col">
          <span className="font-medium text-on-surface flex items-center gap-1">
            <Building2 className="h-3.5 w-3.5 text-on-surface-subtle" />
            {commitment.transporter?.name || "Assigned Carrier"}
          </span>
          <div className="flex items-center gap-2 mt-0.5">
            <span className="text-xs text-on-surface-muted">
              Score:{" "}
              <strong className="text-on-success-container">
                {commitment.transporter?.reliability_score
                  ? `${Math.round(commitment.transporter.reliability_score)}%`
                  : "N/A"}
              </strong>
            </span>
            {commitment.transporter?.phone && (
              <span className="text-[11px] text-on-surface-subtle">{commitment.transporter.phone}</span>
            )}
          </div>
        </div>
      ),
    },
    {
      id: "vehicle_driver",
      header: "Vehicle & Driver",
      cell: (commitment) => (
        <div className="flex flex-col text-xs space-y-0.5">
          <div className="flex items-center gap-1.5 text-on-surface font-mono">
            <Truck className="h-3.5 w-3.5 text-on-surface-subtle" />
            <span>{commitment.vehicle?.license_plate || "Plate Pending"}</span>
            {commitment.vehicle?.vehicle_type && (
              <span className="text-[11px] text-on-surface-subtle">({commitment.vehicle.vehicle_type})</span>
            )}
          </div>
          <div className="flex items-center gap-1.5 text-on-surface-muted">
            <UserCheck className="h-3 w-3 text-on-surface-subtle" />
            <span>
              {commitment.driver
                ? `${commitment.driver.first_name} ${commitment.driver.last_name}`
                : "Driver Pending"}
            </span>
          </div>
        </div>
      ),
    },
    {
      id: "pickup_deadline",
      header: "Pickup Deadline & SLA",
      cell: (commitment) => {
        const deadline = new Date(commitment.pickup_deadline);
        const isPast = deadline.getTime() < Date.now();
        return (
          <div className="flex flex-col">
            <span className="text-xs font-semibold text-on-surface flex items-center gap-1">
              <Calendar className="h-3.5 w-3.5 text-on-surface-subtle" />
              {deadline.toLocaleString()}
            </span>
            <div className="mt-0.5 flex items-center gap-1.5">
              {commitment.is_breached || commitment.status === "MISSED" ? (
                <span className="text-[11px] font-bold text-critical flex items-center gap-0.5">
                  <AlertTriangle className="h-3 w-3" /> SLA BREACHED
                </span>
              ) : commitment.status === "AT_RISK" ? (
                <span className="text-[11px] font-semibold text-warning animate-pulse flex items-center gap-0.5">
                  <Clock className="h-3 w-3" /> &lt; 10m SLA Buffer
                </span>
              ) : isPast && commitment.status !== "COMPLETED" ? (
                <span className="text-[11px] text-rose-500">Overdue</span>
              ) : (
                <span className="text-[11px] text-success">Within Window</span>
              )}
            </div>
          </div>
        );
      },
    },
    {
      id: "status",
      header: "Status",
      cell: (commitment) => <StatusBadge status={commitment.status} />,
    },
    {
      id: "actions",
      header: "Live Operations",
      cell: (commitment) => (
        <div className="flex items-center gap-1.5 flex-wrap">
          {["PENDING", "REMINDER_SENT", "AT_RISK"].includes(commitment.status) && (
            <Button
              size="sm"
              variant="outline"
              className="text-xs h-7 px-2 border-indigo-200 text-indigo-700 hover:bg-indigo-50"
              onClick={() => {
                setSelectedCommitment(commitment);
                setDockNumber("");
                setArrivalNotes("");
                setArrivalModalOpen(true);
              }}
            >
              Report Arrival
            </Button>
          )}

          {commitment.status === "ARRIVED" && (
            <Button
              size="sm"
              variant="outline"
              className="text-xs h-7 px-2 border-teal-200 text-on-success-container hover:bg-success-container"
              onClick={() => {
                setSelectedCommitment(commitment);
                setBayNumber("");
                setStartModalOpen(true);
              }}
            >
              Start Loading
            </Button>
          )}

          {commitment.status === "STARTED" && (
            <Button
              size="sm"
              variant="default"
              className="text-xs h-7 px-2 bg-emerald-600 hover:bg-emerald-700 text-white"
              onClick={() => {
                setSelectedCommitment(commitment);
                setBolNumber("");
                setSealNumber("");
                setLoadedWeight("");
                setCompleteModalOpen(true);
              }}
            >
              Complete Pickup
            </Button>
          )}

          {!["COMPLETED", "MISSED", "CANCELLED"].includes(commitment.status) && (
            <Button
              size="sm"
              variant="ghost"
              className="text-xs h-7 px-2 text-critical hover:bg-critical-container"
              onClick={() => {
                setSelectedCommitment(commitment);
                setFailureReason("");
                setPenaltyAmount("");
                setFailModalOpen(true);
              }}
            >
              Report Failure
            </Button>
          )}

          {commitment.status === "MISSED" && commitment.exception_id && (
            <Link to={`/exceptions/${commitment.exception_id}`}>
              <Button size="sm" variant="outline" className="text-xs h-7 px-2 border-rose-200 text-on-critical-container hover:bg-critical-container">
                View Exception
              </Button>
            </Link>
          )}
        </div>
      ),
    },
  ];

  return (
    <div className="space-y-6">
      {/* Page Header */}
      <PageHeader
        title="Pickup Accountability Engine"
        subtitle="Automated SLA surveillance, 30m reminders, 10m risk mitigation, and instant replacement recovery."
        breadcrumbs={[
          { label: "Overview", href: "/overview" },
          { label: "Pickup Monitoring" },
        ]}
        actions={
          <div className="flex items-center gap-2">
            <Button
              variant="outline"
              size="sm"
              onClick={() => runSimulationMutation.mutate()}
              disabled={runSimulationMutation.isPending}
              className="border-purple-200 text-purple-700 hover:bg-purple-50 shadow-2xs"
            >
              <Sparkles className="h-4 w-4 mr-1.5 text-purple-600" />
              {runSimulationMutation.isPending ? "Simulating..." : "10 AM Scenario Demo"}
            </Button>

            <Button
              variant="default"
              size="sm"
              onClick={() => scanMutation.mutate()}
              disabled={scanMutation.isPending}
              className="bg-navy-900 hover:bg-navy-800 text-white shadow-2xs"
            >
              <RotateCw className={`h-4 w-4 mr-1.5 ${scanMutation.isPending ? "animate-spin" : ""}`} />
              {scanMutation.isPending ? "Scanning SLAs..." : "Scan SLA Timers"}
            </Button>
          </div>
        }
      />

      {/* KPI Cards */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-5 gap-4">
        <MetricCard
          title="Active Commitments"
          value={totalCommitments}
          icon={<Truck className="h-5 w-5 text-primary" />}
          footnote="Monitored booking contracts"
        />
        <MetricCard
          title="Reminder Sent (30m)"
          value={reminderCount}
          icon={<Clock className="h-5 w-5 text-primary" />}
          footnote="Advance alert emitted"
        />
        <MetricCard
          title="At Risk (10m SLA)"
          value={atRiskCount}
          icon={<AlertTriangle className="h-5 w-5 text-amber-500" />}
          footnote="Arrival unconfirmed"
        />
        <MetricCard
          title="Missed / Breached"
          value={missedCount}
          icon={<ShieldAlert className="h-5 w-5 text-critical" />}
          footnote="Exceptions generated"
        />
        <MetricCard
          title="Open Recovery Cases"
          value={openRecoveryCount}
          icon={<Zap className="h-5 w-5 text-purple-600" />}
          footnote="Replacement matching active"
        />
      </div>

      {/* Mode Navigation Tabs */}
      <div className="border-b border-outline-variant">
        <div className="flex gap-6">
          <button
            onClick={() => setActiveTab("commitments")}
            className={`pb-3 text-sm font-semibold transition-colors border-b-2 flex items-center gap-2 ${
              activeTab === "commitments"
                ? "border-blue-600 text-primary"
                : "border-transparent text-on-surface-muted hover:text-on-surface"
            }`}
          >
            <Clock className="h-4 w-4" />
            Pickup Commitments Monitor ({totalCommitments})
          </button>
          <button
            onClick={() => setActiveTab("recovery")}
            className={`pb-3 text-sm font-semibold transition-colors border-b-2 flex items-center gap-2 ${
              activeTab === "recovery"
                ? "border-blue-600 text-primary"
                : "border-transparent text-on-surface-muted hover:text-on-surface"
            }`}
          >
            <Zap className="h-4 w-4" />
            Recovery &amp; Reassignment Cases ({openRecoveryCount} Open)
          </button>
        </div>
      </div>

      {activeTab === "commitments" && (
        <Card className="p-4 space-y-4">
          {/* Status Tab Filters */}
          <div className="flex gap-2 overflow-x-auto pb-1 scrollbar-thin">
            {STATUS_TABS.map((tab) => (
              <button
                key={tab.value}
                onClick={() => {
                  setStatusFilter(tab.value);
                  setPage(1);
                }}
                className={`px-3 py-1.5 rounded-lg text-xs font-medium whitespace-nowrap transition-colors ${
                  statusFilter === tab.value
                    ? "bg-surface-card text-white"
                    : "bg-surface-container text-on-surface-muted hover:bg-surface-container"
                }`}
              >
                {tab.label}
              </button>
            ))}
          </div>

          <DataTable
            columns={columns}
            data={commitments}
            keyExtractor={(item) => item.id}
            isLoading={isLoadingCommitments}
            pagination={{
              currentPage: page,
              totalPages,
              totalItems: totalCommitments,
              pageSize,
              onPageChange: setPage,
            }}
            emptyTitle="No commitments found"
            emptyDescription="No active pickup commitments matching selected criteria."
          />
        </Card>
      )}

      {activeTab === "recovery" && (
        <div className="space-y-4">
          {recoveryCases.length === 0 ? (
            <Card className="p-12 text-center text-on-surface-muted">
              <CheckCircle2 className="h-10 w-10 text-emerald-500 mx-auto mb-2" />
              <h3 className="text-base font-semibold text-on-surface">No Open Recovery Incidents</h3>
              <p className="text-xs text-on-surface-muted max-w-md mx-auto mt-1">
                All pickups are currently on schedule or safely executed without breach.
              </p>
            </Card>
          ) : (
            recoveryCases.map((rc) => (
              <Card key={rc.id} className="p-5 border-l-4 border-l-purple-600 space-y-4">
                <div className="flex flex-col md:flex-row md:items-center justify-between gap-2 border-b border-outline-variant pb-3">
                  <div>
                    <div className="flex items-center gap-2">
                      <span className="font-mono font-bold text-sm text-on-surface">{rc.case_number}</span>
                      <StatusBadge status={rc.status} />
                      <span className="text-xs font-semibold px-2 py-0.5 rounded bg-purple-50 text-purple-700 border border-purple-200">
                        {rc.strategy.replace(/_/g, " ")}
                      </span>
                    </div>
                    <p className="text-xs text-on-surface-muted mt-1">
                      Opened at: {new Date(rc.created_at).toLocaleString()}
                      {rc.shipment_id && ` | Shipment ID: ${rc.shipment_id.slice(0, 8)}`}
                    </p>
                  </div>
                  <div className="flex items-center gap-2">
                    <Link to={`/exceptions/${rc.exception_id}`}>
                      <Button size="sm" variant="outline" className="text-xs">
                        View Linked Exception
                      </Button>
                    </Link>
                  </div>
                </div>

                <div className="grid grid-cols-1 md:grid-cols-2 gap-4 text-xs">
                  <div className="bg-surface-container-low p-3 rounded-lg border border-outline-variant">
                    <span className="font-semibold text-on-surface block mb-1">Incident Diagnosis</span>
                    <p className="text-on-surface-muted leading-relaxed">{rc.proposed_solution}</p>
                    {rc.failure_data?.failure_reason && (
                      <p className="mt-2 text-on-critical-container font-medium">
                        Root Reason: {rc.failure_data.failure_reason}
                      </p>
                    )}
                  </div>

                  <div className="bg-surface-container-low p-3 rounded-lg border border-outline-variant">
                    <span className="font-semibold text-on-surface block mb-1">Original Carrier Dossier</span>
                    <p className="text-on-surface-muted">
                      Carrier ID: <span className="font-mono">{rc.original_transporter_id || "N/A"}</span>
                    </p>
                    <p className="text-on-surface-muted mt-1">
                      Estimated Cost Impact:{" "}
                      <strong className="text-on-surface">${rc.estimated_cost_impact.toLocaleString()}</strong>
                    </p>
                    <p className="text-on-surface-muted mt-1">
                      Historical status: <strong className="text-purple-700">PRESERVED (REASSIGNED)</strong>
                    </p>
                  </div>
                </div>

                {/* Candidate Alternatives */}
                {rc.alternatives_data && rc.alternatives_data.length > 0 && (
                  <div className="space-y-2">
                    <span className="text-xs font-bold text-on-surface uppercase tracking-wider flex items-center gap-1.5">
                      <Sparkles className="h-3.5 w-3.5 text-purple-600" />
                      Algorithmic Replacement Recommendations
                    </span>
                    <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
                      {rc.alternatives_data.map((alt) => (
                        <div
                          key={alt.transporter_id}
                          className="p-3 rounded-lg border border-outline-variant hover:border-purple-400 bg-surface-card shadow-2xs flex flex-col justify-between"
                        >
                          <div>
                            <div className="flex items-center justify-between">
                              <span className="font-semibold text-sm text-on-surface">{alt.transporter_name}</span>
                              <span className="text-xs px-1.5 py-0.5 rounded bg-success-container text-on-success-container font-bold">
                                {Math.round(alt.match_score * 100)}% Match
                              </span>
                            </div>
                            <p className="text-xs text-on-surface-muted mt-1">
                              Reliability: <strong>{Math.round(alt.reliability_score)}%</strong> | Est Cost:{" "}
                              <strong>${alt.estimated_cost}</strong>
                            </p>
                            <p className="text-[11px] text-on-surface-muted mt-1.5 italic bg-surface-container-low p-1.5 rounded">
                              {alt.fit_reason}
                            </p>
                          </div>
                          {rc.status === "OPEN" || rc.status === "PROPOSED" ? (
                            <Button
                              size="sm"
                              className="mt-3 w-full bg-purple-700 hover:bg-purple-800 text-white text-xs"
                              onClick={() => {
                                setSelectedRecoveryCase(rc);
                                setSelectedReplacementTransporterId(alt.transporter_id);
                                setApproveRecoveryModalOpen(true);
                              }}
                            >
                              Dispatch Replacement Tender
                            </Button>
                          ) : (
                            <span className="mt-3 text-center text-xs font-semibold text-on-success-container block">
                              Execution Completed
                            </span>
                          )}
                        </div>
                      ))}
                    </div>
                  </div>
                )}
              </Card>
            ))
          )}
        </div>
      )}

      {/* Arrival Modal */}
      <ConfirmationDialog
        isOpen={arrivalModalOpen}
        onClose={() => setArrivalModalOpen(false)}
        onConfirm={() => reportArrivalMutation.mutate()}
        title="Report Vehicle Arrival at Origin"
        description="Confirm that the assigned transporter and driver have physically arrived at the pickup facility dock."
        confirmLabel="Confirm Arrival"
        isLoading={reportArrivalMutation.isPending}
      >
        <div className="space-y-3 mt-3">
          <div>
            <label className="text-xs font-semibold text-on-surface">Dock / Bay Number (Optional)</label>
            <Input
              value={dockNumber}
              onChange={(e) => setDockNumber(e.target.value)}
              placeholder="e.g. Dock 4B"
              className="mt-1 text-sm"
            />
          </div>
          <div>
            <label className="text-xs font-semibold text-on-surface">Operational Notes</label>
            <Input
              value={arrivalNotes}
              onChange={(e) => setArrivalNotes(e.target.value)}
              placeholder="Driver badge verified, vehicle inspected"
              className="mt-1 text-sm"
            />
          </div>
        </div>
      </ConfirmationDialog>

      {/* Start Loading Modal */}
      <ConfirmationDialog
        isOpen={startModalOpen}
        onClose={() => setStartModalOpen(false)}
        onConfirm={() => startPickupMutation.mutate()}
        title="Commence Cargo Loading"
        description="Update status to Loading in Progress. Cargo is being staged and placed into the trailer."
        confirmLabel="Start Loading"
        isLoading={startPickupMutation.isPending}
      >
        <div className="space-y-3 mt-3">
          <div>
            <label className="text-xs font-semibold text-on-surface">Staging Bay Number (Optional)</label>
            <Input
              value={bayNumber}
              onChange={(e) => setBayNumber(e.target.value)}
              placeholder="e.g. Bay 12"
              className="mt-1 text-sm"
            />
          </div>
        </div>
      </ConfirmationDialog>

      {/* Complete Pickup Modal */}
      <ConfirmationDialog
        isOpen={completeModalOpen}
        onClose={() => setCompleteModalOpen(false)}
        onConfirm={() => completePickupMutation.mutate()}
        title="Complete Pickup &amp; Dispatch Consignment"
        description="Confirm that cargo is fully loaded, trailer is secured, and Bill of Lading has been executed."
        confirmLabel="Complete &amp; Dispatch"
        isLoading={completePickupMutation.isPending}
      >
        <div className="space-y-3 mt-3">
          <div>
            <label className="text-xs font-semibold text-on-surface">Bill of Lading (BOL) Number</label>
            <Input
              value={bolNumber}
              onChange={(e) => setBolNumber(e.target.value)}
              placeholder="BOL-2026-99881"
              className="mt-1 text-sm"
            />
          </div>
          <div>
            <label className="text-xs font-semibold text-on-surface">Container Seal Number</label>
            <Input
              value={sealNumber}
              onChange={(e) => setSealNumber(e.target.value)}
              placeholder="SEAL-44321"
              className="mt-1 text-sm"
            />
          </div>
          <div>
            <label className="text-xs font-semibold text-on-surface">Scale Weight (KG)</label>
            <Input
              type="number"
              value={loadedWeight}
              onChange={(e) => setLoadedWeight(e.target.value)}
              placeholder="e.g. 15000"
              className="mt-1 text-sm"
            />
          </div>
        </div>
      </ConfirmationDialog>

      {/* Fail Pickup Modal */}
      <ConfirmationDialog
        isOpen={failModalOpen}
        onClose={() => setFailModalOpen(false)}
        onConfirm={() => {
          if (!failureReason.trim()) {
            toast.error("Reason Required", "Please specify why the pickup failed.");
            return;
          }
          failPickupMutation.mutate();
        }}
        title="Report Pickup Failure / Carrier Breach"
        description="Marking a pickup as failed triggers the accountability engine, opens an exception record, and launches the recovery workflow."
        confirmLabel="Report Breach"
        variant="destructive"
        isLoading={failPickupMutation.isPending}
      >
        <div className="space-y-3 mt-3">
          <div>
            <label className="text-xs font-semibold text-on-surface">Failure Reason *</label>
            <Input
              value={failureReason}
              onChange={(e) => setFailureReason(e.target.value)}
              placeholder="Driver no-show, vehicle breakdown, capacity refusal"
              className="mt-1 text-sm"
            />
          </div>
          <div>
            <label className="text-xs font-semibold text-on-surface">SLA Contract Penalty ($ Optional)</label>
            <Input
              type="number"
              value={penaltyAmount}
              onChange={(e) => setPenaltyAmount(e.target.value)}
              placeholder="250"
              className="mt-1 text-sm"
            />
          </div>
        </div>
      </ConfirmationDialog>

      {/* Approve Recovery Replacement Modal */}
      <ConfirmationDialog
        isOpen={approveRecoveryModalOpen}
        onClose={() => setApproveRecoveryModalOpen(false)}
        onConfirm={() => approveRecoveryMutation.mutate()}
        title="Approve Replacement Carrier Tender"
        description="This will create a new confirmed booking with the selected replacement carrier, advance the recovery case to RESOLVED, and preserve the breached assignment history as REASSIGNED."
        confirmLabel="Approve &amp; Dispatch"
        isLoading={approveRecoveryMutation.isPending}
      />

      {/* 10 AM Simulation Results Dialog */}
      <ConfirmationDialog
        isOpen={simModalOpen}
        onClose={() => setSimModalOpen(false)}
        onConfirm={() => setSimModalOpen(false)}
        title="10:00 AM Scenario Walkthrough Demonstration"
        description="Complete execution of the CargoPulse Pickup Accountability Engine end-to-end simulation."
        confirmLabel="Acknowledge Scenario"
      >
        {simResult && (
          <div className="space-y-4 mt-3 max-h-[60vh] overflow-y-auto pr-1">
            <div className="bg-surface-container-low p-3 rounded-lg border border-outline-variant text-xs">
              <div className="grid grid-cols-2 gap-2">
                <div>
                  <span className="text-on-surface-muted">Shipment Ref:</span>
                  <p className="font-bold text-on-surface">{simResult.tracking_number}</p>
                </div>
                <div>
                  <span className="text-on-surface-muted">Pickup Deadline:</span>
                  <p className="font-bold text-on-surface">{simResult.pickup_deadline}</p>
                </div>
                <div>
                  <span className="text-on-surface-muted">Breached Carrier:</span>
                  <p className="font-semibold text-on-critical-container">{simResult.transporter_a_name}</p>
                </div>
                <div>
                  <span className="text-on-surface-muted">Replacement Carrier:</span>
                  <p className="font-semibold text-on-success-container">{simResult.transporter_c_name}</p>
                </div>
              </div>
            </div>

            <div className="space-y-2">
              <span className="text-xs font-bold text-on-surface uppercase">Chronological Milestones</span>
              <div className="space-y-2">
                {simResult.milestones.map((m, idx) => (
                  <div key={idx} className="flex items-start gap-2 text-xs bg-surface-card p-2.5 rounded border border-outline-variant">
                    <span className="font-bold text-primary shrink-0">{m.step}:</span>
                    <span className="text-on-surface flex-1">{m.description}</span>
                    <span className="px-1.5 py-0.5 rounded text-[10px] font-semibold bg-surface-container text-on-surface-muted shrink-0">
                      {m.status}
                    </span>
                  </div>
                ))}
              </div>
            </div>

            <div className="p-3 bg-purple-50 rounded-lg border border-purple-200 text-xs text-purple-900 space-y-1">
              <p className="font-bold">Audit &amp; Accountability Verification:</p>
              <p>&bull; Recovery Case Number: <span className="font-mono">{simResult.recovery_case_number}</span></p>
              <p>&bull; Replacement Booking Reference: <span className="font-mono">{simResult.replacement_booking_ref}</span></p>
              <p>&bull; Historical Assignments Preserved: {simResult.assignment_history.map(h => `${h.transporter_name} (${h.status})`).join(" &rarr; ")}</p>
            </div>
          </div>
        )}
      </ConfirmationDialog>
    </div>
  );
};
