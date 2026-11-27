import React, { useState, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import {
  Plus,
  Search,
  Filter,
  Eye,
  AlertTriangle,
  Truck,
  Users,
  ShieldCheck,
  ShieldAlert,
  RefreshCw,
  Building2,
  Phone,
  Mail,
  MapPin,
  X,
} from "lucide-react";
import {
  listTransporters,
  createTransporter,
  verifyTransporter,
  suspendTransporter,
  TransporterListItem,
  TransporterCreatePayload,
} from "@/api/transporters";
import { PageHeader } from "@/components/common/PageHeader";
import { DataTable, ColumnDef } from "@/components/common/DataTable";
import { StatusBadge } from "@/components/common/StatusBadge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Card } from "@/components/ui/card";
import { ConfirmationDialog } from "@/components/common/ConfirmationDialog";
import { useToast } from "@/context/ToastContext";

export const TransporterListPage: React.FC = () => {
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const { toast } = useToast();

  const [page, setPage] = useState(1);
  const [pageSize] = useState(10);
  const [searchTerm, setSearchTerm] = useState("");
  const [debouncedSearch, setDebouncedSearch] = useState("");
  const [verificationFilter, setVerificationFilter] = useState("ALL");
  const [activeFilter, setActiveFilter] = useState("ALL");

  // Create Modal state
  const [createModalOpen, setCreateModalOpen] = useState(false);
  const [formData, setFormData] = useState<TransporterCreatePayload>({
    name: "",
    code: "",
    contact_person: "",
    phone: "",
    email: "",
    gstin: "",
    service_regions: [],
    operating_routes: [],
    vehicle_categories: [],
    max_cargo_capacity_kg: undefined,
  });
  const [regionsInput, setRegionsInput] = useState("");
  const [routesInput, setRoutesInput] = useState("");
  const [categoriesInput, setCategoriesInput] = useState("");

  // Verification modal state
  const [verifyModalOpen, setVerifyModalOpen] = useState(false);
  const [selectedCarrierToVerify, setSelectedCarrierToVerify] = useState<TransporterListItem | null>(null);
  const [verificationTargetStatus, setVerificationTargetStatus] = useState<any>("VERIFIED");
  const [verificationNotes, setVerificationNotes] = useState("");

  // Suspend modal state
  const [suspendModalOpen, setSuspendModalOpen] = useState(false);
  const [selectedCarrierToSuspend, setSelectedCarrierToSuspend] = useState<TransporterListItem | null>(null);
  const [suspendReason, setSuspendReason] = useState("");

  // Search debounce
  useEffect(() => {
    const timer = setTimeout(() => {
      setDebouncedSearch(searchTerm);
      setPage(1);
    }, 350);
    return () => clearTimeout(timer);
  }, [searchTerm]);

  const queryParams = {
    page,
    page_size: pageSize,
    search: debouncedSearch || undefined,
    verification_status: verificationFilter !== "ALL" ? verificationFilter : undefined,
    is_active: activeFilter === "ACTIVE" ? true : activeFilter === "INACTIVE" ? false : undefined,
  };

  const { data, isLoading, refetch } = useQuery({
    queryKey: ["transporters", queryParams],
    queryFn: () => listTransporters(queryParams),
  });

  const createMutation = useMutation({
    mutationFn: (payload: TransporterCreatePayload) => createTransporter(payload),
    onSuccess: (newCarrier) => {
      toast.success("Carrier Registered", `Partner ${newCarrier.name} (${newCarrier.code}) registered successfully.`);
      queryClient.invalidateQueries({ queryKey: ["transporters"] });
      setCreateModalOpen(false);
      resetForm();
    },
    onError: (err: any) => {
      toast.error("Registration Failed", err.response?.data?.detail || "Could not create transporter.");
    },
  });

  const verifyMutation = useMutation({
    mutationFn: ({ id, status, notes }: { id: string; status: any; notes: string }) =>
      verifyTransporter(id, { status, verification_notes: notes }),
    onSuccess: (updated) => {
      toast.success("Verification Updated", `Carrier ${updated.name} status updated to ${updated.verification_status}.`);
      queryClient.invalidateQueries({ queryKey: ["transporters"] });
      setVerifyModalOpen(false);
      setSelectedCarrierToVerify(null);
    },
    onError: (err: any) => {
      toast.error("Action Failed", err.response?.data?.detail || "Could not update verification status.");
    },
  });

  const suspendMutation = useMutation({
    mutationFn: ({ id, reason }: { id: string; reason: string }) => suspendTransporter(id, reason),
    onSuccess: (updated) => {
      toast.warning("Carrier Suspended", `Carrier ${updated.name} has been suspended from active bookings.`);
      queryClient.invalidateQueries({ queryKey: ["transporters"] });
      setSuspendModalOpen(false);
      setSelectedCarrierToSuspend(null);
    },
    onError: (err: any) => {
      toast.error("Action Failed", err.response?.data?.detail || "Could not suspend transporter.");
    },
  });

  const resetForm = () => {
    setFormData({
      name: "",
      code: "",
      contact_person: "",
      phone: "",
      email: "",
      gstin: "",
      service_regions: [],
      operating_routes: [],
      vehicle_categories: [],
      max_cargo_capacity_kg: undefined,
    });
    setRegionsInput("");
    setRoutesInput("");
    setCategoriesInput("");
  };

  const handleCreateSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!formData.name.trim() || !formData.phone.trim()) {
      toast.error("Validation Error", "Transporter name and primary phone number are required.");
      return;
    }

    const payload: TransporterCreatePayload = {
      ...formData,
      service_regions: regionsInput
        .split(",")
        .map((s) => s.trim())
        .filter(Boolean),
      operating_routes: routesInput
        .split(",")
        .map((s) => s.trim())
        .filter(Boolean),
      vehicle_categories: categoriesInput
        .split(",")
        .map((s) => s.trim())
        .filter(Boolean),
    };

    createMutation.mutate(payload);
  };

  // Metrics summary
  const items = data?.items || [];
  const totalCount = data?.total || 0;
  const verifiedCount = items.filter((c) => c.verification_status === "VERIFIED").length;
  const pendingCount = items.filter(
    (c) => c.verification_status === "REGISTERED" || c.verification_status === "DOCUMENTS_SUBMITTED" || c.verification_status === "UNDER_VERIFICATION"
  ).length;
  const suspendedCount = items.filter((c) => c.verification_status === "SUSPENDED" || !c.is_active).length;

  const columns: ColumnDef<TransporterListItem>[] = [
    {
      id: "code",
      header: "Carrier Code & Name",
      cell: (carrier) => (
        <div>
          <button
            onClick={() => navigate(`/transporters/${carrier.id}`)}
            className="font-semibold text-primary hover:underline text-left flex items-center gap-1.5"
          >
            <Building2 className="w-4 h-4 text-on-surface-muted" />
            {carrier.name}
          </button>
          <div className="flex items-center gap-2 mt-0.5">
            <span className="text-xs font-mono text-on-surface-muted bg-surface-container px-1.5 py-0.5 rounded">
              {carrier.code}
            </span>
            {carrier.gstin && (
              <span className="text-xs text-on-surface-subtle">GSTIN: {carrier.gstin}</span>
            )}
          </div>
        </div>
      ),
    },
    {
      id: "contact_person",
      header: "Primary Contact",
      cell: (carrier) => (
        <div className="text-sm">
          <p className="font-medium text-on-surface">{carrier.contact_person || "Operations Desk"}</p>
          <div className="flex flex-col text-xs text-on-surface-muted mt-0.5 space-y-0.5">
            <span className="flex items-center gap-1">
              <Phone className="w-3 h-3 text-on-surface-subtle" />
              {carrier.phone}
            </span>
            {carrier.email && (
              <span className="flex items-center gap-1">
                <Mail className="w-3 h-3 text-on-surface-subtle" />
                {carrier.email}
              </span>
            )}
          </div>
        </div>
      ),
    },
    {
      id: "verification_status",
      header: "Verification",
      cell: (carrier) => (
        <div className="flex flex-col gap-1 items-start">
          <StatusBadge status={carrier.verification_status} size="sm" />
          {!carrier.is_active && (
            <span className="text-[10px] uppercase font-bold text-critical bg-critical-container px-1.5 py-0.5 rounded border border-rose-200">
              Account Inactive
            </span>
          )}
        </div>
      ),
    },
    {
      id: "total_vehicles",
      header: "Fleet Capacity",
      cell: (carrier) => (
        <div className="text-xs space-y-1">
          <div className="flex items-center gap-1.5 text-on-surface">
            <Truck className="w-3.5 h-3.5 text-primary" />
            <span>
              <strong>{carrier.active_vehicles}</strong> / {carrier.total_vehicles} Vehicles Active
            </span>
          </div>
          <div className="flex items-center gap-1.5 text-on-surface">
            <Users className="w-3.5 h-3.5 text-success" />
            <span>
              <strong>{carrier.active_drivers}</strong> / {carrier.total_drivers} Drivers Available
            </span>
          </div>
        </div>
      ),
    },
    {
      id: "reliability_score",
      header: "Reliability & Score",
      cell: (carrier) => (
        <div>
          <div className="flex items-center gap-2">
            <span className="font-bold text-sm text-on-surface">{carrier.reliability_score.toFixed(1)}%</span>
            <div className="w-16 bg-surface-container h-2 rounded-full overflow-hidden">
              <div
                className={`h-full rounded-full ${
                  carrier.reliability_score >= 90
                    ? "bg-success-container0"
                    : carrier.reliability_score >= 75
                    ? "bg-warning-container0"
                    : "bg-critical-container0"
                }`}
                style={{ width: `${Math.min(100, carrier.reliability_score)}%` }}
              />
            </div>
          </div>
          <p className="text-[11px] text-on-surface-muted mt-0.5">
            {carrier.on_time_deliveries} / {carrier.total_deliveries} on-time ({carrier.on_time_delivery_rate.toFixed(0)}%)
          </p>
        </div>
      ),
    },
    {
      id: "service_regions",
      header: "Regions",
      cell: (carrier) => (
        <div className="max-w-[180px]">
          {carrier.service_regions.length > 0 ? (
            <div className="flex flex-wrap gap-1">
              {carrier.service_regions.slice(0, 2).map((reg, idx) => (
                <span
                  key={idx}
                  className="text-[11px] bg-surface-container text-on-surface px-1.5 py-0.5 rounded flex items-center gap-0.5"
                >
                  <MapPin className="w-2.5 h-2.5 text-on-surface-subtle" />
                  {reg}
                </span>
              ))}
              {carrier.service_regions.length > 2 && (
                <span className="text-[11px] text-on-surface-muted">+{carrier.service_regions.length - 2} more</span>
              )}
            </div>
          ) : (
            <span className="text-xs text-on-surface-subtle italic">National / Open</span>
          )}
        </div>
      ),
    },
    {
      id: "actions",
      header: "Actions",
      cell: (carrier) => (
        <div className="flex items-center gap-1.5">
          <Button
            variant="ghost"
            size="sm"
            onClick={() => navigate(`/transporters/${carrier.id}`)}
            className="h-8 px-2 text-on-surface-muted hover:text-primary"
            title="View Full Carrier Profile & Fleet"
          >
            <Eye className="w-4 h-4 mr-1" />
            View
          </Button>
          {carrier.verification_status !== "VERIFIED" && carrier.verification_status !== "SUSPENDED" && (
            <Button
              variant="outline"
              size="sm"
              onClick={() => {
                setSelectedCarrierToVerify(carrier);
                setVerificationTargetStatus("VERIFIED");
                setVerificationNotes("");
                setVerifyModalOpen(true);
              }}
              className="h-8 px-2 text-on-success-container border-teal-200 hover:bg-success-container"
              title="Verify Carrier"
            >
              <ShieldCheck className="w-3.5 h-3.5 mr-1" />
              Verify
            </Button>
          )}
          {carrier.verification_status !== "SUSPENDED" && (
            <Button
              variant="ghost"
              size="sm"
              onClick={() => {
                setSelectedCarrierToSuspend(carrier);
                setSuspendReason("");
                setSuspendModalOpen(true);
              }}
              className="h-8 px-2 text-critical hover:bg-critical-container"
              title="Suspend Carrier"
            >
              <ShieldAlert className="w-3.5 h-3.5" />
            </Button>
          )}
        </div>
      ),
    },
  ];

  return (
    <div className="space-y-6">
      <PageHeader
        title="Transporters & Carrier Network"
        subtitle="Coordinate vetted commercial carriers, verify compliance certifications, and track fleet availability."
        actions={
          <div className="flex items-center gap-3">
            <Button
              variant="outline"
              size="sm"
              onClick={() => refetch()}
              className="gap-1.5 text-on-surface-muted"
            >
              <RefreshCw className="w-4 h-4" />
              Refresh
            </Button>
            <Button
              onClick={() => {
                resetForm();
                setCreateModalOpen(true);
              }}
              className="gap-2 bg-primary hover:bg-primary/90 text-white"
            >
              <Plus className="w-4 h-4" />
              Add Transporter
            </Button>
          </div>
        }
      />

      {/* Metrics Row */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
        <Card className="p-4 flex items-center justify-between border-outline-variant">
          <div>
            <p className="text-xs font-semibold text-on-surface-muted uppercase tracking-wider">Total Carriers</p>
            <h3 className="text-2xl font-bold text-on-surface mt-1">{totalCount}</h3>
            <p className="text-xs text-on-surface-subtle mt-0.5">Registered partners</p>
          </div>
          <div className="w-10 h-10 rounded-lg bg-primary-container text-primary flex items-center justify-center">
            <Building2 className="w-5 h-5" />
          </div>
        </Card>

        <Card className="p-4 flex items-center justify-between border-outline-variant">
          <div>
            <p className="text-xs font-semibold text-on-surface-muted uppercase tracking-wider">Verified & Active</p>
            <h3 className="text-2xl font-bold text-success mt-1">{verifiedCount}</h3>
            <p className="text-xs text-on-surface-subtle mt-0.5">Eligible for bookings</p>
          </div>
          <div className="w-10 h-10 rounded-lg bg-success-container text-success flex items-center justify-center">
            <ShieldCheck className="w-5 h-5" />
          </div>
        </Card>

        <Card className="p-4 flex items-center justify-between border-outline-variant">
          <div>
            <p className="text-xs font-semibold text-on-surface-muted uppercase tracking-wider">Pending Verification</p>
            <h3 className="text-2xl font-bold text-warning mt-1">{pendingCount}</h3>
            <p className="text-xs text-on-surface-subtle mt-0.5">Document review required</p>
          </div>
          <div className="w-10 h-10 rounded-lg bg-warning-container text-warning flex items-center justify-center">
            <AlertTriangle className="w-5 h-5" />
          </div>
        </Card>

        <Card className="p-4 flex items-center justify-between border-outline-variant">
          <div>
            <p className="text-xs font-semibold text-on-surface-muted uppercase tracking-wider">Suspended / Inactive</p>
            <h3 className="text-2xl font-bold text-critical mt-1">{suspendedCount}</h3>
            <p className="text-xs text-on-surface-subtle mt-0.5">Blocked from dispatch</p>
          </div>
          <div className="w-10 h-10 rounded-lg bg-critical-container text-critical flex items-center justify-center">
            <ShieldAlert className="w-5 h-5" />
          </div>
        </Card>
      </div>

      {/* Filters and Search */}
      <Card className="p-4 border-outline-variant">
        <div className="flex flex-col md:flex-row gap-4 items-center justify-between">
          <div className="relative w-full md:w-80">
            <Search className="w-4 h-4 absolute left-3 top-1/2 -translate-y-1/2 text-on-surface-subtle" />
            <Input
              placeholder="Search carrier name, code, phone, region..."
              value={searchTerm}
              onChange={(e) => setSearchTerm(e.target.value)}
              className="pl-9 bg-surface-container-low border-outline-variant focus:bg-surface-card text-sm"
            />
          </div>

          <div className="flex flex-wrap items-center gap-3 w-full md:w-auto">
            <div className="flex items-center gap-1.5 text-xs text-on-surface-muted font-medium">
              <Filter className="w-3.5 h-3.5" />
              <span>Verification:</span>
            </div>
            <select
              value={verificationFilter}
              onChange={(e) => {
                setVerificationFilter(e.target.value);
                setPage(1);
              }}
              className="text-xs border border-outline-variant rounded-md px-2.5 py-1.5 bg-surface-card text-on-surface focus:outline-none focus:ring-1 focus:ring-primary"
            >
              <option value="ALL">All Statuses</option>
              <option value="VERIFIED">Verified</option>
              <option value="UNDER_VERIFICATION">Under Verification</option>
              <option value="DOCUMENTS_SUBMITTED">Docs Submitted</option>
              <option value="REGISTERED">Registered</option>
              <option value="SUSPENDED">Suspended</option>
              <option value="REJECTED">Rejected</option>
            </select>

            <div className="flex items-center gap-1.5 text-xs text-on-surface-muted font-medium ml-2">
              <span>Account:</span>
            </div>
            <select
              value={activeFilter}
              onChange={(e) => {
                setActiveFilter(e.target.value);
                setPage(1);
              }}
              className="text-xs border border-outline-variant rounded-md px-2.5 py-1.5 bg-surface-card text-on-surface focus:outline-none focus:ring-1 focus:ring-primary"
            >
              <option value="ALL">All Accounts</option>
              <option value="ACTIVE">Active Only</option>
              <option value="INACTIVE">Inactive Only</option>
            </select>
          </div>
        </div>
      </Card>

      {/* Transporters DataTable */}
      <DataTable
        columns={columns}
        data={data?.items || []}
        keyExtractor={(carrier) => carrier.id}
        isLoading={isLoading}
        emptyTitle="No Transporters Found"
        emptyDescription="No transporters match your criteria. Click '+ Add Transporter' to onboard a carrier partner."
        pagination={{
          currentPage: data?.page || 1,
          pageSize: data?.page_size || 10,
          totalItems: data?.total || 0,
          totalPages: data?.total_pages || 1,
          onPageChange: (newPage) => setPage(newPage),
        }}
      />

      {/* Add Transporter Modal Dialog */}
      {createModalOpen && (
        <div className="fixed inset-0 z-50 bg-surface-card/40 backdrop-blur-sm flex items-center justify-center p-4">
          <div className="bg-surface-card rounded-xl shadow-xl w-full max-w-2xl border border-outline-variant overflow-hidden max-h-[90vh] flex flex-col">
            <div className="px-6 py-4 border-b border-outline-variant flex items-center justify-between">
              <div>
                <h3 className="text-lg font-bold text-on-surface">Onboard Transporter Partner</h3>
                <p className="text-xs text-on-surface-muted mt-0.5">Register a commercial carrier for freight dispatch and booking assignments.</p>
              </div>
              <button
                onClick={() => setCreateModalOpen(false)}
                className="text-on-surface-subtle hover:text-on-surface-muted p-1 rounded-md"
              >
                <X className="w-5 h-5" />
              </button>
            </div>

            <form onSubmit={handleCreateSubmit} className="p-6 overflow-y-auto space-y-4">
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <div className="space-y-1">
                  <label className="text-xs font-semibold text-on-surface">Carrier Legal Name *</label>
                  <Input
                    required
                    placeholder="e.g. Apex Freight Logistics LLC"
                    value={formData.name}
                    onChange={(e) => setFormData({ ...formData, name: e.target.value })}
                  />
                </div>

                <div className="space-y-1">
                  <label className="text-xs font-semibold text-on-surface">Carrier Code (Optional)</label>
                  <Input
                    placeholder="e.g. TRP-APEX (Auto-generated if empty)"
                    value={formData.code}
                    onChange={(e) => setFormData({ ...formData, code: e.target.value.toUpperCase() })}
                  />
                </div>

                <div className="space-y-1">
                  <label className="text-xs font-semibold text-on-surface">Contact Person</label>
                  <Input
                    placeholder="e.g. Sarah Jenkins (Head of Dispatch)"
                    value={formData.contact_person}
                    onChange={(e) => setFormData({ ...formData, contact_person: e.target.value })}
                  />
                </div>

                <div className="space-y-1">
                  <label className="text-xs font-semibold text-on-surface">Dispatch Phone *</label>
                  <Input
                    required
                    placeholder="e.g. +1-312-555-0199"
                    value={formData.phone}
                    onChange={(e) => setFormData({ ...formData, phone: e.target.value })}
                  />
                </div>

                <div className="space-y-1">
                  <label className="text-xs font-semibold text-on-surface">Dispatch Email</label>
                  <Input
                    type="email"
                    placeholder="e.g. dispatch@apexfreight.com"
                    value={formData.email}
                    onChange={(e) => setFormData({ ...formData, email: e.target.value })}
                  />
                </div>

                <div className="space-y-1">
                  <label className="text-xs font-semibold text-on-surface">GSTIN / Tax Registration</label>
                  <Input
                    placeholder="e.g. 27AAAPL1234A1Z5"
                    value={formData.gstin}
                    onChange={(e) => setFormData({ ...formData, gstin: e.target.value })}
                  />
                </div>

                <div className="space-y-1">
                  <label className="text-xs font-semibold text-on-surface">Max Cargo Capacity (kg)</label>
                  <Input
                    type="number"
                    min="1"
                    placeholder="e.g. 28000"
                    value={formData.max_cargo_capacity_kg || ""}
                    onChange={(e) =>
                      setFormData({
                        ...formData,
                        max_cargo_capacity_kg: e.target.value ? parseFloat(e.target.value) : undefined,
                      })
                    }
                  />
                </div>

                <div className="space-y-1">
                  <label className="text-xs font-semibold text-on-surface">Vehicle Categories (Comma-separated)</label>
                  <Input
                    placeholder="e.g. 53' Dry Van, Flatbed 48', Reefer"
                    value={categoriesInput}
                    onChange={(e) => setCategoriesInput(e.target.value)}
                  />
                </div>
              </div>

              <div className="space-y-1">
                <label className="text-xs font-semibold text-on-surface">Primary Operating Corridors / Routes</label>
                <Input
                  placeholder="e.g. Chicago -> Detroit, Detroit -> Cleveland, Milwaukee -> Minneapolis"
                  value={routesInput}
                  onChange={(e) => setRoutesInput(e.target.value)}
                />
                <p className="text-[11px] text-on-surface-subtle">Separate multiple routes with commas.</p>
              </div>

              <div className="space-y-1">
                <label className="text-xs font-semibold text-on-surface">Service Regions / Operating States</label>
                <Input
                  placeholder="e.g. Midwest, Great Lakes, Illinois, Michigan, Ohio"
                  value={regionsInput}
                  onChange={(e) => setRegionsInput(e.target.value)}
                />
              </div>

              <div className="pt-4 border-t border-outline-variant flex items-center justify-end gap-3">
                <Button
                  type="button"
                  variant="outline"
                  onClick={() => setCreateModalOpen(false)}
                >
                  Cancel
                </Button>
                <Button
                  type="submit"
                  disabled={createMutation.isPending}
                  className="bg-primary hover:bg-primary/90 text-white"
                >
                  {createMutation.isPending ? "Registering..." : "Register Transporter"}
                </Button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Verification State Modal */}
      {verifyModalOpen && selectedCarrierToVerify && (
        <div className="fixed inset-0 z-50 bg-surface-card/40 backdrop-blur-sm flex items-center justify-center p-4">
          <div className="bg-surface-card rounded-xl shadow-xl w-full max-w-lg border border-outline-variant overflow-hidden">
            <div className="px-6 py-4 border-b border-outline-variant flex items-center justify-between">
              <div>
                <h3 className="text-base font-bold text-on-surface">
                  Update Carrier Verification: {selectedCarrierToVerify.name}
                </h3>
                <p className="text-xs text-on-surface-muted mt-0.5">Code: {selectedCarrierToVerify.code}</p>
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
                  placeholder="e.g. DOT safety score verified, insurance certificates validated, tax registration confirmed."
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
                      id: selectedCarrierToVerify.id,
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
        description={`Are you sure you want to suspend ${selectedCarrierToSuspend?.name} (${selectedCarrierToSuspend?.code})? Suspended carriers cannot receive new booking requests or accept shipment assignments.`}
        confirmLabel={suspendMutation.isPending ? "Suspending..." : "Confirm Suspension"}
        variant="destructive"
        onConfirm={() => {
          if (selectedCarrierToSuspend) {
            suspendMutation.mutate({
              id: selectedCarrierToSuspend.id,
              reason: suspendReason || "Operational suspension by Operations Manager",
            });
          }
        }}
        onClose={() => {
          setSuspendModalOpen(false);
          setSelectedCarrierToSuspend(null);
        }}
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

export default TransporterListPage;
