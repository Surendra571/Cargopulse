import React, { useState, useEffect, useRef } from "react";
import { useParams, Link, useNavigate } from "react-router-dom";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import {
  ArrowLeft,
  Radio,
  Clock,
  MapPin,
  Truck,
  Building2,
  UserCheck,
  Calendar,
  AlertTriangle,
  CheckCircle2,
  FileCheck2,
  Plus,
  Edit3,
} from "lucide-react";
import {
  trackingApi,
  ShipmentMilestone,
  TrackingEventSource,
} from "@/api/tracking";
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

const MILESTONES_LIST: { key: ShipmentMilestone; label: string }[] = [
  { key: "SHIPMENT_CREATED", label: "Shipment Created" },
  { key: "TRANSPORTER_ASSIGNED", label: "Transporter Assigned" },
  { key: "BOOKING_CONFIRMED", label: "Booking Confirmed" },
  { key: "VEHICLE_ASSIGNED", label: "Vehicle Assigned" },
  { key: "VEHICLE_ARRIVED", label: "Vehicle Arrived at Dock" },
  { key: "PICKUP_COMPLETED", label: "Pickup Completed & Loaded" },
  { key: "IN_TRANSIT", label: "In Transit" },
  { key: "CHECKPOINT_REACHED", label: "Route Checkpoint Reached" },
  { key: "OUT_FOR_DELIVERY", label: "Out for Delivery" },
  { key: "DELIVERED", label: "Consignment Delivered" },
];

