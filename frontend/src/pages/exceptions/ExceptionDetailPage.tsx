import React, { useState } from "react";
import { useParams, Link, useNavigate } from "react-router-dom";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import {
  ArrowLeft,
  AlertTriangle,
  Clock,
  CheckCircle2,
  Truck,
  Building2,
  UserCheck,
  FileText,
  TrendingUp,
  ExternalLink,
  Zap,
} from "lucide-react";
import {
  exceptionsApi,
  ExceptionSeverity,
} from "@/api/exceptions";
import { PageHeader } from "@/components/common/PageHeader";
import { StatusBadge } from "@/components/common/StatusBadge";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { ConfirmationDialog } from "@/components/common/ConfirmationDialog";
import { ActivityTimeline, TimelineEvent } from "@/components/common/ActivityTimeline";
import { LoadingState } from "@/components/common/LoadingState";
import { ErrorState } from "@/components/common/ErrorState";
import { useToast } from "@/context/ToastContext";

export const ExceptionDetailPage: React.FC = () => {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const { toast } = useToast();

  // Action Modals State
  const [ackModalOpen, setAckModalOpen] = useState(false);
  const [ackNotes, setAckNotes] = useState("");

  const [assignModalOpen, setAssignModalOpen] = useState(false);
  const [assignedOwnerId, setAssignedOwnerId] = useState("");
  const [assignNotes, setAssignNotes] = useState("");

  const [escalateModalOpen, setEscalateModalOpen] = useState(false);
  const [targetSeverity, setTargetSeverity] = useState<ExceptionSeverity>("CRITICAL");
  const [escalationReason, setEscalationReason] = useState("");

  const [resolveModalOpen, setResolveModalOpen] = useState(false);
  const [rootCause, setRootCause] = useState("");
  const [resolutionNotes, setResolutionNotes] = useState("");

  const [closeModalOpen, setCloseModalOpen] = useState(false);
  const [closureReason, setClosureReason] = useState("");

  // Fetch Exception Dossier
  const { data: exc, isLoading, error, refetch } = useQuery({
    queryKey: ["exception-detail", id],
    queryFn: () => exceptionsApi.getException(id!),
    enabled: !!id,
  });

  // Action Mutations
  const acknowledgeMutation = useMutation({
    mutationFn: () => exceptionsApi.acknowledgeException(id!, ackNotes || undefined),
    onSuccess: () => {
      toast.success("Acknowledged", "Incident marked as acknowledged.");
      setAckModalOpen(false);
      refetch();
      queryClient.invalidateQueries({ queryKey: ["exceptions"] });
    },
    onError: (err: any) => {
      toast.error("Action Failed", err.response?.data?.detail || "Could not acknowledge");
    },
  });

  const assignMutation = useMutation({
    mutationFn: () => exceptionsApi.assignException(id!, assignedOwnerId, assignNotes || undefined),
    onSuccess: () => {
      toast.success("Owner Assigned", "Operational incident assigned to coordinator.");
      setAssignModalOpen(false);
      refetch();
      queryClient.invalidateQueries({ queryKey: ["exceptions"] });
    },
    onError: (err: any) => {
      toast.error("Assignment Failed", err.response?.data?.detail || "Could not assign owner");
    },
  });

  const escalateMutation = useMutation({
    mutationFn: () =>
      exceptionsApi.escalateException(id!, {
        target_severity: targetSeverity,
        escalation_reason: escalationReason,
      }),
    onSuccess: () => {
      toast.warning("Incident Escalated", "Severity bumped and executive alerts notified.");
      setEscalateModalOpen(false);
      refetch();
      queryClient.invalidateQueries({ queryKey: ["exceptions"] });
    },
    onError: (err: any) => {
      toast.error("Escalation Failed", err.response?.data?.detail || "Could not escalate incident");
    },
  });

  const resolveMutation = useMutation({
    mutationFn: () =>
      exceptionsApi.resolveException(id!, {
        root_cause: rootCause,
        resolution_notes: resolutionNotes,
      }),
    onSuccess: () => {
      toast.success("Incident Resolved", "Root cause diagnosed and resolution logged.");
      setResolveModalOpen(false);
      refetch();
      queryClient.invalidateQueries({ queryKey: ["exceptions"] });
    },
    onError: (err: any) => {
      toast.error("Resolution Failed", err.response?.data?.detail || "Could not resolve incident");
    },
  });

  const closeMutation = useMutation({
    mutationFn: () =>
      exceptionsApi.closeException(id!, {
        closure_reason: closureReason,
      }),
    onSuccess: () => {
      toast.success("Incident Closed", "Case officially archived in compliance ledger.");
      setCloseModalOpen(false);
      refetch();
      queryClient.invalidateQueries({ queryKey: ["exceptions"] });
    },
    onError: (err: any) => {
      toast.error("Closure Failed", err.response?.data?.detail || "Could not close incident");
    },
  });

  if (isLoading) {
    return <LoadingState text="Retrieving incident dossier and audit records..." />;
  }

  if (error || !exc) {
    return (
      <ErrorState
        title="Incident Record Not Found"
        message="The requested operational exception dossier could not be located."
        onRetry={() => navigate("/exceptions")}
      />
    );
  }

  // Build timeline events from audit trail
  const timelineEvents: TimelineEvent[] = (exc.audit_trail || []).map((audit) => ({
    id: audit.id,
    title: audit.action.replace(/_/g, " "),
    description: audit.details,
    timestamp: audit.timestamp,
    actor: audit.user_name,
    iconColor: audit.action.includes("RESOLVED") || audit.action.includes("CLOSED")
      ? "emerald"
      : audit.action.includes("ESCALATED") || audit.action.includes("CRITICAL")
      ? "rose"
      : audit.action.includes("ACKNOWLEDGED")
      ? "amber"
      : "blue",
  }));

  return (
    <div className="space-y-6">
      {/* Page Header */}
      <PageHeader
        title={exc.title}
        subtitle={`Incident Dossier: ${exc.exception_type.replace(/_/g, " ")} | Ref: ${exc.id.slice(0, 8)}`}
        breadcrumbs={[
          { label: "Overview", href: "/overview" },
          { label: "Exceptions", href: "/exceptions" },
          { label: exc.id.slice(0, 8) },
        ]}
        actions={
          <div className="flex items-center gap-2">
            <Link to="/exceptions">
              <Button variant="outline" size="sm">
                <ArrowLeft className="h-4 w-4 mr-1.5" />
                Back to Control Tower
              </Button>
            </Link>
          </div>
        }
      />

      {/* Top Banner Status Bar */}
      <Card className="p-4 bg-surface-card text-white flex flex-wrap items-center justify-between gap-4">
        <div className="flex items-center gap-3">
          <StatusBadge status={exc.status} />
          <div className="flex items-center gap-2">
            <span className="text-xs text-on-surface-subtle">Severity:</span>
            <StatusBadge status={exc.severity} size="sm" />
          </div>
          <div className="flex items-center gap-2">
            <span className="text-xs text-on-surface-subtle">Priority:</span>
            <span className="text-xs font-semibold px-2 py-0.5 rounded bg-surface-container text-on-surface">
              {exc.priority}
            </span>
          </div>
          {exc.escalation_level > 0 && (
            <span className="text-xs font-bold px-2 py-0.5 rounded bg-rose-950 text-rose-300 border border-rose-800 flex items-center gap-1">
              <TrendingUp className="h-3 w-3" /> Level {exc.escalation_level} Escalation
            </span>
          )}
        </div>

        {/* Action Controls */}
        <div className="flex items-center gap-2 flex-wrap">
          {exc.status === "OPEN" && (
            <Button
              size="sm"
              className="bg-warning-container0 hover:bg-amber-600 text-on-surface font-semibold text-xs"
              onClick={() => {
                setAckNotes("");
                setAckModalOpen(true);
              }}
            >
              Acknowledge Incident
            </Button>
          )}

          {["OPEN", "ACKNOWLEDGED", "INVESTIGATING", "RESOLVING"].includes(exc.status) && (
            <>
              <Button
                size="sm"
                variant="outline"
                className="bg-surface-container border-outline-strong text-on-surface hover:bg-surface-container-high text-xs"
                onClick={() => {
                  setAssignedOwnerId(exc.assigned_owner_id || "");
                  setAssignNotes("");
                  setAssignModalOpen(true);
                }}
              >
                <UserCheck className="h-3.5 w-3.5 mr-1" />
                Assign Owner
              </Button>

              <Button
                size="sm"
                variant="outline"
                className="bg-rose-950/40 border-rose-800 text-rose-300 hover:bg-rose-900/60 text-xs"
                onClick={() => {
                  setTargetSeverity("CRITICAL");
                  setEscalationReason("");
                  setEscalateModalOpen(true);
                }}
              >
                <AlertTriangle className="h-3.5 w-3.5 mr-1 text-rose-400" />
                Escalate
              </Button>

              <Button
                size="sm"
                className="bg-emerald-600 hover:bg-emerald-700 text-white text-xs font-semibold"
                onClick={() => {
                  setRootCause(exc.root_cause || "");
                  setResolutionNotes(exc.resolution_notes || "");
                  setResolveModalOpen(true);
                }}
              >
                <CheckCircle2 className="h-3.5 w-3.5 mr-1" />
                Resolve Incident
              </Button>
            </>
          )}

          {exc.status === "RESOLVED" && (
            <Button
              size="sm"
              className="bg-primary hover:bg-burnt-orange text-white text-xs font-semibold"
              onClick={() => {
                setClosureReason("");
                setCloseModalOpen(true);
              }}
            >
              <CheckCircle2 className="h-3.5 w-3.5 mr-1" />
              Close &amp; Archive Case
            </Button>
          )}
        </div>
      </Card>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Left 2 Columns: Incident Overview & Audit Trail */}
        <div className="lg:col-span-2 space-y-6">
          {/* Incident Description & Root Cause Card */}
          <Card className="p-5 space-y-4">
            <h3 className="text-sm font-bold text-on-surface uppercase tracking-wider flex items-center gap-1.5">
              <FileText className="h-4 w-4 text-primary" />
              Incident Narrative &amp; Findings
            </h3>

            <div className="bg-surface-container-low p-3.5 rounded-lg border border-outline-variant">
              <span className="text-xs font-semibold text-on-surface-muted uppercase">Description</span>
              <p className="text-sm text-on-surface mt-1 leading-relaxed">{exc.description}</p>
            </div>

            {exc.root_cause && (
              <div className="bg-purple-50 p-3.5 rounded-lg border border-purple-200">
                <span className="text-xs font-semibold text-purple-700 uppercase">Root Cause Analysis</span>
                <p className="text-sm text-purple-950 mt-1 leading-relaxed font-medium">{exc.root_cause}</p>
              </div>
            )}

            {exc.resolution_notes && (
              <div className="bg-success-container p-3.5 rounded-lg border border-emerald-200">
                <span className="text-xs font-semibold text-on-success-container uppercase">Resolution Notes</span>
                <p className="text-sm text-emerald-950 mt-1 leading-relaxed">{exc.resolution_notes}</p>
              </div>
            )}

            {exc.closure_reason && (
              <div className="bg-surface-container p-3.5 rounded-lg border border-outline-variant">
                <span className="text-xs font-semibold text-on-surface-muted uppercase">Closure Verification</span>
                <p className="text-sm text-on-surface mt-1 leading-relaxed">{exc.closure_reason}</p>
              </div>
            )}
          </Card>

          {/* Activity Timeline */}
          <Card className="p-5 space-y-4">
            <h3 className="text-sm font-bold text-on-surface uppercase tracking-wider flex items-center gap-1.5">
              <Clock className="h-4 w-4 text-primary" />
              Activity &amp; Audit Trail
            </h3>
            <ActivityTimeline events={timelineEvents} />
          </Card>
        </div>

        {/* Right Column: Linked Entities Dossiers */}
        <div className="space-y-6">
          {/* Shipment Dossier */}
          <Card className="p-4 space-y-3">
            <div className="flex items-center justify-between border-b border-outline-variant pb-2">
              <span className="text-xs font-bold text-on-surface uppercase tracking-wider flex items-center gap-1.5">
                <Truck className="h-4 w-4 text-primary" />
                Linked Shipment
              </span>
              {exc.shipment && (
                <Link
                  to={`/shipments/${exc.shipment_id}`}
                  className="text-xs text-primary hover:underline flex items-center gap-0.5"
                >
                  View <ExternalLink className="h-3 w-3" />
                </Link>
              )}
            </div>

            {exc.shipment ? (
              <div className="text-xs space-y-2">
                <div>
                  <span className="text-on-surface-subtle">Tracking Reference:</span>
                  <p className="font-mono font-bold text-on-surface">{exc.shipment.tracking_number}</p>
                </div>
                <div>
                  <span className="text-on-surface-subtle">Route:</span>
                  <p className="font-medium text-on-surface">
                    {exc.shipment.origin_city} &rarr; {exc.shipment.destination_city}
                  </p>
                </div>
                <div>
                  <span className="text-on-surface-subtle">Current Status:</span>
                  <div className="mt-0.5">
                    <StatusBadge status={exc.shipment.status} size="sm" />
                  </div>
                </div>
              </div>
            ) : (
              <p className="text-xs text-on-surface-subtle italic">No shipment directly tied to this exception.</p>
            )}
          </Card>

          {/* Transporter Dossier */}
          <Card className="p-4 space-y-3">
            <div className="flex items-center justify-between border-b border-outline-variant pb-2">
              <span className="text-xs font-bold text-on-surface uppercase tracking-wider flex items-center gap-1.5">
                <Building2 className="h-4 w-4 text-primary" />
                Involved Transporter
              </span>
              {exc.transporter && (
                <Link
                  to={`/transporters/${exc.transporter_id}`}
                  className="text-xs text-primary hover:underline flex items-center gap-0.5"
                >
                  Profile <ExternalLink className="h-3 w-3" />
                </Link>
              )}
            </div>

            {exc.transporter ? (
              <div className="text-xs space-y-2">
                <div>
                  <span className="text-on-surface-subtle">Company Name:</span>
                  <p className="font-bold text-on-surface">{exc.transporter.name}</p>
                </div>
                <div>
                  <span className="text-on-surface-subtle">Carrier Code:</span>
                  <p className="font-mono text-on-surface">{exc.transporter.code}</p>
                </div>
              </div>
            ) : (
              <p className="text-xs text-on-surface-subtle italic">No specific carrier flagged in this exception.</p>
            )}
          </Card>

          {/* Recovery Cases */}
          {exc.recovery_cases && exc.recovery_cases.length > 0 && (
            <Card className="p-4 space-y-3 border-l-4 border-l-purple-600">
              <span className="text-xs font-bold text-purple-900 uppercase tracking-wider flex items-center gap-1.5">
                <Zap className="h-4 w-4 text-purple-600" />
                Associated Recovery Cases
              </span>
              <div className="space-y-2">
                {exc.recovery_cases.map((rc: any) => (
                  <div key={rc.id} className="p-2.5 rounded bg-purple-50 border border-purple-200 text-xs">
                    <div className="flex items-center justify-between">
                      <span className="font-mono font-bold text-purple-950">{rc.case_number}</span>
                      <StatusBadge status={rc.status} size="sm" />
                    </div>
                    <p className="text-purple-800 mt-1">{rc.proposed_solution}</p>
                  </div>
                ))}
              </div>
            </Card>
          )}

          {/* Metadata & Ownership */}
          <Card className="p-4 space-y-3 text-xs">
            <span className="text-xs font-bold text-on-surface uppercase tracking-wider block border-b border-outline-variant pb-2">
              Case Ownership &amp; Milestones
            </span>
            <div className="space-y-2">
              <div>
                <span className="text-on-surface-subtle">Assigned Coordinator:</span>
                <p className="font-semibold text-on-surface">
                  {exc.assigned_owner ? exc.assigned_owner.full_name : "Unassigned"}
                </p>
              </div>
              <div>
                <span className="text-on-surface-subtle">Reported At:</span>
                <p className="text-on-surface">{new Date(exc.reported_at).toLocaleString()}</p>
              </div>
              {exc.acknowledged_at && (
                <div>
                  <span className="text-on-surface-subtle">Acknowledged At:</span>
                  <p className="text-on-surface">{new Date(exc.acknowledged_at).toLocaleString()}</p>
                </div>
              )}
              {exc.resolved_at && (
                <div>
                  <span className="text-on-surface-subtle">Resolved At:</span>
                  <p className="text-on-surface">{new Date(exc.resolved_at).toLocaleString()}</p>
                </div>
              )}
              {exc.closed_at && (
                <div>
                  <span className="text-on-surface-subtle">Closed At:</span>
                  <p className="text-on-surface">{new Date(exc.closed_at).toLocaleString()}</p>
                </div>
              )}
            </div>
          </Card>
        </div>
      </div>

      {/* Acknowledge Modal */}
      <ConfirmationDialog
        isOpen={ackModalOpen}
        onClose={() => setAckModalOpen(false)}
        onConfirm={() => acknowledgeMutation.mutate()}
        title="Acknowledge Operational Incident"
        description="Acknowledge that this incident has been reviewed by the control tower and investigation is underway."
        confirmLabel="Acknowledge"
        isLoading={acknowledgeMutation.isPending}
      >
        <div className="mt-3">
          <label className="text-xs font-semibold text-on-surface">Acknowledgment Notes (Optional)</label>
          <Input
            value={ackNotes}
            onChange={(e) => setAckNotes(e.target.value)}
            placeholder="Reviewing driver telematics and carrier logs..."
            className="mt-1 text-xs"
          />
        </div>
      </ConfirmationDialog>

      {/* Assign Owner Modal */}
      <ConfirmationDialog
        isOpen={assignModalOpen}
        onClose={() => setAssignModalOpen(false)}
        onConfirm={() => {
          if (!assignedOwnerId.trim()) {
            toast.error("User ID Required", "Please specify user ID of the assigned coordinator.");
            return;
          }
          assignMutation.mutate();
        }}
        title="Assign Incident Coordinator"
        description="Designate an operational manager to lead triage and recovery execution."
        confirmLabel="Assign Owner"
        isLoading={assignMutation.isPending}
      >
        <div className="space-y-3 mt-3">
          <div>
            <label className="text-xs font-semibold text-on-surface">Coordinator User ID *</label>
            <Input
              value={assignedOwnerId}
              onChange={(e) => setAssignedOwnerId(e.target.value)}
              placeholder="e.g. User UUID"
              className="mt-1 text-xs font-mono"
            />
          </div>
          <div>
            <label className="text-xs font-semibold text-on-surface">Handover Notes (Optional)</label>
            <Input
              value={assignNotes}
              onChange={(e) => setAssignNotes(e.target.value)}
              placeholder="Prioritize alternative dispatch coordination"
              className="mt-1 text-xs"
            />
          </div>
        </div>
      </ConfirmationDialog>

      {/* Escalate Modal */}
      <ConfirmationDialog
        isOpen={escalateModalOpen}
        onClose={() => setEscalateModalOpen(false)}
        onConfirm={() => {
          if (!escalationReason.trim()) {
            toast.error("Reason Required", "Please specify the escalation reason.");
            return;
          }
          escalateMutation.mutate();
        }}
        title="Escalate Operational Incident"
        description="Escalate this incident to executive dispatch and increase SLA severity tier."
        confirmLabel="Escalate Incident"
        variant="destructive"
        isLoading={escalateMutation.isPending}
      >
        <div className="space-y-3 mt-3">
          <div>
            <label className="text-xs font-semibold text-on-surface">Target Severity *</label>
            <select
              value={targetSeverity}
              onChange={(e) => setTargetSeverity(e.target.value as ExceptionSeverity)}
              className="w-full mt-1 text-xs border rounded-md p-1.5 bg-surface-card border-outline-variant"
            >
              <option value="CRITICAL">Critical (Immediate VP Alert)</option>
              <option value="HIGH">High (Operations Lead)</option>
            </select>
          </div>
          <div>
            <label className="text-xs font-semibold text-on-surface">Escalation Reason *</label>
            <Input
              value={escalationReason}
              onChange={(e) => setEscalationReason(e.target.value)}
              placeholder="Critical SLA breach deadline elapsed with zero response"
              className="mt-1 text-xs"
            />
          </div>
        </div>
      </ConfirmationDialog>

      {/* Resolve Modal */}
      <ConfirmationDialog
        isOpen={resolveModalOpen}
        onClose={() => setResolveModalOpen(false)}
        onConfirm={() => {
          if (!rootCause.trim() || !resolutionNotes.trim()) {
            toast.error("Fields Required", "Please provide both root cause and resolution notes.");
            return;
          }
          resolveMutation.mutate();
        }}
        title="Resolve Operational Incident"
        description="Record the confirmed root cause and operational resolution measures taken to restore service."
        confirmLabel="Submit Resolution"
        isLoading={resolveMutation.isPending}
      >
        <div className="space-y-3 mt-3">
          <div>
            <label className="text-xs font-semibold text-on-surface">Root Cause Diagnosis *</label>
            <Input
              value={rootCause}
              onChange={(e) => setRootCause(e.target.value)}
              placeholder="e.g. Carrier tractor mechanical failure en route"
              className="mt-1 text-xs"
            />
          </div>
          <div>
            <label className="text-xs font-semibold text-on-surface">Resolution Measures *</label>
            <textarea
              rows={3}
              value={resolutionNotes}
              onChange={(e) => setResolutionNotes(e.target.value)}
              placeholder="Dispatched replacement transporter C with priority dock assignment."
              className="w-full mt-1 text-xs border rounded-md p-2 bg-surface-card border-outline-variant"
            />
          </div>
        </div>
      </ConfirmationDialog>

      {/* Close Modal */}
      <ConfirmationDialog
        isOpen={closeModalOpen}
        onClose={() => setCloseModalOpen(false)}
        onConfirm={() => {
          if (!closureReason.trim()) {
            toast.error("Reason Required", "Please provide a final closure reason.");
            return;
          }
          closeMutation.mutate();
        }}
        title="Close &amp; Archive Incident Dossier"
        description="Permanently close the exception record once all downstream impacts have been reconciled."
        confirmLabel="Close Case"
        isLoading={closeMutation.isPending}
      >
        <div className="mt-3">
          <label className="text-xs font-semibold text-on-surface">Closure Reason *</label>
          <Input
            value={closureReason}
            onChange={(e) => setClosureReason(e.target.value)}
            placeholder="Consignment delivered successfully by replacement carrier."
            className="mt-1 text-xs"
          />
        </div>
      </ConfirmationDialog>
    </div>
  );
};
