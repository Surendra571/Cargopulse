import React, { useState } from "react";
import { useParams, useNavigate, Link } from "react-router-dom";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import {
  MapPin,
  Calendar,
  Clock,
  Truck,
  User,
  ShieldCheck,
  AlertTriangle,
  ArrowLeft,
  Edit2,
  XCircle,
  FileText,
  FileCheck2,
  Activity,
  History,
  CheckCircle2,
  Download,
  Info,
  Sparkles,
  Radio,
} from "lucide-react";
import { shipmentApi, ShipmentAuditLogItem } from "@/api/shipments";
import { PageHeader } from "@/components/common/PageHeader";
import { StatusBadge } from "@/components/common/StatusBadge";
import { Button } from "@/components/ui/button";
import { Card, CardHeader, CardTitle, CardContent } from "@/components/ui/card";
import { LoadingState } from "@/components/common/LoadingState";
import { ErrorState } from "@/components/common/ErrorState";
import { ConfirmationDialog } from "@/components/common/ConfirmationDialog";
import { useToast } from "@/context/ToastContext";

export const ShipmentDetailPage: React.FC = () => {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const { toast } = useToast();

  const [activeTab, setActiveTab] = useState<"timeline" | "bookings" | "exceptions" | "audit" | "pod">("timeline");
  const [cancelModalOpen, setCancelModalOpen] = useState(false);
  const [cancellationReason, setCancellationReason] = useState("");

  const { data: shipment, isLoading, isError, refetch } = useQuery({
    queryKey: ["shipment", id],
    queryFn: () => shipmentApi.getShipment(id!),
    enabled: Boolean(id),
  });

  const cancelMutation = useMutation({
    mutationFn: ({ reason }: { reason: string }) =>
      shipmentApi.cancelShipment(id!, { cancellation_reason: reason }),
    onSuccess: (updated) => {
      toast.success(
        "Shipment Cancelled",
        `Shipment ${updated.tracking_number} has been cancelled.`
      );
      setCancelModalOpen(false);
      setCancellationReason("");
      queryClient.invalidateQueries({ queryKey: ["shipment", id] });
      queryClient.invalidateQueries({ queryKey: ["shipments"] });
    },
    onError: (err: any) => {
      const msg = err.response?.data?.detail || "Failed to cancel shipment.";
      toast.error("Cancellation Error", msg);
    },
  });

  const handleConfirmCancel = () => {
    if (!cancellationReason.trim()) {
      toast.warning("Reason Required", "Please specify a cancellation reason.");
      return;
    }
    cancelMutation.mutate({ reason: cancellationReason.trim() });
  };

  if (isLoading) return <LoadingState text="Retrieving lane, carrier, and milestone events..." />;
  if (isError || !shipment) return <ErrorState title="Shipment Not Found" message="The requested shipment could not be located or you lack authorization." onRetry={() => refetch()} />;

  const canEdit = ["DRAFT", "PENDING_ACCEPTANCE", "COMMITTED"].includes(shipment.status);
  const canCancel = !["DELIVERED", "CANCELLED"].includes(shipment.status);

  return (
    <div className="p-6 max-w-7xl mx-auto space-y-6">
      {/* Top Header */}
      <PageHeader
        title={shipment.tracking_number}
        badge={
          <div className="flex items-center gap-2">
            <StatusBadge status={shipment.status} />
            <span className={`inline-flex items-center px-2 py-0.5 rounded-full text-[10px] font-semibold border ${
              shipment.priority === "CRITICAL"
                ? "bg-critical-container text-on-critical-container border-rose-200"
                : shipment.priority === "EXPEDITED"
                ? "bg-warning-container text-on-warning-container border-amber-200"
                : "bg-surface-container text-on-surface border-outline-variant"
            }`}>
              {shipment.priority}
            </span>
          </div>
        }
        subtitle={`Consigned by ${shipment.customer_name || "Internal Shipper"} • Created ${new Date(shipment.created_at).toLocaleString()}`}
        breadcrumbs={[
          { label: "Dashboard", href: "/overview" },
          { label: "Shipments", href: "/shipments" },
          { label: shipment.tracking_number, href: `/shipments/${id}` },
        ]}
        actions={
          <div className="flex items-center gap-2">
            <Button
              variant="outline"
              size="sm"
              onClick={() => navigate("/shipments")}
              className="h-9 gap-1.5 text-xs text-on-surface-muted"
            >
              <ArrowLeft className="h-3.5 w-3.5" />
              All Shipments
            </Button>

            <Button
              variant="outline"
              size="sm"
              onClick={() => navigate(`/tracking/${id}`)}
              className="h-9 gap-1.5 text-xs text-primary bg-primary-container/70 hover:bg-primary-container hover:border-blue-300 font-semibold"
            >
              <Radio className="h-3.5 w-3.5 text-primary animate-pulse" />
              Live Tracking
            </Button>

            <Button
              variant="outline"
              size="sm"
              onClick={() => navigate(`/pod/review/${id}`)}
              className="h-9 gap-1.5 text-xs text-on-success-container bg-success-container/70 hover:bg-emerald-100 hover:border-emerald-300 font-semibold"
            >
              <FileCheck2 className="h-3.5 w-3.5 text-success" />
              Proof of Delivery
            </Button>

            {shipment.status !== "CANCELLED" && shipment.status !== "DELIVERED" && (
              <Button
                variant="outline"
                size="sm"
                onClick={() => navigate(`/matching?shipment_id=${id}`)}
                className="h-9 gap-1.5 text-xs text-indigo-700 bg-indigo-50/70 hover:bg-indigo-100 hover:border-indigo-300 font-semibold"
              >
                <Sparkles className="h-3.5 w-3.5 text-indigo-600" />
                Match Carriers
              </Button>
            )}

            {canEdit && (
              <Button
                variant="outline"
                size="sm"
                onClick={() => navigate(`/shipments/${id}/edit`)}
                className="h-9 gap-1.5 text-xs text-on-surface hover:text-warning hover:border-amber-300"
              >
                <Edit2 className="h-3.5 w-3.5" />
                Edit Details
              </Button>
            )}

            {canCancel && (
              <Button
                variant="outline"
                size="sm"
                onClick={() => setCancelModalOpen(true)}
                className="h-9 gap-1.5 text-xs text-critical hover:text-on-critical-container hover:bg-critical-container hover:border-rose-300"
              >
                <XCircle className="h-3.5 w-3.5" />
                Cancel Shipment
              </Button>
            )}
          </div>
        }
      />

      {/* Metrics Row */}
      <div className="grid grid-cols-2 md:grid-cols-5 gap-3">
        <Card className="p-3.5 bg-surface-card border-outline-variant shadow-xs">
          <div className="text-[11px] font-medium text-on-surface-muted uppercase">Gross Weight</div>
          <div className="text-base font-bold text-on-surface mt-1 font-mono">
            {shipment.total_weight_kg.toLocaleString()} kg
          </div>
          <div className="text-[10px] text-on-surface-subtle mt-0.5">
            {shipment.total_volume_cbm ? `${shipment.total_volume_cbm} CBM` : "Standard volume"}
          </div>
        </Card>

        <Card className="p-3.5 bg-surface-card border-outline-variant shadow-xs">
          <div className="text-[11px] font-medium text-on-surface-muted uppercase">Packaging</div>
          <div className="text-base font-bold text-on-surface mt-1">
            {shipment.package_count} {shipment.package_unit}
          </div>
          <div className="text-[10px] text-on-surface-subtle mt-0.5">
            {shipment.is_hazardous ? "⚠️ HAZMAT Endorsement" : "Non-Hazardous"}
          </div>
        </Card>

        <Card className="p-3.5 bg-surface-card border-outline-variant shadow-xs">
          <div className="text-[11px] font-medium text-on-surface-muted uppercase">Equipment Required</div>
          <div className="text-base font-bold text-on-surface mt-1 truncate" title={shipment.required_vehicle_type}>
            {shipment.required_vehicle_type}
          </div>
          <div className="text-[10px] text-on-surface-subtle mt-0.5">{shipment.cargo_category.replace(/_/g, " ")}</div>
        </Card>

        <Card className="p-3.5 bg-surface-card border-outline-variant shadow-xs">
          <div className="text-[11px] font-medium text-on-surface-muted uppercase">Customer PO / Ref</div>
          <div className="text-base font-bold text-on-surface mt-1 truncate" title={shipment.customer_reference || "N/A"}>
            {shipment.customer_reference || "None"}
          </div>
          <div className="text-[10px] text-on-surface-subtle mt-0.5">{shipment.customer_name || "Direct Customer"}</div>
        </Card>

        <Card className="p-3.5 bg-surface-card border-outline-variant shadow-xs">
          <div className="text-[11px] font-medium text-on-surface-muted uppercase">Commercial Value</div>
          <div className="text-base font-bold text-on-surface mt-1 font-mono">
            {shipment.invoice_value ? `$${shipment.invoice_value.toLocaleString()}` : "Not declared"}
          </div>
          <div className="text-[10px] text-on-surface-subtle mt-0.5">{shipment.invoice_number ? `Inv: ${shipment.invoice_number}` : "No invoice #"}</div>
        </Card>
      </div>

      {/* Lane & Carrier Details Cards */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
        {/* Origin Card */}
        <Card className="bg-surface-card border-outline-variant shadow-xs">
          <CardHeader className="pb-3 border-b border-outline-variant bg-surface-container-low/50">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                <MapPin className="h-4 w-4 text-primary" />
                <CardTitle className="text-xs font-bold text-on-surface uppercase tracking-wide">
                  Origin (Shipper)
                </CardTitle>
              </div>
              <span className="text-[11px] font-semibold text-primary bg-primary-container px-2 py-0.5 rounded">
                Dock {shipment.origin_dock_number || "Default"}
              </span>
            </div>
          </CardHeader>
          <CardContent className="pt-3.5 space-y-2.5 text-xs">
            <div>
              <div className="font-semibold text-on-surface text-sm">{shipment.origin_name}</div>
              <div className="text-on-surface-muted">{shipment.origin_address}</div>
              <div className="text-on-surface-muted">{shipment.origin_city}, {shipment.origin_state} {shipment.origin_postal_code}</div>
            </div>

            <div className="pt-2 border-t border-outline-variant flex items-center justify-between text-on-surface-muted">
              <span>Dock Contact:</span>
              <span className="font-medium text-on-surface">{shipment.origin_contact_name} ({shipment.origin_contact_phone})</span>
            </div>

            <div className="pt-2 border-t border-outline-variant flex items-center justify-between text-on-surface-muted">
              <span className="flex items-center gap-1"><Clock className="h-3 w-3 text-amber-500" /> Cutoff:</span>
              <span className="font-semibold text-on-surface font-mono">
                {new Date(shipment.scheduled_pickup_time).toLocaleString([], { dateStyle: "short", timeStyle: "short" })}
              </span>
            </div>

            {shipment.actual_pickup_time && (
              <div className="p-2 bg-success-container border border-emerald-200 rounded text-emerald-800 flex items-center justify-between font-medium">
                <span>Picked Up:</span>
                <span className="font-mono">{new Date(shipment.actual_pickup_time).toLocaleTimeString()}</span>
              </div>
            )}
          </CardContent>
        </Card>

        {/* Destination Card */}
        <Card className="bg-surface-card border-outline-variant shadow-xs">
          <CardHeader className="pb-3 border-b border-outline-variant bg-surface-container-low/50">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                <MapPin className="h-4 w-4 text-success" />
                <CardTitle className="text-xs font-bold text-on-surface uppercase tracking-wide">
                  Destination (Consignee)
                </CardTitle>
              </div>
              <span className="text-[11px] font-semibold text-success bg-success-container px-2 py-0.5 rounded">
                Bay {shipment.destination_dock_number || "Receiving"}
              </span>
            </div>
          </CardHeader>
          <CardContent className="pt-3.5 space-y-2.5 text-xs">
            <div>
              <div className="font-semibold text-on-surface text-sm">{shipment.destination_name}</div>
              <div className="text-on-surface-muted">{shipment.destination_address}</div>
              <div className="text-on-surface-muted">{shipment.destination_city}, {shipment.destination_state} {shipment.destination_postal_code}</div>
            </div>

            <div className="pt-2 border-t border-outline-variant flex items-center justify-between text-on-surface-muted">
              <span>Receiving Contact:</span>
              <span className="font-medium text-on-surface">{shipment.destination_contact_name} ({shipment.destination_contact_phone})</span>
            </div>

            <div className="pt-2 border-t border-outline-variant flex items-center justify-between text-on-surface-muted">
              <span className="flex items-center gap-1"><Calendar className="h-3 w-3 text-teal-500" /> Delivery ETA:</span>
              <span className="font-semibold text-on-surface font-mono">
                {new Date(shipment.expected_delivery_time).toLocaleString([], { dateStyle: "short", timeStyle: "short" })}
              </span>
            </div>

            {shipment.actual_delivery_time && (
              <div className="p-2 bg-success-container border border-emerald-200 rounded text-emerald-800 flex items-center justify-between font-medium">
                <span>Delivered:</span>
                <span className="font-mono">{new Date(shipment.actual_delivery_time).toLocaleTimeString()}</span>
              </div>
            )}
          </CardContent>
        </Card>

        {/* Transporter & Driver Card */}
        <Card className="bg-surface-card border-outline-variant shadow-xs">
          <CardHeader className="pb-3 border-b border-outline-variant bg-surface-container-low/50">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                <Truck className="h-4 w-4 text-indigo-600" />
                <CardTitle className="text-xs font-bold text-on-surface uppercase tracking-wide">
                  Transporter Execution
                </CardTitle>
              </div>
              <span className="text-[10px] font-semibold text-on-surface-muted bg-surface-container px-2 py-0.5 rounded">
                Carrier Match
              </span>
            </div>
          </CardHeader>
          <CardContent className="pt-3.5 space-y-2.5 text-xs">
            <div>
              <div className="font-semibold text-on-surface text-sm">
                {shipment.assigned_transporter_name || "Unassigned"}
              </div>
              <div className="text-on-surface-muted">
                {shipment.assigned_transporter_name ? "Contracted Logistics Partner" : "Awaiting booking confirmation"}
              </div>
            </div>

            <div className="pt-2 border-t border-outline-variant flex items-center justify-between text-on-surface-muted">
              <span className="flex items-center gap-1"><User className="h-3 w-3 text-on-surface-subtle" /> Assigned Driver:</span>
              <span className="font-medium text-on-surface">{shipment.assigned_driver_name || "Not assigned"}</span>
            </div>

            <div className="pt-2 border-t border-outline-variant flex items-center justify-between text-on-surface-muted">
              <span className="flex items-center gap-1"><Truck className="h-3 w-3 text-on-surface-subtle" /> Assigned Vehicle:</span>
              <span className="font-mono font-medium text-on-surface">{shipment.assigned_vehicle_plate || "Not assigned"}</span>
            </div>

            <div className="pt-2 border-t border-outline-variant flex items-center justify-between text-on-surface-muted">
              <span className="flex items-center gap-1"><ShieldCheck className="h-3 w-3 text-on-surface-subtle" /> POD Status:</span>
              <span className={`font-semibold ${shipment.pod_verified ? "text-success" : "text-on-surface-muted"}`}>
                {shipment.pod_verified ? "Verified e-POD" : "Pending Delivery"}
              </span>
            </div>

            {!shipment.assigned_transporter_name && shipment.status !== "CANCELLED" && shipment.status !== "DELIVERED" && (
              <div className="pt-2">
                <Button
                  size="sm"
                  onClick={() => navigate(`/matching?shipment_id=${id}`)}
                  className="w-full text-xs bg-indigo-600 hover:bg-indigo-700 text-white gap-1.5 font-medium shadow-xs"
                >
                  <Sparkles className="h-3.5 w-3.5" />
                  Find Best Transporter
                </Button>
              </div>
            )}
          </CardContent>
        </Card>
      </div>

      {/* Special Instructions Alert if present */}
      {shipment.special_instructions && (
        <div className="p-4 bg-primary-container/70 border border-burnt-orange/30 rounded-xl flex items-start gap-3 text-xs text-blue-900">
          <Info className="h-4 w-4 text-primary shrink-0 mt-0.5" />
          <div>
            <span className="font-bold">Special Handling & Gate Instructions:</span> {shipment.special_instructions}
          </div>
        </div>
      )}

      {/* Tabs Section */}
      <Card className="bg-surface-card border-outline-variant shadow-xs overflow-hidden">
        <div className="flex border-b border-outline-variant bg-surface-container-low px-4">
          <button
            onClick={() => setActiveTab("timeline")}
            className={`py-3 px-4 text-xs font-semibold border-b-2 flex items-center gap-2 transition-colors ${
              activeTab === "timeline"
                ? "border-blue-600 text-primary bg-surface-card"
                : "border-transparent text-on-surface-muted hover:text-on-surface"
            }`}
          >
            <Activity className="h-3.5 w-3.5" />
            Milestone Timeline ({shipment.events.length})
          </button>

          <button
            onClick={() => setActiveTab("bookings")}
            className={`py-3 px-4 text-xs font-semibold border-b-2 flex items-center gap-2 transition-colors ${
              activeTab === "bookings"
                ? "border-blue-600 text-primary bg-surface-card"
                : "border-transparent text-on-surface-muted hover:text-on-surface"
            }`}
          >
            <Truck className="h-3.5 w-3.5" />
            Carrier Bookings ({shipment.bookings.length})
          </button>

          <button
            onClick={() => setActiveTab("exceptions")}
            className={`py-3 px-4 text-xs font-semibold border-b-2 flex items-center gap-2 transition-colors ${
              activeTab === "exceptions"
                ? "border-blue-600 text-primary bg-surface-card"
                : "border-transparent text-on-surface-muted hover:text-on-surface"
            }`}
          >
            <AlertTriangle className="h-3.5 w-3.5" />
            Exceptions ({shipment.exceptions.length})
          </button>

          <button
            onClick={() => setActiveTab("audit")}
            className={`py-3 px-4 text-xs font-semibold border-b-2 flex items-center gap-2 transition-colors ${
              activeTab === "audit"
                ? "border-blue-600 text-primary bg-surface-card"
                : "border-transparent text-on-surface-muted hover:text-on-surface"
            }`}
          >
            <History className="h-3.5 w-3.5" />
            Audit Trail ({shipment.audit_history.length})
          </button>

          <button
            onClick={() => setActiveTab("pod")}
            className={`py-3 px-4 text-xs font-semibold border-b-2 flex items-center gap-2 transition-colors ${
              activeTab === "pod"
                ? "border-blue-600 text-primary bg-surface-card"
                : "border-transparent text-on-surface-muted hover:text-on-surface"
            }`}
          >
            <CheckCircle2 className="h-3.5 w-3.5" />
            Proof of Delivery
          </button>
        </div>

        <CardContent className="p-6">
          {/* Tab 1: Milestone Timeline */}
          {activeTab === "timeline" && (
            <div className="space-y-4">
              {shipment.events.length === 0 ? (
                <div className="text-xs text-on-surface-muted py-6 text-center italic">
                  No milestone events recorded yet.
                </div>
              ) : (
                <div className="relative pl-6 border-l-2 border-outline-variant space-y-6">
                  {shipment.events.map((ev) => (
                    <div key={ev.id} className="relative group">
                      {/* Node Bullet */}
                      <div className="absolute -left-[31px] top-0.5 h-4 w-4 rounded-full border-2 border-blue-600 bg-surface-card flex items-center justify-center">
                        <div className="h-1.5 w-1.5 rounded-full bg-primary" />
                      </div>

                      <div className="bg-surface-container-low border border-outline-variant rounded-lg p-3">
                        <div className="flex items-center justify-between">
                          <span className="font-mono text-xs font-bold text-on-surface">
                            {ev.event_type.replace(/_/g, " ")}
                          </span>
                          <span className="text-[11px] text-on-surface-subtle font-mono">
                            {new Date(ev.occurred_at).toLocaleString()}
                          </span>
                        </div>
                        <div className="text-xs text-on-surface mt-1">{ev.description}</div>
                        <div className="flex items-center gap-3 mt-2 text-[11px] text-on-surface-muted">
                          {ev.location_name && <span>📍 {ev.location_name}</span>}
                          <span>Source: {ev.source}</span>
                        </div>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>
          )}

          {/* Tab 2: Carrier Bookings */}
          {activeTab === "bookings" && (
            <div className="space-y-3">
              {shipment.bookings.length === 0 ? (
                <div className="text-xs text-on-surface-muted py-6 text-center italic">
                  No carrier tenders or bookings created yet for this shipment.
                </div>
              ) : (
                <div className="overflow-x-auto">
                  <table className="w-full text-xs text-left">
                    <thead className="bg-surface-container-low text-on-surface-muted font-medium border-b border-outline-variant">
                      <tr>
                        <th className="py-2 px-3">Carrier Name</th>
                        <th className="py-2 px-3">Transporter Code</th>
                        <th className="py-2 px-3">Status</th>
                        <th className="py-2 px-3">Offered Rate</th>
                        <th className="py-2 px-3">Agreed Rate</th>
                        <th className="py-2 px-3">Created</th>
                        <th className="py-2 px-3 text-right">Action</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-outline-variant">
                      {shipment.bookings.map((b) => (
                        <tr key={b.id} className="hover:bg-surface-container-low/50">
                          <td className="py-2.5 px-3 font-semibold text-on-surface">{b.transporter_name}</td>
                          <td className="py-2.5 px-3 font-mono text-on-surface-muted">{b.transporter_code}</td>
                          <td className="py-2.5 px-3"><StatusBadge status={b.status} /></td>
                          <td className="py-2.5 px-3 font-mono">{b.offered_rate ? `$${b.offered_rate.toFixed(2)}` : "-"}</td>
                          <td className="py-2.5 px-3 font-mono font-semibold text-on-success-container">{b.agreed_rate ? `$${b.agreed_rate.toFixed(2)}` : "-"}</td>
                          <td className="py-2.5 px-3 text-on-surface-muted">{new Date(b.created_at).toLocaleDateString()}</td>
                          <td className="py-2.5 px-3 text-right">
                            <Link
                              to={`/bookings/${b.id}`}
                              className="text-xs font-semibold text-primary hover:text-burnt-orange hover:underline"
                            >
                              View Tender
                            </Link>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </div>
          )}

          {/* Tab 3: Exceptions */}
          {activeTab === "exceptions" && (
            <div className="space-y-3">
              {shipment.exceptions.length === 0 ? (
                <div className="text-xs text-on-surface-muted py-6 text-center italic">
                  No operational exceptions recorded for this shipment.
                </div>
              ) : (
                <div className="space-y-3">
                  {shipment.exceptions.map((ex) => (
                    <div key={ex.id} className="p-3.5 bg-critical-container/40 border border-rose-200 rounded-lg">
                      <div className="flex items-center justify-between">
                        <div className="flex items-center gap-2">
                          <AlertTriangle className="h-4 w-4 text-critical" />
                          <span className="font-semibold text-on-surface text-xs">{ex.title}</span>
                          <span className="text-[10px] bg-rose-100 text-rose-800 px-1.5 py-0.5 rounded font-mono font-bold">
                            {ex.severity}
                          </span>
                        </div>
                        <StatusBadge status={ex.status} />
                      </div>
                      <p className="text-xs text-on-surface mt-2">{ex.description}</p>
                      {ex.resolution_notes && (
                        <div className="mt-2 text-xs bg-surface-card p-2 rounded border border-emerald-200 text-emerald-800">
                          <span className="font-semibold">Resolution:</span> {ex.resolution_notes}
                        </div>
                      )}
                    </div>
                  ))}
                </div>
              )}
            </div>
          )}

          {/* Tab 4: Audit History */}
          {activeTab === "audit" && (
            <div className="space-y-3">
              {shipment.audit_history.length === 0 ? (
                <div className="text-xs text-on-surface-muted py-6 text-center italic">
                  No audit history records found.
                </div>
              ) : (
                <div className="overflow-x-auto">
                  <table className="w-full text-xs text-left">
                    <thead className="bg-surface-container-low text-on-surface-muted font-medium border-b border-outline-variant">
                      <tr>
                        <th className="py-2 px-3">Action</th>
                        <th className="py-2 px-3">Performed By</th>
                        <th className="py-2 px-3">Timestamp</th>
                        <th className="py-2 px-3">Field Changes</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-outline-variant">
                      {shipment.audit_history.map((a: ShipmentAuditLogItem) => (
                        <tr key={a.id} className="hover:bg-surface-container-low/50">
                          <td className="py-2.5 px-3 font-mono font-bold text-on-surface">{a.action}</td>
                          <td className="py-2.5 px-3 text-on-surface">{a.user_email || "System"}</td>
                          <td className="py-2.5 px-3 text-on-surface-muted font-mono">{new Date(a.performed_at).toLocaleString()}</td>
                          <td className="py-2.5 px-3 text-on-surface-muted max-w-md">
                            {a.new_values ? (
                              <pre className="text-[10px] bg-surface-container p-1.5 rounded overflow-x-auto max-h-24">
                                {JSON.stringify(a.new_values, null, 2)}
                              </pre>
                            ) : (
                              <span className="text-on-surface-subtle italic">No specific payload diff</span>
                            )}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </div>
          )}

          {/* Tab 5: Proof of Delivery */}
          {activeTab === "pod" && (
            <div>
              {shipment.pod_verified ? (
                <div className="p-4 bg-success-container border border-emerald-200 rounded-xl space-y-3">
                  <div className="flex items-center gap-2 text-emerald-800 font-bold text-sm">
                    <CheckCircle2 className="h-5 w-5 text-success" />
                    Electronic Proof of Delivery (e-POD) Confirmed
                  </div>
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-4 text-xs text-on-surface pt-2">
                    <div>
                      <span className="font-medium text-on-surface-muted">Signatory Consignee:</span>
                      <div className="font-semibold text-on-surface mt-0.5">{shipment.pod_signatory_name || "Authorized Consignee"}</div>
                    </div>
                    <div>
                      <span className="font-medium text-on-surface-muted">Signed At:</span>
                      <div className="font-mono text-on-surface mt-0.5">{shipment.pod_signed_at ? new Date(shipment.pod_signed_at).toLocaleString() : "Timestamp Recorded"}</div>
                    </div>
                  </div>
                  {shipment.pod_document_url && (
                    <div className="pt-2">
                      <Button
                        variant="outline"
                        size="sm"
                        onClick={() => window.open(shipment.pod_document_url!, "_blank")}
                        className="h-8 text-xs text-on-success-container border-emerald-300 hover:bg-emerald-100/50"
                      >
                        <Download className="h-3.5 w-3.5 mr-1" />
                        Download Signed Bill of Lading / e-POD Document
                      </Button>
                    </div>
                  )}
                </div>
              ) : (
                <div className="p-8 text-center bg-surface-container-low/50 rounded-xl border border-dashed border-outline-variant space-y-2">
                  <FileText className="h-8 w-8 text-on-surface-subtle mx-auto" />
                  <div className="text-sm font-semibold text-on-surface">Pending Consignee Signature</div>
                  <div className="text-xs text-on-surface-muted max-w-md mx-auto">
                    The driver will capture the receiver signature and upload electronic BOL document upon arrival at the destination dock.
                  </div>
                </div>
              )}
            </div>
          )}
        </CardContent>
      </Card>

      {/* Cancel Shipment Confirmation Dialog */}
      <ConfirmationDialog
        isOpen={cancelModalOpen}
        onClose={() => setCancelModalOpen(false)}
        onConfirm={handleConfirmCancel}
        title={`Cancel Shipment ${shipment.tracking_number}`}
        description="Are you sure you want to cancel this shipment? All active carrier bookings and pickup commitments will be invalidated. This action is permanently recorded in the audit history."
        confirmLabel="Cancel Shipment"
        variant="destructive"
        isLoading={cancelMutation.isPending}
      >
        <div className="mt-4 space-y-2">
          <label className="text-xs font-semibold text-on-surface">
            Cancellation Reason <span className="text-rose-500">*</span>
          </label>
          <textarea
            value={cancellationReason}
            onChange={(e) => setCancellationReason(e.target.value)}
            placeholder="Please specify a valid operational or customer reason for cancellation..."
            rows={3}
            className="w-full text-xs rounded-md border border-outline-variant p-2 text-on-surface focus:outline-hidden focus:ring-2 focus:ring-rose-500/20 focus:border-rose-500"
          />
        </div>
      </ConfirmationDialog>
    </div>
  );
};

export default ShipmentDetailPage;