export const TrackingDetailPage: React.FC = () => {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const { toast } = useToast();

  const [wsConnected, setWsConnected] = useState(false);
  const wsRef = useRef<WebSocket | null>(null);

  // Modals
  const [eventModalOpen, setEventModalOpen] = useState(false);
  const [selectedMilestone, setSelectedMilestone] = useState<ShipmentMilestone>("IN_TRANSIT");
  const [eventLocation, setEventLocation] = useState("");
  const [eventLatitude, setEventLatitude] = useState("");
  const [eventLongitude, setEventLongitude] = useState("");
  const [eventDescription, setEventDescription] = useState("");
  const [eventSource, setEventSource] = useState<TrackingEventSource>("OPERATOR");

  const [etaModalOpen, setEtaModalOpen] = useState(false);
  const [newEta, setNewEta] = useState("");
  const [etaReason, setEtaReason] = useState("");

  // Query Timeline & Shipment Details
  const { data: timeline, isLoading, error, refetch } = useQuery({
    queryKey: ["shipment-timeline", id],
    queryFn: () => trackingApi.getTimeline(id!),
    enabled: !!id,
  });

  // WebSocket Connection
  useEffect(() => {
    if (!id) return;

    let socket: WebSocket | null = null;
    let reconnectTimeout: any = null;

    const connectWs = () => {
      try {
        const url = trackingApi.getWebSocketUrl(id);
        socket = new WebSocket(url);
        wsRef.current = socket;

        socket.onopen = () => {
          setWsConnected(true);
        };

        socket.onmessage = (event) => {
          try {
            const data = JSON.parse(event.data);
            if (data.type === "TRACKING_EVENT_RECORDED" || data.type === "TRACKING_STALE_ALERT") {
              // Invalidate queries to refresh live timeline and badges
              queryClient.invalidateQueries({ queryKey: ["shipment-timeline", id] });
              queryClient.invalidateQueries({ queryKey: ["tracking-shipments"] });
              toast.info(
                "Live Telematics Update",
                `${data.event?.description || data.tracking_number}: ${data.status}`
              );
            }
          } catch (e) {
            console.error("Error parsing WebSocket event", e);
          }
        };

        socket.onclose = () => {
          setWsConnected(false);
          // Auto reconnect after 5s
          reconnectTimeout = setTimeout(connectWs, 5000);
        };

        socket.onerror = () => {
          setWsConnected(false);
        };
      } catch (err) {
        setWsConnected(false);
      }
    };

    connectWs();

    // Heartbeat keep-alive every 30s
    const pingInterval = setInterval(() => {
      if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN) {
        wsRef.current.send(JSON.stringify({ type: "PING" }));
      }
    }, 30000);

    return () => {
      clearInterval(pingInterval);
      if (reconnectTimeout) clearTimeout(reconnectTimeout);
      if (wsRef.current) {
        wsRef.current.close();
      }
    };
  }, [id, queryClient, toast]);

  // Mutations
  const recordEventMutation = useMutation({
    mutationFn: () =>
      trackingApi.recordEvent(id!, {
        milestone: selectedMilestone,
        location_name: eventLocation || undefined,
        latitude: eventLatitude ? parseFloat(eventLatitude) : undefined,
        longitude: eventLongitude ? parseFloat(eventLongitude) : undefined,
        description: eventDescription || undefined,
        source: eventSource,
      }),
    onSuccess: (res) => {
      toast.success("Event Recorded", `${res.description || res.event_type} logged.`);
      setEventModalOpen(false);
      resetEventForm();
      refetch();
      queryClient.invalidateQueries({ queryKey: ["tracking-shipments"] });
    },
    onError: (err: any) => {
      toast.error("Action Failed", err.response?.data?.detail || "Could not record tracking event");
    },
  });

  const updateEtaMutation = useMutation({
    mutationFn: () =>
      trackingApi.updateETA(id!, {
        new_eta: newEta,
        reason: etaReason || undefined,
      }),
    onSuccess: () => {
      toast.success("ETA Revised", "New expected delivery time recorded.");
      setEtaModalOpen(false);
      setNewEta("");
      setEtaReason("");
      refetch();
      queryClient.invalidateQueries({ queryKey: ["tracking-shipments"] });
    },
    onError: (err: any) => {
      toast.error("ETA Revision Failed", err.response?.data?.detail || "Could not update ETA");
    },
  });

  const resetEventForm = () => {
    setSelectedMilestone("IN_TRANSIT");
    setEventLocation("");
    setEventLatitude("");
    setEventLongitude("");
    setEventDescription("");
    setEventSource("OPERATOR");
  };

  if (isLoading) {
    return <LoadingState text="Connecting to telematics stream and timeline..." />;
  }

  if (error || !timeline) {
    return (
      <ErrorState
        title="Shipment Not Found"
        message="The requested shipment tracking timeline could not be loaded."
        onRetry={() => navigate("/tracking")}
      />
    );
  }

  // Map events to timeline format
  const timelineEvents: TimelineEvent[] = timeline.events.map((ev) => ({
    id: ev.id,
    title: ev.milestone ? ev.milestone.replace(/_/g, " ") : ev.event_type.replace(/_/g, " "),
    description: ev.description,
    timestamp: ev.occurred_at,
    actor: `${ev.source} ${ev.location_name ? `(${ev.location_name})` : ""}`,
    iconColor: ev.milestone === "DELIVERED"
      ? "emerald"
      : ev.milestone === "IN_TRANSIT" || ev.milestone === "CHECKPOINT_REACHED"
      ? "blue"
      : ev.event_type.includes("STALE") || ev.event_type.includes("DELAY")
      ? "rose"
      : "teal",
  }));

  return (
    <div className="space-y-6">
      {/* Page Header */}
      <PageHeader
        title={`Live Tracking: ${timeline.tracking_number}`}
        subtitle={`${timeline.origin.city}, ${timeline.origin.state} → ${timeline.destination.city}, ${timeline.destination.state} (${Math.round(timeline.total_weight_kg).toLocaleString()} kg)`}
        breadcrumbs={[
          { label: "Overview", href: "/overview" },
          { label: "Tracking", href: "/tracking" },
          { label: timeline.tracking_number },
        ]}
        actions={
          <div className="flex items-center gap-2">
            <Link to="/tracking">
              <Button variant="outline" size="sm">
                <ArrowLeft className="h-4 w-4 mr-1.5" />
                Back to Tracking Tower
              </Button>
            </Link>
          </div>
        }
      />

      {/* Real-time Status Banner */}
      <Card className="p-4 bg-surface-card text-white flex flex-wrap items-center justify-between gap-4">
        <div className="flex items-center gap-3">
          <StatusBadge status={timeline.status} />
          {timeline.current_milestone && (
            <span className="text-xs font-bold px-2.5 py-1 rounded-full bg-indigo-950 text-indigo-300 border border-indigo-700">
              {timeline.current_milestone.replace(/_/g, " ")}
            </span>
          )}

          {/* WebSocket Live Indicator */}
          <div className="flex items-center gap-1.5 ml-2">
            <span className={`h-2.5 w-2.5 rounded-full ${wsConnected ? "bg-emerald-400 animate-pulse" : "bg-amber-400"}`} />
            <span className="text-xs text-on-surface-muted font-mono">
              {wsConnected ? "Live WebSocket Stream" : "Reconnecting..."}
            </span>
          </div>

          {timeline.is_tracking_stale && (
            <span className="text-xs font-bold px-2 py-0.5 rounded bg-rose-950 text-rose-300 border border-rose-800 animate-pulse flex items-center gap-1">
              <AlertTriangle className="h-3 w-3" /> Stale Telemetry (&gt;6h)
            </span>
          )}
        </div>

        {/* Action Controls */}
        <div className="flex items-center gap-2">
          <Button
            size="sm"
            variant="outline"
            className="bg-surface-container border-outline-strong text-on-surface hover:bg-surface-container-high text-xs"
            onClick={() => {
              setNewEta(timeline.expected_delivery_time.slice(0, 16));
              setEtaReason("");
              setEtaModalOpen(true);
            }}
          >
            <Edit3 className="h-3.5 w-3.5 mr-1" />
            Update ETA
          </Button>

          <Button
            size="sm"
            variant="outline"
            className="bg-emerald-950 border-emerald-800 text-emerald-300 hover:bg-emerald-900 text-xs font-semibold"
            onClick={() => navigate(`/pod/review/${id}`)}
          >
            <FileCheck2 className="h-3.5 w-3.5 mr-1 text-emerald-400" />
            ePOD Review
          </Button>

          <Button
            size="sm"
            className="bg-primary hover:bg-burnt-orange text-white text-xs font-semibold"
            onClick={() => {
              resetEventForm();
              setEventModalOpen(true);
            }}
          >
            <Plus className="h-3.5 w-3.5 mr-1" />
            Record Milestone / Event
          </Button>
        </div>
      </Card>

      {/* 10-Milestone Progressive Roadmap */}
      <Card className="p-5 space-y-4">
        <h3 className="text-sm font-bold text-on-surface uppercase tracking-wider flex items-center gap-1.5">
          <Radio className="h-4 w-4 text-primary" />
          Shipment Milestone Roadmap
        </h3>

        <div className="grid grid-cols-2 sm:grid-cols-5 lg:grid-cols-10 gap-2">
          {timeline.milestone_progress.map((item, idx) => (
            <div
              key={item.milestone}
              className={`p-2.5 rounded-lg border flex flex-col justify-between text-xs transition-colors ${
                item.is_current
                  ? "bg-indigo-50 border-indigo-500 shadow-xs ring-1 ring-indigo-400"
                  : item.completed
                  ? "bg-success-container/60 border-emerald-300 text-emerald-950"
                  : "bg-surface-container-low border-outline-variant text-on-surface-subtle"
              }`}
            >
              <div>
                <div className="flex items-center justify-between mb-1">
                  <span className="font-mono text-[10px] font-bold text-on-surface-subtle">{idx + 1}</span>
                  {item.completed ? (
                    <CheckCircle2 className="h-3.5 w-3.5 text-success" />
                  ) : item.is_current ? (
                    <Radio className="h-3.5 w-3.5 text-indigo-600 animate-pulse" />
                  ) : (
                    <span className="h-2 w-2 rounded-full bg-slate-300" />
                  )}
                </div>
                <span className={`font-semibold text-[11px] leading-tight block ${item.is_current ? "text-indigo-900 font-bold" : ""}`}>
                  {item.label}
                </span>
              </div>

              {item.occurred_at && (
                <span className="text-[10px] text-on-surface-muted mt-2 block font-mono">
                  {new Date(item.occurred_at).toLocaleDateString([], { month: 'numeric', day: 'numeric' })}{" "}
                  {new Date(item.occurred_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                </span>
              )}
            </div>
          ))}
        </div>
      </Card>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Left 2 Columns: Chronological Event Timeline */}
        <div className="lg:col-span-2 space-y-6">
          <Card className="p-5 space-y-4">
            <div className="flex items-center justify-between border-b border-outline-variant pb-3">
              <h3 className="text-sm font-bold text-on-surface uppercase tracking-wider flex items-center gap-1.5">
                <Clock className="h-4 w-4 text-primary" />
                Chronological Event Timeline ({timeline.events.length} Events)
              </h3>
              <span className="text-xs text-on-surface-subtle font-mono">UTC Timestamped Log</span>
            </div>

            <ActivityTimeline events={timelineEvents} />
          </Card>
        </div>

        {/* Right Column: Telematics & Linked Parties */}
        <div className="space-y-6">
          {/* Last Reported Telemetry Card */}
          <Card className="p-4 space-y-3">
            <span className="text-xs font-bold text-on-surface uppercase tracking-wider flex items-center gap-1.5 border-b border-outline-variant pb-2">
              <MapPin className="h-4 w-4 text-primary" />
              Telematics &amp; Live Location
            </span>

            <div className="space-y-2 text-xs">
              <div>
                <span className="text-on-surface-subtle">Current Ground Location:</span>
                <p className="font-semibold text-on-surface flex items-center gap-1 mt-0.5">
                  <MapPin className="h-3.5 w-3.5 text-primary" />
                  {timeline.last_known_location || "Awaiting GPS Ping"}
                </p>
              </div>

              {timeline.last_known_latitude !== null && timeline.last_known_longitude !== null && (
                <div>
                  <span className="text-on-surface-subtle">Coordinates:</span>
                  <p className="font-mono text-on-surface">
                    {timeline.last_known_latitude?.toFixed(4)}, {timeline.last_known_longitude?.toFixed(4)}
                  </p>
                </div>
              )}

              <div>
                <span className="text-on-surface-subtle">Last Telemetry Ping:</span>
                <p className="text-on-surface">
                  {timeline.last_tracking_event_at
                    ? new Date(timeline.last_tracking_event_at).toLocaleString()
                    : "No ping recorded"}
                </p>
              </div>

              <div className="pt-2 border-t border-outline-variant">
                <span className="text-on-surface-subtle">Expected Delivery Time (ETA):</span>
                <p className="font-bold text-on-surface mt-0.5 flex items-center gap-1">
                  <Calendar className="h-3.5 w-3.5 text-on-surface-subtle" />
                  {new Date(timeline.expected_delivery_time).toLocaleString()}
                </p>
                {timeline.eta_delay_minutes > 0 ? (
                  <span className="text-critical font-bold text-[11px] block mt-0.5">
                    +{timeline.eta_delay_minutes} minutes schedule delay
                  </span>
                ) : (
                  <span className="text-success font-medium text-[11px] block mt-0.5">
                    Within delivery schedule
                  </span>
                )}
              </div>
            </div>
          </Card>

          {/* Assigned Transporter & Vehicle */}
          <Card className="p-4 space-y-3 text-xs">
            <span className="text-xs font-bold text-on-surface uppercase tracking-wider flex items-center gap-1.5 border-b border-outline-variant pb-2">
              <Building2 className="h-4 w-4 text-primary" />
              Carrier &amp; Equipment
            </span>

            <div className="space-y-2">
              <div>
                <span className="text-on-surface-subtle">Contracted Carrier:</span>
                <p className="font-bold text-on-surface">
                  {timeline.transporter?.name || "Carrier Pending"}
                </p>
              </div>

              <div>
                <span className="text-on-surface-subtle">Assigned Vehicle Plate:</span>
                <p className="font-mono font-semibold text-on-surface flex items-center gap-1">
                  <Truck className="h-3.5 w-3.5 text-on-surface-subtle" />
                  {timeline.assigned_vehicle?.license_plate || "Plate Pending"}
                </p>
              </div>

              <div>
                <span className="text-on-surface-subtle">Assigned Driver:</span>
                <p className="font-semibold text-on-surface flex items-center gap-1">
                  <UserCheck className="h-3.5 w-3.5 text-on-surface-subtle" />
                  {timeline.assigned_driver?.name || "Driver Pending"}
                </p>
                {timeline.assigned_driver?.phone && (
                  <span className="text-on-surface-muted text-[11px] font-mono">
                    {timeline.assigned_driver.phone}
                  </span>
                )}
              </div>
            </div>
          </Card>

          {/* Lane Route Details */}
          <Card className="p-4 space-y-3 text-xs">
            <span className="text-xs font-bold text-on-surface uppercase tracking-wider flex items-center gap-1.5 border-b border-outline-variant pb-2">
              <MapPin className="h-4 w-4 text-primary" />
              Consignment Lane
            </span>

            <div className="space-y-3">
              <div>
                <span className="text-on-surface-subtle block font-semibold">Origin Facility</span>
                <p className="text-on-surface font-medium">{timeline.origin.name}</p>
                <p className="text-on-surface-muted">
                  {timeline.origin.city}, {timeline.origin.state} {timeline.origin.postal_code}
                </p>
              </div>
              <div>
                <span className="text-on-surface-subtle block font-semibold">Destination Facility</span>
                <p className="text-on-surface font-medium">{timeline.destination.name}</p>
                <p className="text-on-surface-muted">
                  {timeline.destination.city}, {timeline.destination.state} {timeline.destination.postal_code}
                </p>
              </div>
            </div>
          </Card>
        </div>
      </div>

      {/* Record Milestone / Event Modal */}
      <ConfirmationDialog
        isOpen={eventModalOpen}
        onClose={() => setEventModalOpen(false)}
        onConfirm={() => recordEventMutation.mutate()}
        title="Record Live Milestone / Telematics Event"
        description="Append a verified operational milestone or location update into the shipment audit ledger and broadcast in real-time."
        confirmLabel="Record Event"
        isLoading={recordEventMutation.isPending}
      >
        <div className="space-y-3 mt-3 max-h-[60vh] overflow-y-auto pr-1">
          <div>
            <label className="text-xs font-semibold text-on-surface">Milestone *</label>
            <select
              value={selectedMilestone}
              onChange={(e) => setSelectedMilestone(e.target.value as ShipmentMilestone)}
              className="w-full mt-1 text-xs border rounded-md p-1.5 bg-surface-card border-outline-variant"
            >
              {MILESTONES_LIST.map((m) => (
                <option key={m.key} value={m.key}>
                  {m.label}
                </option>
              ))}
            </select>
          </div>

          <div>
            <label className="text-xs font-semibold text-on-surface">Location Name / Toll Plaza / Dock</label>
            <Input
              value={eventLocation}
              onChange={(e) => setEventLocation(e.target.value)}
              placeholder="e.g. Exit 42 Toll Plaza, Columbus Hub"
              className="mt-1 text-xs"
            />
          </div>

          <div className="grid grid-cols-2 gap-2">
            <div>
              <label className="text-xs font-semibold text-on-surface">Latitude (Optional)</label>
              <Input
                type="number"
                step="any"
                value={eventLatitude}
                onChange={(e) => setEventLatitude(e.target.value)}
                placeholder="39.9612"
                className="mt-1 text-xs font-mono"
              />
            </div>
            <div>
              <label className="text-xs font-semibold text-on-surface">Longitude (Optional)</label>
              <Input
                type="number"
                step="any"
                value={eventLongitude}
                onChange={(e) => setEventLongitude(e.target.value)}
                placeholder="-82.9988"
                className="mt-1 text-xs font-mono"
              />
            </div>
          </div>

          <div className="grid grid-cols-2 gap-2">
            <div>
              <label className="text-xs font-semibold text-on-surface">Event Source *</label>
              <select
                value={eventSource}
                onChange={(e) => setEventSource(e.target.value as TrackingEventSource)}
                className="w-full mt-1 text-xs border rounded-md p-1.5 bg-surface-card border-outline-variant"
              >
                <option value="OPERATOR">Operator / Dispatcher</option>
                <option value="TRANSPORTER">Transporter</option>
                <option value="DRIVER">Driver</option>
                <option value="TELEMATICS">Telematics GPS</option>
                <option value="WEBHOOK">Webhook</option>
              </select>
            </div>
          </div>

          <div>
            <label className="text-xs font-semibold text-on-surface">Event Description / Notes</label>
            <Input
              value={eventDescription}
              onChange={(e) => setEventDescription(e.target.value)}
              placeholder="e.g. Cleared security checkpoint, moving on schedule"
              className="mt-1 text-xs"
            />
          </div>
        </div>
      </ConfirmationDialog>

      {/* Update ETA Modal */}
      <ConfirmationDialog
        isOpen={etaModalOpen}
        onClose={() => setEtaModalOpen(false)}
        onConfirm={() => {
          if (!newEta) {
            toast.error("ETA Required", "Please select a revised delivery date and time.");
            return;
          }
          updateEtaMutation.mutate();
        }}
        title="Update Expected Delivery Time (ETA)"
        description="Revise the operational ETA supplied by the carrier or driver. Any delay exceeding 60 minutes will automatically log an SLA exception."
        confirmLabel="Save ETA"
        isLoading={updateEtaMutation.isPending}
      >
        <div className="space-y-3 mt-3">
          <div>
            <label className="text-xs font-semibold text-on-surface">Revised Expected Delivery Time *</label>
            <Input
              type="datetime-local"
              value={newEta}
              onChange={(e) => setNewEta(e.target.value)}
              className="mt-1 text-xs font-mono"
            />
          </div>

          <div>
            <label className="text-xs font-semibold text-on-surface">Operational Delay Reason (Optional)</label>
            <Input
              value={etaReason}
              onChange={(e) => setEtaReason(e.target.value)}
              placeholder="e.g. Highway construction detour, heavy rain slowing transit"
              className="mt-1 text-xs"
            />
          </div>
        </div>
      </ConfirmationDialog>
    </div>
  );
};
