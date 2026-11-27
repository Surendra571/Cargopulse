import React, { useState } from "react";
import { useParams, useNavigate } from "react-router-dom";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import {
  ArrowLeft,
  Phone,
  MapPin,
  Truck,
  Users,
  ShieldCheck,
  ShieldAlert,
  FileText,
  Clock,
  Plus,
  Trash2,
  ExternalLink,
  AlertTriangle,
  X,
} from "lucide-react";
import {
  getTransporter,
  verifyTransporter,
  suspendTransporter,
  uploadTransporterDocument,
  addTransporterServiceArea,
  createVehicle,
  createDriver,
  deleteVehicle,
  deleteDriver,
  assignDriverToVehicle,
  VehicleListItem,
  DriverListItem,
  VehicleCreatePayload,
  DriverCreatePayload,
  DocumentUploadPayload,
  ServiceAreaCreatePayload,
} from "@/api/transporters";
import { PageHeader } from "@/components/common/PageHeader";
import { StatusBadge } from "@/components/common/StatusBadge";
import { DataTable, ColumnDef } from "@/components/common/DataTable";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { ConfirmationDialog } from "@/components/common/ConfirmationDialog";
import { useToast } from "@/context/ToastContext";

export const TransporterDetailPage: React.FC = () => {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const { toast } = useToast();

  const [activeTab, setActiveTab] = useState<"fleet" | "drivers" | "lanes" | "bookings" | "docs">("fleet");

  // Modals state
  const [verifyModalOpen, setVerifyModalOpen] = useState(false);
  const [verificationTargetStatus, setVerificationTargetStatus] = useState<any>("VERIFIED");
  const [verificationNotes, setVerificationNotes] = useState("");

  const [suspendModalOpen, setSuspendModalOpen] = useState(false);
  const [suspendReason, setSuspendReason] = useState("");

  const [addVehicleOpen, setAddVehicleOpen] = useState(false);
  const [vehicleForm, setVehicleForm] = useState<Omit<VehicleCreatePayload, "transporter_id">>({
    license_plate: "",
    vehicle_type: "53' Dry Van",
    capacity_kg: 20000,
    volume_cbm: 90,
    rc_number: "",
    insurance_expiry: "",
    fitness_expiry: "",
    telematics_device_id: "",
    is_available: true,
  });

  const [addDriverOpen, setAddDriverOpen] = useState(false);
  const [driverForm, setDriverForm] = useState<Omit<DriverCreatePayload, "transporter_id">>({
    first_name: "",
    last_name: "",
    phone: "",
    license_number: "",
    license_expiry: "",
    is_available: true,
    assigned_vehicle_id: undefined,
  });

  const [addDocOpen, setAddDocOpen] = useState(false);
  const [docForm, setDocForm] = useState<DocumentUploadPayload>({
    doc_type: "MOTOR_CARRIER_PERMIT",
    document_number: "",
    file_url: "",
    expiry_date: "",
  });

  const [addLaneOpen, setAddLaneOpen] = useState(false);
  const [laneForm, setLaneForm] = useState<ServiceAreaCreatePayload>({
    origin_region: "",
    destination_region: "",
    estimated_transit_hours: 24,
  });

  const [assignModalOpen, setAssignModalOpen] = useState(false);
  const [selectedDriverForAssign, setSelectedDriverForAssign] = useState<DriverListItem | null>(null);
  const [selectedVehicleIdToAssign, setSelectedVehicleIdToAssign] = useState<string>("");

  const { data: carrier, isLoading } = useQuery({
    queryKey: ["transporter", id],
    queryFn: () => getTransporter(id!),
    enabled: !!id,
  });

  const verifyMutation = useMutation({
    mutationFn: ({ status, notes }: { status: any; notes: string }) =>
      verifyTransporter(id!, { status, verification_notes: notes }),
    onSuccess: (updated) => {
      toast.success("Verification Updated", `Status is now ${updated.verification_status}.`);
      queryClient.invalidateQueries({ queryKey: ["transporter", id] });
      queryClient.invalidateQueries({ queryKey: ["transporters"] });
      setVerifyModalOpen(false);
    },
    onError: (err: any) => {
      toast.error("Verification Error", err.response?.data?.detail || "Could not update status.");
    },
  });

  const suspendMutation = useMutation({
    mutationFn: (reason: string) => suspendTransporter(id!, reason),
    onSuccess: () => {
      toast.warning("Carrier Suspended", "Carrier has been suspended from active bookings.");
      queryClient.invalidateQueries({ queryKey: ["transporter", id] });
      queryClient.invalidateQueries({ queryKey: ["transporters"] });
      setSuspendModalOpen(false);
    },
    onError: (err: any) => {
      toast.error("Suspension Error", err.response?.data?.detail || "Could not suspend carrier.");
    },
  });

  const createVehicleMutation = useMutation({
    mutationFn: (payload: VehicleCreatePayload) => createVehicle(payload),
    onSuccess: (v) => {
      toast.success("Vehicle Added", `Registered vehicle ${v.license_plate} to carrier fleet.`);
      queryClient.invalidateQueries({ queryKey: ["transporter", id] });
      setAddVehicleOpen(false);
      setVehicleForm({
        license_plate: "",
        vehicle_type: "53' Dry Van",
        capacity_kg: 20000,
        volume_cbm: 90,
        rc_number: "",
        insurance_expiry: "",
        fitness_expiry: "",
        telematics_device_id: "",
        is_available: true,
      });
    },
    onError: (err: any) => {
      toast.error("Vehicle Error", err.response?.data?.detail || "Could not register vehicle.");
    },
  });

  const createDriverMutation = useMutation({
    mutationFn: (payload: DriverCreatePayload) => createDriver(payload),
    onSuccess: (d) => {
      toast.success("Driver Added", `Registered driver ${d.full_name}.`);
      queryClient.invalidateQueries({ queryKey: ["transporter", id] });
      setAddDriverOpen(false);
      setDriverForm({
        first_name: "",
        last_name: "",
        phone: "",
        license_number: "",
        license_expiry: "",
        is_available: true,
        assigned_vehicle_id: undefined,
      });
    },
    onError: (err: any) => {
      toast.error("Driver Error", err.response?.data?.detail || "Could not register driver.");
    },
  });

  const uploadDocMutation = useMutation({
    mutationFn: (payload: DocumentUploadPayload) => uploadTransporterDocument(id!, payload),
    onSuccess: () => {
      toast.success("Document Uploaded", "Compliance certification recorded.");
      queryClient.invalidateQueries({ queryKey: ["transporter", id] });
      setAddDocOpen(false);
      setDocForm({
        doc_type: "MOTOR_CARRIER_PERMIT",
        document_number: "",
        file_url: "",
        expiry_date: "",
      });
    },
    onError: (err: any) => {
      toast.error("Upload Error", err.response?.data?.detail || "Could not upload document.");
    },
  });

  const addLaneMutation = useMutation({
    mutationFn: (payload: ServiceAreaCreatePayload) => addTransporterServiceArea(id!, payload),
    onSuccess: () => {
      toast.success("Corridor Added", "New operating lane mapped.");
      queryClient.invalidateQueries({ queryKey: ["transporter", id] });
      setAddLaneOpen(false);
      setLaneForm({
        origin_region: "",
        destination_region: "",
        estimated_transit_hours: 24,
      });
    },
    onError: (err: any) => {
      toast.error("Corridor Error", err.response?.data?.detail || "Could not add lane.");
    },
  });

  const assignDriverMutation = useMutation({
    mutationFn: ({ driverId, vehicleId }: { driverId: string; vehicleId: string | null }) =>
      assignDriverToVehicle(driverId, vehicleId),
    onSuccess: (d) => {
      toast.success("Vehicle Assigned", `Driver ${d.full_name} assigned.`);
      queryClient.invalidateQueries({ queryKey: ["transporter", id] });
      setAssignModalOpen(false);
      setSelectedDriverForAssign(null);
    },
    onError: (err: any) => {
      toast.error("Assignment Failed", err.response?.data?.detail || "Could not assign vehicle.");
    },
  });

  const deleteVehicleMutation = useMutation({
    mutationFn: (vehicleId: string) => deleteVehicle(vehicleId),
    onSuccess: () => {
      toast.success("Vehicle Removed", "Vehicle deleted from fleet.");
      queryClient.invalidateQueries({ queryKey: ["transporter", id] });
    },
    onError: (err: any) => {
      toast.error("Delete Failed", err.response?.data?.detail || "Could not delete vehicle.");
    },
  });

  const deleteDriverMutation = useMutation({
    mutationFn: (driverId: string) => deleteDriver(driverId),
    onSuccess: () => {
      toast.success("Driver Removed", "Driver deleted from carrier roster.");
      queryClient.invalidateQueries({ queryKey: ["transporter", id] });
    },
    onError: (err: any) => {
      toast.error("Delete Failed", err.response?.data?.detail || "Could not delete driver.");
    },
  });

  if (isLoading) {
    return (
      <div className="flex items-center justify-center min-h-[400px]">
        <div className="text-center space-y-3">
          <div className="w-8 h-8 border-2 border-primary border-t-transparent rounded-full animate-spin mx-auto" />
          <p className="text-xs text-on-surface-muted">Loading carrier profile...</p>
        </div>
      </div>
    );
  }

  if (!carrier) {
    return (
      <div className="text-center py-12 space-y-4">
        <AlertTriangle className="w-12 h-12 text-rose-500 mx-auto" />
        <h3 className="text-lg font-bold text-on-surface">Transporter Not Found</h3>
        <p className="text-sm text-on-surface-muted">The requested carrier partner could not be located in your organization.</p>
        <Button onClick={() => navigate("/transporters")} variant="outline">
          Back to Carriers
        </Button>
      </div>
    );
  }

  const vehicleColumns: ColumnDef<VehicleListItem>[] = [
    {
      id: "license_plate",
      header: "License Plate",
      cell: (v) => (
        <div className="font-mono font-bold text-on-surface flex items-center gap-1.5">
          <Truck className="w-4 h-4 text-on-surface-muted" />
          {v.license_plate}
        </div>
      ),
    },
    {
      id: "vehicle_type",
      header: "Type & Capacity",
      cell: (v) => (
        <div className="text-xs">
          <p className="font-semibold text-on-surface">{v.vehicle_type}</p>
          <p className="text-on-surface-muted">{v.capacity_kg.toLocaleString()} kg max capacity</p>
        </div>
      ),
    },
    {
      id: "status",
      header: "Status",
      cell: (v) => (
        <div className="flex flex-col gap-1 items-start">
          <StatusBadge status={v.status} size="sm" />
          {v.has_expired_documents && (
            <span className="text-[10px] bg-critical-container text-on-critical-container px-1 py-0.5 rounded font-bold border border-rose-200">
              Expired Insurance / Fitness
            </span>
          )}
        </div>
      ),
    },
    {
      id: "assigned_driver_name",
      header: "Assigned Driver",
      cell: (v) => (
        <div className="text-xs text-on-surface">
          {v.assigned_driver_name ? (
            <span className="font-medium text-on-surface flex items-center gap-1">
              <Users className="w-3.5 h-3.5 text-success" />
              {v.assigned_driver_name}
            </span>
          ) : (
            <span className="text-on-surface-subtle italic">Unassigned</span>
          )}
        </div>
      ),
    },
    {
      id: "telematics_device_id",
      header: "Telematics / GPS",
      cell: (v) => (
        <span className="text-xs font-mono text-on-surface-muted">
          {v.telematics_device_id || "No telematics paired"}
        </span>
      ),
    },
    {
      id: "actions",
      header: "Actions",
      cell: (v) => (
        <Button
          variant="ghost"
          size="sm"
          onClick={() => {
            if (confirm(`Remove vehicle ${v.license_plate} from fleet?`)) {
              deleteVehicleMutation.mutate(v.id);
            }
          }}
          className="h-8 px-2 text-critical hover:bg-critical-container"
        >
          <Trash2 className="w-4 h-4" />
        </Button>
      ),
    },
  ];

  const driverColumns: ColumnDef<DriverListItem>[] = [
    {
      id: "full_name",
      header: "Driver Name",
      cell: (d) => (
        <div>
          <p className="font-semibold text-on-surface">{d.full_name}</p>
          <p className="text-xs text-on-surface-muted flex items-center gap-1 mt-0.5">
            <Phone className="w-3 h-3 text-on-surface-subtle" />
            {d.phone}
          </p>
        </div>
      ),
    },
    {
      id: "license_number_masked",
      header: "License Number",
      cell: (d) => (
        <div className="text-xs">
          <p className="font-mono font-semibold text-on-surface">{d.license_number_masked}</p>
          {d.is_license_expired ? (
            <span className="text-[10px] text-on-critical-container bg-critical-container font-bold px-1.5 py-0.5 rounded border border-rose-200">
              Expired License
            </span>
          ) : d.license_expiry ? (
            <span className="text-[11px] text-on-surface-subtle">
              Exp: {new Date(d.license_expiry).toLocaleDateString()}
            </span>
          ) : null}
        </div>
      ),
    },
    {
      id: "status",
      header: "Status",
      cell: (d) => <StatusBadge status={d.status} size="sm" />,
    },
    {
      id: "assigned_vehicle_plate",
      header: "Assigned Vehicle",
      cell: (d) => (
        <div className="text-xs">
          {d.assigned_vehicle_plate ? (
            <span className="font-mono font-bold text-on-surface bg-surface-container px-2 py-0.5 rounded">
              {d.assigned_vehicle_plate}
            </span>
          ) : (
            <span className="text-on-surface-subtle italic">No vehicle assigned</span>
          )}
        </div>
      ),
    },
    {
      id: "actions",
      header: "Actions",
      cell: (d) => (
        <div className="flex items-center gap-1.5">
          <Button
            variant="outline"
            size="sm"
            onClick={() => {
              setSelectedDriverForAssign(d);
              setSelectedVehicleIdToAssign(d.assigned_vehicle_id || "");
              setAssignModalOpen(true);
            }}
            className="h-8 px-2 text-xs text-on-success-container border-teal-200 hover:bg-success-container"
          >
            Assign Vehicle
          </Button>
          <Button
            variant="ghost"
            size="sm"
            onClick={() => {
              if (confirm(`Remove driver ${d.full_name}?`)) {
                deleteDriverMutation.mutate(d.id);
              }
            }}
            className="h-8 px-2 text-critical hover:bg-critical-container"
          >
            <Trash2 className="w-4 h-4" />
          </Button>
        </div>
      ),
    },
  ];

  return (
    <div className="space-y-6">
      {/* Back button & Header */}
      <div>
        <button
          onClick={() => navigate("/transporters")}
          className="inline-flex items-center gap-1.5 text-xs font-semibold text-on-surface-muted hover:text-on-surface transition-colors mb-2"
        >
          <ArrowLeft className="w-3.5 h-3.5" />
          Back to Carrier Network
        </button>

        <PageHeader
          title={carrier.name}
          badge={
            <div className="flex items-center gap-2">
              <span className="text-xs font-mono text-on-surface-muted bg-surface-container px-2 py-0.5 rounded border border-outline-variant">
                {carrier.code}
              </span>
              <StatusBadge status={carrier.verification_status} size="sm" />
              {!carrier.is_active && (
                <span className="text-xs uppercase font-bold text-critical bg-critical-container px-2 py-0.5 rounded border border-rose-200">
                  Suspended / Inactive
                </span>
              )}
            </div>
          }
          subtitle={`Onboarded on ${new Date(carrier.created_at).toLocaleDateString()} • Dispatch: ${carrier.phone} ${
            carrier.email ? `• ${carrier.email}` : ""
          }`}
          actions={
            <div className="flex items-center gap-2">
              <Button
                variant="outline"
                size="sm"
                onClick={() => setVerifyModalOpen(true)}
                className="gap-1.5 text-on-success-container border-teal-200 hover:bg-success-container"
              >
                <ShieldCheck className="w-4 h-4" />
                Verification Status
              </Button>
              {carrier.verification_status !== "SUSPENDED" && (
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => setSuspendModalOpen(true)}
                  className="gap-1.5 text-on-critical-container border-rose-200 hover:bg-critical-container"
                >
                  <ShieldAlert className="w-4 h-4" />
                  Suspend Carrier
                </Button>
              )}
            </div>
          }
        />
      </div>

      {/* KPI Stats Ribbon */}
      <div className="grid grid-cols-2 md:grid-cols-5 gap-4">
        <Card className="p-3.5 border-outline-variant">
          <p className="text-[11px] font-semibold text-on-surface-muted uppercase tracking-wider">Reliability Score</p>
          <div className="flex items-center gap-2 mt-1">
            <span className="text-2xl font-bold text-on-surface">{carrier.performance.reliability_score.toFixed(1)}%</span>
            <div className="w-12 bg-surface-container h-1.5 rounded-full overflow-hidden">
              <div
                className={`h-full rounded-full ${
                  carrier.performance.reliability_score >= 90
                    ? "bg-success-container0"
                    : carrier.performance.reliability_score >= 75
                    ? "bg-warning-container0"
                    : "bg-critical-container0"
                }`}
                style={{ width: `${Math.min(100, carrier.performance.reliability_score)}%` }}
              />
            </div>
          </div>
          <p className="text-[10px] text-on-surface-subtle mt-0.5">Historical fulfillment</p>
        </Card>

        <Card className="p-3.5 border-outline-variant">
          <p className="text-[11px] font-semibold text-on-surface-muted uppercase tracking-wider">On-Time Rate</p>
          <h3 className="text-2xl font-bold text-success mt-1">
            {carrier.performance.on_time_rate.toFixed(0)}%
          </h3>
          <p className="text-[10px] text-on-surface-subtle mt-0.5">
            {carrier.performance.on_time_deliveries} / {carrier.performance.total_deliveries} deliveries
          </p>
        </Card>

        <Card className="p-3.5 border-outline-variant">
          <p className="text-[11px] font-semibold text-on-surface-muted uppercase tracking-wider">Fleet Vehicles</p>
          <h3 className="text-2xl font-bold text-primary mt-1">{carrier.vehicles.length}</h3>
          <p className="text-[10px] text-on-surface-subtle mt-0.5">
            {carrier.vehicles.filter((v) => v.is_available).length} available for load
          </p>
        </Card>

        <Card className="p-3.5 border-outline-variant">
          <p className="text-[11px] font-semibold text-on-surface-muted uppercase tracking-wider">Commercial Drivers</p>
          <h3 className="text-2xl font-bold text-indigo-600 mt-1">{carrier.drivers.length}</h3>
          <p className="text-[10px] text-on-surface-subtle mt-0.5">
            {carrier.drivers.filter((d) => d.is_available).length} on duty / ready
          </p>
        </Card>

        <Card className="p-3.5 border-outline-variant">
          <p className="text-[11px] font-semibold text-on-surface-muted uppercase tracking-wider">Accepted Bookings</p>
          <h3 className="text-2xl font-bold text-on-surface mt-1">
            {carrier.performance.accepted_bookings_count}
          </h3>
          <p className="text-[10px] text-on-surface-subtle mt-0.5">
            {carrier.performance.active_exceptions} active exceptions
          </p>
        </Card>
      </div>

      {/* Navigation Tabs */}
      <div className="border-b border-outline-variant flex items-center gap-6 text-sm font-semibold text-on-surface-muted">
        <button
          onClick={() => setActiveTab("fleet")}
          className={`pb-3 flex items-center gap-2 border-b-2 transition-colors ${
            activeTab === "fleet"
              ? "border-primary text-primary"
              : "border-transparent text-on-surface-muted hover:text-on-surface"
          }`}
        >
          <Truck className="w-4 h-4" />
          Fleet Vehicles ({carrier.vehicles.length})
        </button>

        <button
          onClick={() => setActiveTab("drivers")}
          className={`pb-3 flex items-center gap-2 border-b-2 transition-colors ${
            activeTab === "drivers"
              ? "border-primary text-primary"
              : "border-transparent text-on-surface-muted hover:text-on-surface"
          }`}
        >
          <Users className="w-4 h-4" />
          Commercial Drivers ({carrier.drivers.length})
        </button>

        <button
          onClick={() => setActiveTab("lanes")}
          className={`pb-3 flex items-center gap-2 border-b-2 transition-colors ${
            activeTab === "lanes"
              ? "border-primary text-primary"
              : "border-transparent text-on-surface-muted hover:text-on-surface"
          }`}
        >
          <MapPin className="w-4 h-4" />
          Operating Corridors ({carrier.service_areas.length})
        </button>

        <button
          onClick={() => setActiveTab("bookings")}
          className={`pb-3 flex items-center gap-2 border-b-2 transition-colors ${
            activeTab === "bookings"
              ? "border-primary text-primary"
              : "border-transparent text-on-surface-muted hover:text-on-surface"
          }`}
        >
          <Clock className="w-4 h-4" />
          Recent Bookings ({carrier.recent_bookings.length})
        </button>

        <button
          onClick={() => setActiveTab("docs")}
          className={`pb-3 flex items-center gap-2 border-b-2 transition-colors ${
            activeTab === "docs"
              ? "border-primary text-primary"
              : "border-transparent text-on-surface-muted hover:text-on-surface"
          }`}
        >
          <FileText className="w-4 h-4" />
          Compliance Documents ({carrier.documents.length})
        </button>
      </div>

      {/* Tab 1: Fleet Vehicles */}
      {activeTab === "fleet" && (
        <div className="space-y-4">
          <div className="flex items-center justify-between">
            <div>
              <h4 className="text-sm font-bold text-on-surface">Registered Fleet Equipment</h4>
              <p className="text-xs text-on-surface-muted">Commercial vehicles mapped for dispatch assignment.</p>
            </div>
            <Button
              size="sm"
              onClick={() => setAddVehicleOpen(true)}
              className="gap-1.5 bg-primary hover:bg-primary/90 text-white"
            >
              <Plus className="w-4 h-4" />
              Register Vehicle
            </Button>
          </div>

          <DataTable
            columns={vehicleColumns}
            data={carrier.vehicles}
            keyExtractor={(v) => v.id}
            isLoading={false}
            emptyTitle="No Vehicles Registered"
            emptyDescription="No commercial vehicles registered for this carrier yet. Click 'Register Vehicle' to add fleet equipment."
          />
        </div>
      )}

      {/* Tab 2: Commercial Drivers */}
      {activeTab === "drivers" && (
        <div className="space-y-4">
          <div className="flex items-center justify-between">
            <div>
              <h4 className="text-sm font-bold text-on-surface">Commercial Driver Roster</h4>
              <p className="text-xs text-on-surface-muted">Commercial drivers certified for freight transit.</p>
            </div>
            <Button
              size="sm"
              onClick={() => setAddDriverOpen(true)}
              className="gap-1.5 bg-primary hover:bg-primary/90 text-white"
            >
              <Plus className="w-4 h-4" />
              Register Driver
            </Button>
          </div>

          <DataTable
            columns={driverColumns}
            data={carrier.drivers}
            keyExtractor={(d) => d.id}
            isLoading={false}
            emptyTitle="No Drivers Registered"
            emptyDescription="No commercial drivers registered for this carrier yet. Click 'Register Driver' to add roster personnel."
          />
        </div>
      )}

      {/* Tab 3: Operating Corridors */}
      {activeTab === "lanes" && (
        <div className="space-y-4">
          <div className="flex items-center justify-between">
            <div>
              <h4 className="text-sm font-bold text-on-surface">Operating Lanes & Corridors</h4>
              <p className="text-xs text-on-surface-muted">Origin-destination regions and estimated transit turnaround.</p>
            </div>
            <Button
              size="sm"
              onClick={() => setAddLaneOpen(true)}
              className="gap-1.5 bg-primary hover:bg-primary/90 text-white"
            >
              <Plus className="w-4 h-4" />
              Add Corridor
            </Button>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            {carrier.service_areas.map((lane) => (
              <Card key={lane.id} className="p-4 border-outline-variant space-y-2">
                <div className="flex items-center justify-between text-xs text-on-surface-muted font-semibold uppercase">
                  <span>Corridor</span>
                  <span className="text-on-success-container bg-success-container px-1.5 py-0.5 rounded font-bold">
                    ~{lane.estimated_transit_hours} hrs transit
                  </span>
                </div>
                <div className="flex items-center gap-2 text-sm font-bold text-on-surface">
                  <MapPin className="w-4 h-4 text-primary shrink-0" />
                  <span>{lane.origin_region}</span>
                  <span className="text-on-surface-subtle font-normal">→</span>
                  <span>{lane.destination_region}</span>
                </div>
                <p className="text-[11px] text-on-surface-subtle">
                  Mapped on {new Date(lane.created_at).toLocaleDateString()}
                </p>
              </Card>
            ))}

            {carrier.service_areas.length === 0 && (
              <div className="col-span-3 text-center py-8 text-xs text-on-surface-subtle italic">
                No specific corridors defined. Carrier is eligible for broad regional dispatch.
              </div>
            )}
          </div>
        </div>
      )}

      {/* Tab 4: Recent Bookings */}
      {activeTab === "bookings" && (
        <div className="space-y-4">
          <div>
            <h4 className="text-sm font-bold text-on-surface">Recent Shipment Bookings</h4>
            <p className="text-xs text-on-surface-muted">History of dispatch requests and accepted haul assignments.</p>
          </div>

          <div className="border border-outline-variant rounded-lg overflow-hidden">
            <table className="w-full text-left text-xs text-on-surface">
              <thead className="bg-surface-container-low text-on-surface-muted font-semibold border-b border-outline-variant">
                <tr>
                  <th className="py-2.5 px-4">Shipment Tracking #</th>
                  <th className="py-2.5 px-4">Origin</th>
                  <th className="py-2.5 px-4">Destination</th>
                  <th className="py-2.5 px-4">Status</th>
                  <th className="py-2.5 px-4">Agreed Rate</th>
                  <th className="py-2.5 px-4">Booked At</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-outline-variant">
                {carrier.recent_bookings.map((b) => (
                  <tr key={b.id} className="hover:bg-surface-container-low/60">
                    <td className="py-2.5 px-4 font-mono font-bold text-primary">
                      {b.shipment_tracking_number}
                    </td>
                    <td className="py-2.5 px-4">{b.origin_summary}</td>
                    <td className="py-2.5 px-4">{b.destination_summary}</td>
                    <td className="py-2.5 px-4">
                      <StatusBadge status={b.status} size="sm" />
                    </td>
                    <td className="py-2.5 px-4 font-medium">
                      {b.agreed_rate ? `$${b.agreed_rate.toLocaleString()}` : "N/A"}
                    </td>
                    <td className="py-2.5 px-4 text-on-surface-muted">
                      {new Date(b.created_at).toLocaleDateString()}
                    </td>
                  </tr>
                ))}
                {carrier.recent_bookings.length === 0 && (
                  <tr>
                    <td colSpan={6} className="py-8 text-center text-on-surface-subtle italic">
                      No booking records found for this carrier partner yet.
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* Tab 5: Compliance Documents */}
      {activeTab === "docs" && (
        <div className="space-y-4">
          <div className="flex items-center justify-between">
            <div>
              <h4 className="text-sm font-bold text-on-surface">Regulatory Certifications & Documents</h4>
              <p className="text-xs text-on-surface-muted">Motor Carrier Permits, Insurance declarations, and Tax IDs.</p>
            </div>
            <Button
              size="sm"
              onClick={() => setAddDocOpen(true)}
              className="gap-1.5 bg-primary hover:bg-primary/90 text-white"
            >
              <Plus className="w-4 h-4" />
              Upload Document
            </Button>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {carrier.documents.map((doc, idx) => (
              <Card key={idx} className="p-4 border-outline-variant flex items-start justify-between">
                <div className="space-y-1">
                  <div className="flex items-center gap-2">
                    <FileText className="w-4 h-4 text-primary" />
                    <span className="font-semibold text-sm text-on-surface">{doc.doc_type}</span>
                  </div>
                  {doc.document_number && (
                    <p className="text-xs font-mono text-on-surface-muted">ID / No: {doc.document_number}</p>
                  )}
                  <p className="text-[11px] text-on-surface-subtle">
                    Submitted: {new Date(doc.submitted_at).toLocaleDateString()}
                    {doc.expiry_date && ` • Expires: ${new Date(doc.expiry_date).toLocaleDateString()}`}
                  </p>
                </div>
                <div className="flex flex-col items-end gap-2">
                  <StatusBadge status={doc.status} size="sm" />
                  <a
                    href={doc.file_url}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="text-xs text-primary hover:underline flex items-center gap-1 font-medium"
                  >
                    <ExternalLink className="w-3 h-3" />
                    View Doc
                  </a>
                </div>
              </Card>
            ))}

            {carrier.documents.length === 0 && (
              <div className="col-span-2 text-center py-8 text-xs text-on-surface-subtle italic">
                No compliance documentation uploaded yet. Upload Motor Carrier Permit or Insurance Certificate to verify.
              </div>
            )}
          </div>
        </div>
      )}

      {/* Register Vehicle Modal */}
      {addVehicleOpen && (
        <div className="fixed inset-0 z-50 bg-surface-card/40 backdrop-blur-sm flex items-center justify-center p-4">
          <div className="bg-surface-card rounded-xl shadow-xl w-full max-w-lg border border-outline-variant overflow-hidden">
            <div className="px-6 py-4 border-b border-outline-variant flex items-center justify-between">
              <div>
                <h3 className="text-base font-bold text-on-surface">Register Fleet Vehicle</h3>
                <p className="text-xs text-on-surface-muted mt-0.5">Add commercial vehicle to {carrier.name}</p>
              </div>
              <button onClick={() => setAddVehicleOpen(false)} className="text-on-surface-subtle hover:text-on-surface-muted">
                <X className="w-5 h-5" />
              </button>
            </div>

            <form
              onSubmit={(e) => {
                e.preventDefault();
                createVehicleMutation.mutate({
                  ...vehicleForm,
                  transporter_id: carrier.id,
                });
              }}
              className="p-6 space-y-4"
            >
              <div className="grid grid-cols-2 gap-4">
                <div className="space-y-1">
                  <label className="text-xs font-semibold text-on-surface">License Plate *</label>
                  <Input
                    required
                    placeholder="e.g. IL-TRK-9901"
                    value={vehicleForm.license_plate}
                    onChange={(e) =>
                      setVehicleForm({ ...vehicleForm, license_plate: e.target.value.toUpperCase() })
                    }
                  />
                </div>

                <div className="space-y-1">
                  <label className="text-xs font-semibold text-on-surface">Vehicle Type *</label>
                  <select
                    value={vehicleForm.vehicle_type}
                    onChange={(e) => setVehicleForm({ ...vehicleForm, vehicle_type: e.target.value })}
                    className="w-full text-sm border border-outline-variant rounded-md p-2 bg-surface-card text-on-surface"
                  >
                    <option value="53' Dry Van">53' Dry Van</option>
                    <option value="48' Flatbed">48' Flatbed</option>
                    <option value="Reefer 53'">Reefer 53'</option>
                    <option value="Box Truck 26'">Box Truck 26'</option>
                    <option value="Step Deck 53'">Step Deck 53'</option>
                  </select>
                </div>

                <div className="space-y-1">
                  <label className="text-xs font-semibold text-on-surface">Max Capacity (kg) *</label>
                  <Input
                    type="number"
                    min="1"
                    required
                    value={vehicleForm.capacity_kg}
                    onChange={(e) =>
                      setVehicleForm({ ...vehicleForm, capacity_kg: parseFloat(e.target.value) || 0 })
                    }
                  />
                </div>

                <div className="space-y-1">
                  <label className="text-xs font-semibold text-on-surface">Volume (CBM)</label>
                  <Input
                    type="number"
                    min="0"
                    value={vehicleForm.volume_cbm || ""}
                    onChange={(e) =>
                      setVehicleForm({
                        ...vehicleForm,
                        volume_cbm: e.target.value ? parseFloat(e.target.value) : undefined,
                      })
                    }
                  />
                </div>

                <div className="space-y-1">
                  <label className="text-xs font-semibold text-on-surface">Insurance Expiry</label>
                  <Input
                    type="date"
                    value={vehicleForm.insurance_expiry || ""}
                    onChange={(e) =>
                      setVehicleForm({
                        ...vehicleForm,
                        insurance_expiry: e.target.value
                          ? new Date(e.target.value).toISOString()
                          : undefined,
                      })
                    }
                  />
                </div>

                <div className="space-y-1">
                  <label className="text-xs font-semibold text-on-surface">Fitness / Inspection Expiry</label>
                  <Input
                    type="date"
                    value={vehicleForm.fitness_expiry || ""}
                    onChange={(e) =>
                      setVehicleForm({
                        ...vehicleForm,
                        fitness_expiry: e.target.value
                          ? new Date(e.target.value).toISOString()
                          : undefined,
                      })
                    }
                  />
                </div>
              </div>

              <div className="space-y-1">
                <label className="text-xs font-semibold text-on-surface">Telematics / GPS Unit ID</label>
                <Input
                  placeholder="e.g. SAMSARA-9901-TRK"
                  value={vehicleForm.telematics_device_id || ""}
                  onChange={(e) => setVehicleForm({ ...vehicleForm, telematics_device_id: e.target.value })}
                />
              </div>

              <div className="pt-4 border-t border-outline-variant flex items-center justify-end gap-3">
                <Button type="button" variant="outline" onClick={() => setAddVehicleOpen(false)}>
                  Cancel
                </Button>
                <Button
                  type="submit"
                  disabled={createVehicleMutation.isPending}
                  className="bg-primary hover:bg-primary/90 text-white"
                >
                  {createVehicleMutation.isPending ? "Adding..." : "Add to Fleet"}
                </Button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Register Driver Modal */}
      {addDriverOpen && (
        <div className="fixed inset-0 z-50 bg-surface-card/40 backdrop-blur-sm flex items-center justify-center p-4">
          <div className="bg-surface-card rounded-xl shadow-xl w-full max-w-lg border border-outline-variant overflow-hidden">
            <div className="px-6 py-4 border-b border-outline-variant flex items-center justify-between">
              <div>
                <h3 className="text-base font-bold text-on-surface">Register Commercial Driver</h3>
                <p className="text-xs text-on-surface-muted mt-0.5">Add certified driver to {carrier.name}</p>
              </div>
              <button onClick={() => setAddDriverOpen(false)} className="text-on-surface-subtle hover:text-on-surface-muted">
                <X className="w-5 h-5" />
              </button>
            </div>

            <form
              onSubmit={(e) => {
                e.preventDefault();
                createDriverMutation.mutate({
                  ...driverForm,
                  transporter_id: carrier.id,
                });
              }}
              className="p-6 space-y-4"
            >
              <div className="grid grid-cols-2 gap-4">
                <div className="space-y-1">
                  <label className="text-xs font-semibold text-on-surface">First Name *</label>
                  <Input
                    required
                    value={driverForm.first_name}
                    onChange={(e) => setDriverForm({ ...driverForm, first_name: e.target.value })}
                  />
                </div>

                <div className="space-y-1">
                  <label className="text-xs font-semibold text-on-surface">Last Name *</label>
                  <Input
                    required
                    value={driverForm.last_name}
                    onChange={(e) => setDriverForm({ ...driverForm, last_name: e.target.value })}
                  />
                </div>

                <div className="space-y-1">
                  <label className="text-xs font-semibold text-on-surface">Mobile Phone *</label>
                  <Input
                    required
                    placeholder="+1-312-555-0100"
                    value={driverForm.phone}
                    onChange={(e) => setDriverForm({ ...driverForm, phone: e.target.value })}
                  />
                </div>

                <div className="space-y-1">
                  <label className="text-xs font-semibold text-on-surface">License Number *</label>
                  <Input
                    required
                    placeholder="e.g. DL-99210-IL"
                    value={driverForm.license_number}
                    onChange={(e) => setDriverForm({ ...driverForm, license_number: e.target.value })}
                  />
                </div>
              </div>

              <div className="space-y-1">
                <label className="text-xs font-semibold text-on-surface">License Expiration Date</label>
                <Input
                  type="date"
                  value={driverForm.license_expiry || ""}
                  onChange={(e) =>
                    setDriverForm({
                      ...driverForm,
                      license_expiry: e.target.value ? new Date(e.target.value).toISOString() : undefined,
                    })
                  }
                />
              </div>

              <div className="pt-4 border-t border-outline-variant flex items-center justify-end gap-3">
                <Button type="button" variant="outline" onClick={() => setAddDriverOpen(false)}>
                  Cancel
                </Button>
                <Button
                  type="submit"
                  disabled={createDriverMutation.isPending}
                  className="bg-primary hover:bg-primary/90 text-white"
                >
                  {createDriverMutation.isPending ? "Adding..." : "Register Driver"}
                </Button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Assign Driver to Vehicle Modal */}
      {assignModalOpen && selectedDriverForAssign && (
        <div className="fixed inset-0 z-50 bg-surface-card/40 backdrop-blur-sm flex items-center justify-center p-4">
          <div className="bg-surface-card rounded-xl shadow-xl w-full max-w-md border border-outline-variant overflow-hidden">
            <div className="px-6 py-4 border-b border-outline-variant flex items-center justify-between">
              <div>
                <h3 className="text-base font-bold text-on-surface">
                  Assign Vehicle to {selectedDriverForAssign.full_name}
                </h3>
                <p className="text-xs text-on-surface-muted mt-0.5">
                  Driver License: {selectedDriverForAssign.license_number_masked}
                </p>
              </div>
              <button onClick={() => setAssignModalOpen(false)} className="text-on-surface-subtle hover:text-on-surface-muted">
                <X className="w-5 h-5" />
              </button>
            </div>

            <div className="p-6 space-y-4">
              <div className="space-y-1">
                <label className="text-xs font-semibold text-on-surface">Select Fleet Equipment</label>
                <select
                  value={selectedVehicleIdToAssign}
                  onChange={(e) => setSelectedVehicleIdToAssign(e.target.value)}
                  className="w-full text-sm border border-outline-variant rounded-md p-2 bg-surface-card text-on-surface"
                >
                  <option value="">-- Unassign / No Vehicle --</option>
                  {carrier.vehicles.map((v) => (
                    <option key={v.id} value={v.id}>
                      {v.license_plate} - {v.vehicle_type} ({v.capacity_kg} kg)
                    </option>
                  ))}
                </select>
              </div>

              <div className="pt-3 border-t border-outline-variant flex items-center justify-end gap-3">
                <Button variant="outline" onClick={() => setAssignModalOpen(false)}>
                  Cancel
                </Button>
                <Button
                  onClick={() =>
                    assignDriverMutation.mutate({
                      driverId: selectedDriverForAssign.id,
                      vehicleId: selectedVehicleIdToAssign || null,
                    })
                  }
                  disabled={assignDriverMutation.isPending}
                  className="bg-primary hover:bg-primary/90 text-white"
                >
                  {assignDriverMutation.isPending ? "Assigning..." : "Save Assignment"}
                </Button>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Upload Document Modal */}
      {addDocOpen && (
        <div className="fixed inset-0 z-50 bg-surface-card/40 backdrop-blur-sm flex items-center justify-center p-4">
          <div className="bg-surface-card rounded-xl shadow-xl w-full max-w-md border border-outline-variant overflow-hidden">
            <div className="px-6 py-4 border-b border-outline-variant flex items-center justify-between">
              <div>
                <h3 className="text-base font-bold text-on-surface">Upload Compliance Document</h3>
                <p className="text-xs text-on-surface-muted mt-0.5">Certificates & Regulatory documents</p>
              </div>
              <button onClick={() => setAddDocOpen(false)} className="text-on-surface-subtle hover:text-on-surface-muted">
                <X className="w-5 h-5" />
              </button>
            </div>

            <form
              onSubmit={(e) => {
                e.preventDefault();
                uploadDocMutation.mutate(docForm);
              }}
              className="p-6 space-y-4"
            >
              <div className="space-y-1">
                <label className="text-xs font-semibold text-on-surface">Document Classification *</label>
                <select
                  value={docForm.doc_type}
                  onChange={(e) => setDocForm({ ...docForm, doc_type: e.target.value })}
                  className="w-full text-sm border border-outline-variant rounded-md p-2 bg-surface-card text-on-surface"
                >
                  <option value="MOTOR_CARRIER_PERMIT">Motor Carrier Permit (MCP / DOT)</option>
                  <option value="INSURANCE_CERTIFICATE">Cargo & Liability Insurance Certificate</option>
                  <option value="GSTIN_CERTIFICATE">GST / Tax Registration Certificate</option>
                  <option value="SAFETY_AUDIT">Safety Audit Certificate</option>
                </select>
              </div>

              <div className="space-y-1">
                <label className="text-xs font-semibold text-on-surface">Document / Certificate #</label>
                <Input
                  placeholder="e.g. MCP-2026-99201"
                  value={docForm.document_number || ""}
                  onChange={(e) => setDocForm({ ...docForm, document_number: e.target.value })}
                />
              </div>

              <div className="space-y-1">
                <label className="text-xs font-semibold text-on-surface">Document URL / Storage Reference *</label>
                <Input
                  required
                  placeholder="https://storage.cargopulse.internal/docs/carrier-mcp.pdf"
                  value={docForm.file_url}
                  onChange={(e) => setDocForm({ ...docForm, file_url: e.target.value })}
                />
              </div>

              <div className="space-y-1">
                <label className="text-xs font-semibold text-on-surface">Expiry Date</label>
                <Input
                  type="date"
                  value={docForm.expiry_date || ""}
                  onChange={(e) =>
                    setDocForm({
                      ...docForm,
                      expiry_date: e.target.value ? new Date(e.target.value).toISOString() : undefined,
                    })
                  }
                />
              </div>

              <div className="pt-4 border-t border-outline-variant flex items-center justify-end gap-3">
                <Button type="button" variant="outline" onClick={() => setAddDocOpen(false)}>
                  Cancel
                </Button>
                <Button
                  type="submit"
                  disabled={uploadDocMutation.isPending}
                  className="bg-primary hover:bg-primary/90 text-white"
                >
                  {uploadDocMutation.isPending ? "Uploading..." : "Save Document"}
                </Button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Add Operating Lane Modal */}
      {addLaneOpen && (
        <div className="fixed inset-0 z-50 bg-surface-card/40 backdrop-blur-sm flex items-center justify-center p-4">
          <div className="bg-surface-card rounded-xl shadow-xl w-full max-w-md border border-outline-variant overflow-hidden">
            <div className="px-6 py-4 border-b border-outline-variant flex items-center justify-between">
              <div>
                <h3 className="text-base font-bold text-on-surface">Map Operating Corridor</h3>
                <p className="text-xs text-on-surface-muted mt-0.5">Define standard lane capability</p>
              </div>
              <button onClick={() => setAddLaneOpen(false)} className="text-on-surface-subtle hover:text-on-surface-muted">
                <X className="w-5 h-5" />
              </button>
            </div>

            <form
              onSubmit={(e) => {
                e.preventDefault();
                addLaneMutation.mutate(laneForm);
              }}
              className="p-6 space-y-4"
            >
              <div className="space-y-1">
                <label className="text-xs font-semibold text-on-surface">Origin Region / Hub *</label>
                <Input
                  required
                  placeholder="e.g. Chicago, IL"
                  value={laneForm.origin_region}
                  onChange={(e) => setLaneForm({ ...laneForm, origin_region: e.target.value })}
                />
              </div>

              <div className="space-y-1">
                <label className="text-xs font-semibold text-on-surface">Destination Region / Hub *</label>
                <Input
                  required
                  placeholder="e.g. Detroit, MI"
                  value={laneForm.destination_region}
                  onChange={(e) => setLaneForm({ ...laneForm, destination_region: e.target.value })}
                />
              </div>

              <div className="space-y-1">
                <label className="text-xs font-semibold text-on-surface">Estimated Transit (Hours) *</label>
                <Input
                  type="number"
                  min="1"
                  required
                  value={laneForm.estimated_transit_hours}
                  onChange={(e) =>
                    setLaneForm({
                      ...laneForm,
                      estimated_transit_hours: parseInt(e.target.value) || 24,
                    })
                  }
                />
              </div>

              <div className="pt-4 border-t border-outline-variant flex items-center justify-end gap-3">
                <Button type="button" variant="outline" onClick={() => setAddLaneOpen(false)}>
                  Cancel
                </Button>
                <Button
                  type="submit"
                  disabled={addLaneMutation.isPending}
                  className="bg-primary hover:bg-primary/90 text-white"
                >
                  {addLaneMutation.isPending ? "Adding..." : "Add Corridor"}
                </Button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Verify State Modal */}
      {verifyModalOpen && (
        <div className="fixed inset-0 z-50 bg-surface-card/40 backdrop-blur-sm flex items-center justify-center p-4">
          <div className="bg-surface-card rounded-xl shadow-xl w-full max-w-lg border border-outline-variant overflow-hidden">
            <div className="px-6 py-4 border-b border-outline-variant flex items-center justify-between">
              <div>
                <h3 className="text-base font-bold text-on-surface">
                  Update Carrier Verification: {carrier.name}
                </h3>
                <p className="text-xs text-on-surface-muted mt-0.5">Code: {carrier.code}</p>
              </div>
              <button onClick={() => setVerifyModalOpen(false)} className="text-on-surface-subtle hover:text-on-surface-muted">
                <X className="w-5 h-5" />
              </button>
            </div>

            <div className="p-6 space-y-4">
              <div className="space-y-1">
                <label className="text-xs font-semibold text-on-surface">Target Verification Status</label>
                <select
                  value={verificationTargetStatus}
                  onChange={(e) => setVerificationTargetStatus(e.target.value)}
                  className="w-full text-sm border border-outline-variant rounded-md p-2 bg-surface-card text-on-surface"
                >
                  <option value="VERIFIED">VERIFIED (Eligible for active bookings)</option>
                  <option value="UNDER_VERIFICATION">UNDER_VERIFICATION (Compliance under review)</option>
                  <option value="DOCUMENTS_SUBMITTED">DOCUMENTS_SUBMITTED</option>
                  <option value="REJECTED">REJECTED (Failed compliance / documentation)</option>
                  <option value="SUSPENDED">SUSPENDED (Safety or contract breach)</option>
                </select>
              </div>

              <div className="space-y-1">
                <label className="text-xs font-semibold text-on-surface">Verification Notes / Compliance Audit Summary</label>
                <textarea
                  rows={3}
                  placeholder="e.g. Safety score verified, insurance certificates validated, tax registration confirmed."
                  value={verificationNotes}
                  onChange={(e) => setVerificationNotes(e.target.value)}
                  className="w-full text-sm border border-outline-variant rounded-md p-2 text-on-surface focus:outline-none focus:ring-1 focus:ring-primary"
                />
              </div>

              <div className="pt-3 border-t border-outline-variant flex items-center justify-end gap-3">
                <Button variant="outline" onClick={() => setVerifyModalOpen(false)}>
                  Cancel
                </Button>
                <Button
                  onClick={() =>
                    verifyMutation.mutate({
                      status: verificationTargetStatus,
                      notes: verificationNotes,
                    })
                  }
                  disabled={verifyMutation.isPending}
                  className="bg-primary hover:bg-primary/90 text-white"
                >
                  {verifyMutation.isPending ? "Updating..." : "Confirm Status"}
                </Button>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Suspend Confirmation Dialog */}
      <ConfirmationDialog
        isOpen={suspendModalOpen}
        title="Suspend Carrier from Dispatch"
        description={`Are you sure you want to suspend ${carrier.name} (${carrier.code})? Suspended carriers cannot receive new booking requests or accept shipment assignments.`}
        confirmLabel={suspendMutation.isPending ? "Suspending..." : "Confirm Suspension"}
        variant="destructive"
        onConfirm={() => {
          suspendMutation.mutate(suspendReason || "Operational suspension by Operations Manager");
        }}
        onClose={() => setSuspendModalOpen(false)}
      >
        <div className="mt-2 space-y-1">
          <label className="text-xs font-semibold text-on-surface">Reason for Suspension *</label>
          <Input
            placeholder="e.g. Failed safety inspection, excessive delayed pickups, insurance lapse"
            value={suspendReason}
            onChange={(e) => setSuspendReason(e.target.value)}
            className="text-sm"
          />
        </div>
      </ConfirmationDialog>
    </div>
  );
};

export default TransporterDetailPage;
