import React, { useState, useEffect } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import {
  Users,
  Plus,
  Search,
  AlertTriangle,
  CheckCircle,
  Truck,
  Phone,
  Trash2,
  RefreshCw,
  Building2,
  X,
} from "lucide-react";
import {
  listDrivers,
  listTransporters,
  listVehicles,
  createDriver,
  deleteDriver,
  assignDriverToVehicle,
  DriverListItem,
  DriverCreatePayload,
} from "@/api/transporters";
import { PageHeader } from "@/components/common/PageHeader";
import { DataTable, ColumnDef } from "@/components/common/DataTable";
import { StatusBadge } from "@/components/common/StatusBadge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Card } from "@/components/ui/card";
import { useToast } from "@/context/ToastContext";

export const DriverListPage: React.FC = () => {
  const queryClient = useQueryClient();
  const { toast } = useToast();

  const [page, setPage] = useState(1);
  const [pageSize] = useState(10);
  const [searchTerm, setSearchTerm] = useState("");
  const [debouncedSearch, setDebouncedSearch] = useState("");
  const [selectedTransporterId, setSelectedTransporterId] = useState("ALL");
  const [availabilityFilter, setAvailabilityFilter] = useState("ALL");
  const [licenseExpiryFilter, setLicenseExpiryFilter] = useState("ALL");

  // Create Modal
  const [createModalOpen, setCreateModalOpen] = useState(false);
  const [formData, setFormData] = useState<DriverCreatePayload>({
    transporter_id: "",
    first_name: "",
    last_name: "",
    phone: "",
    license_number: "",
    license_expiry: "",
    is_available: true,
  });

  // Assign Vehicle Modal
  const [assignModalOpen, setAssignModalOpen] = useState(false);
  const [selectedDriverForAssign, setSelectedDriverForAssign] = useState<DriverListItem | null>(null);
  const [targetVehicleId, setTargetVehicleId] = useState<string>("");

  // Debounce search
  useEffect(() => {
    const timer = setTimeout(() => {
      setDebouncedSearch(searchTerm);
      setPage(1);
    }, 350);
    return () => clearTimeout(timer);
  }, [searchTerm]);

  // Fetch carriers
  const { data: carriersData } = useQuery({
    queryKey: ["transporters-dropdown"],
    queryFn: () => listTransporters({ page: 1, page_size: 100 }),
  });

  // Fetch vehicles for assignment dialog
  const { data: vehiclesData } = useQuery({
    queryKey: ["vehicles-dropdown", selectedDriverForAssign?.transporter_id],
    queryFn: () =>
      listVehicles({
        page: 1,
        page_size: 100,
        transporter_id: selectedDriverForAssign?.transporter_id,
      }),
    enabled: !!selectedDriverForAssign,
  });

  const queryParams = {
    page,
    page_size: pageSize,
    search: debouncedSearch || undefined,
    transporter_id: selectedTransporterId !== "ALL" ? selectedTransporterId : undefined,
    is_available: availabilityFilter === "AVAILABLE" ? true : availabilityFilter === "UNAVAILABLE" ? false : undefined,
    is_license_expired: licenseExpiryFilter === "EXPIRED" ? true : undefined,
  };

  const { data, isLoading, refetch } = useQuery({
    queryKey: ["drivers", queryParams],
    queryFn: () => listDrivers(queryParams),
  });

  const createMutation = useMutation({
    mutationFn: (payload: DriverCreatePayload) => createDriver(payload),
    onSuccess: (d) => {
      toast.success("Driver Registered", `Driver ${d.full_name} added to carrier roster.`);
      queryClient.invalidateQueries({ queryKey: ["drivers"] });
      queryClient.invalidateQueries({ queryKey: ["transporters"] });
      setCreateModalOpen(false);
      resetForm();
    },
    onError: (err: any) => {
      toast.error("Registration Failed", err.response?.data?.detail || "Could not register driver.");
    },
  });

  const assignMutation = useMutation({
    mutationFn: ({ driverId, vehicleId }: { driverId: string; vehicleId: string | null }) =>
      assignDriverToVehicle(driverId, vehicleId),
    onSuccess: (d) => {
      toast.success("Assignment Updated", `Driver ${d.full_name} vehicle updated.`);
      queryClient.invalidateQueries({ queryKey: ["drivers"] });
      queryClient.invalidateQueries({ queryKey: ["vehicles"] });
      setAssignModalOpen(false);
      setSelectedDriverForAssign(null);
    },
    onError: (err: any) => {
      toast.error("Assignment Failed", err.response?.data?.detail || "Could not update vehicle assignment.");
    },
  });

  const deleteMutation = useMutation({
    mutationFn: (id: string) => deleteDriver(id),
    onSuccess: () => {
      toast.success("Driver Removed", "Driver deleted from carrier roster.");
      queryClient.invalidateQueries({ queryKey: ["drivers"] });
    },
    onError: (err: any) => {
      toast.error("Action Failed", err.response?.data?.detail || "Could not delete driver.");
    },
  });

  const resetForm = () => {
    setFormData({
      transporter_id: carriersData?.items[0]?.id || "",
      first_name: "",
      last_name: "",
      phone: "",
      license_number: "",
      license_expiry: "",
      is_available: true,
    });
  };

  const items = data?.items || [];
  const totalCount = data?.total || 0;
  const readyDriversCount = items.filter((d) => d.is_available && !d.is_license_expired).length;
  const expiredLicenseCount = items.filter((d) => d.is_license_expired).length;

  const columns: ColumnDef<DriverListItem>[] = [
    {
      id: "full_name",
      header: "Driver & Carrier",
      cell: (d) => (
        <div>
          <div className="flex items-center gap-1.5 font-bold text-on-surface text-sm">
            <Users className="w-4 h-4 text-success" />
            {d.full_name}
          </div>
          <div className="flex items-center gap-1 text-xs text-on-surface-muted mt-0.5">
            <Building2 className="w-3 h-3 text-on-surface-subtle" />
            <span>{d.transporter_name}</span>
          </div>
        </div>
      ),
    },
    {
      id: "phone",
      header: "Phone",
      cell: (d) => (
        <span className="text-xs font-mono text-on-surface flex items-center gap-1">
          <Phone className="w-3 h-3 text-on-surface-subtle" />
          {d.phone}
        </span>
      ),
    },
    {
      id: "license_number_masked",
      header: "Commercial License",
      cell: (d) => (
        <div className="text-xs">
          <span className="font-mono font-semibold text-on-surface bg-surface-container px-1.5 py-0.5 rounded">
            {d.license_number_masked}
          </span>
          <div className="mt-1">
            {d.is_license_expired ? (
              <span className="text-[10px] font-bold text-on-critical-container bg-critical-container px-1.5 py-0.5 rounded border border-rose-200">
                License Expired
              </span>
            ) : d.license_expiry ? (
              <span className="text-[11px] text-on-surface-subtle">
                Exp: {new Date(d.license_expiry).toLocaleDateString()}
              </span>
            ) : (
              <span className="text-[11px] text-on-surface-subtle italic">No expiry set</span>
            )}
          </div>
        </div>
      ),
    },
    {
      id: "status",
      header: "Status",
      cell: (d) => (
        <div className="flex flex-col gap-1 items-start">
          <StatusBadge status={d.status} size="sm" />
          {d.is_license_expired && (
            <span className="text-[10px] font-bold text-on-critical-container bg-critical-container px-1 py-0.5 rounded border border-rose-200">
              Dispatch Ineligible
            </span>
          )}
        </div>
      ),
    },
    {
      id: "assigned_vehicle_plate",
      header: "Assigned Vehicle",
      cell: (d) => (
        <div className="text-xs">
          {d.assigned_vehicle_plate ? (
            <span className="font-mono font-bold text-on-surface bg-surface-container px-2 py-0.5 rounded flex items-center gap-1 w-max">
              <Truck className="w-3 h-3 text-primary" />
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
              setTargetVehicleId(d.assigned_vehicle_id || "");
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
                deleteMutation.mutate(d.id);
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
      <PageHeader
        title="Commercial Drivers Roster"
        subtitle="Manage commercial drivers across all partner carriers, protect sensitive license numbers, and enforce license validity before vehicle assignment."
        actions={
          <div className="flex items-center gap-3">
            <Button variant="outline" size="sm" onClick={() => refetch()} className="gap-1.5 text-on-surface-muted">
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
              Register Driver
            </Button>
          </div>
        }
      />

      {/* Metrics Row */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <Card className="p-4 flex items-center justify-between border-outline-variant">
          <div>
            <p className="text-xs font-semibold text-on-surface-muted uppercase tracking-wider">Total Drivers</p>
            <h3 className="text-2xl font-bold text-on-surface mt-1">{totalCount}</h3>
            <p className="text-xs text-on-surface-subtle mt-0.5">Commercial roster</p>
          </div>
          <div className="w-10 h-10 rounded-lg bg-indigo-50 text-indigo-600 flex items-center justify-center">
            <Users className="w-5 h-5" />
          </div>
        </Card>

        <Card className="p-4 flex items-center justify-between border-outline-variant">
          <div>
            <p className="text-xs font-semibold text-on-surface-muted uppercase tracking-wider">Ready / On-Duty</p>
            <h3 className="text-2xl font-bold text-success mt-1">{readyDriversCount}</h3>
            <p className="text-xs text-on-surface-subtle mt-0.5">Available with valid license</p>
          </div>
          <div className="w-10 h-10 rounded-lg bg-success-container text-success flex items-center justify-center">
            <CheckCircle className="w-5 h-5" />
          </div>
        </Card>

        <Card className="p-4 flex items-center justify-between border-outline-variant">
          <div>
            <p className="text-xs font-semibold text-on-surface-muted uppercase tracking-wider">Expired Licenses</p>
            <h3 className="text-2xl font-bold text-critical mt-1">{expiredLicenseCount}</h3>
            <p className="text-xs text-on-surface-subtle mt-0.5">Blocked from assignment</p>
          </div>
          <div className="w-10 h-10 rounded-lg bg-critical-container text-critical flex items-center justify-center">
            <AlertTriangle className="w-5 h-5" />
          </div>
        </Card>
      </div>

      {/* Filters Bar */}
      <Card className="p-4 border-outline-variant">
        <div className="flex flex-col md:flex-row gap-4 items-center justify-between">
          <div className="relative w-full md:w-72">
            <Search className="w-4 h-4 absolute left-3 top-1/2 -translate-y-1/2 text-on-surface-subtle" />
            <Input
              placeholder="Search driver name, phone, carrier..."
              value={searchTerm}
              onChange={(e) => setSearchTerm(e.target.value)}
              className="pl-9 bg-surface-container-low border-outline-variant focus:bg-surface-card text-sm"
            />
          </div>

          <div className="flex flex-wrap items-center gap-3 w-full md:w-auto">
            <div className="flex items-center gap-1.5 text-xs text-on-surface-muted font-medium">
              <Building2 className="w-3.5 h-3.5" />
              <span>Carrier:</span>
            </div>
            <select
              value={selectedTransporterId}
              onChange={(e) => {
                setSelectedTransporterId(e.target.value);
                setPage(1);
              }}
              className="text-xs border border-outline-variant rounded-md px-2.5 py-1.5 bg-surface-card text-on-surface"
            >
              <option value="ALL">All Carriers</option>
              {carriersData?.items.map((c) => (
                <option key={c.id} value={c.id}>
                  {c.name} ({c.code})
                </option>
              ))}
            </select>

            <div className="flex items-center gap-1.5 text-xs text-on-surface-muted font-medium ml-2">
              <span>Availability:</span>
            </div>
            <select
              value={availabilityFilter}
              onChange={(e) => {
                setAvailabilityFilter(e.target.value);
                setPage(1);
              }}
              className="text-xs border border-outline-variant rounded-md px-2.5 py-1.5 bg-surface-card text-on-surface"
            >
              <option value="ALL">All</option>
              <option value="AVAILABLE">Available Only</option>
              <option value="UNAVAILABLE">Unavailable Only</option>
            </select>

            <div className="flex items-center gap-1.5 text-xs text-on-surface-muted font-medium ml-2">
              <span>License Status:</span>
            </div>
            <select
              value={licenseExpiryFilter}
              onChange={(e) => {
                setLicenseExpiryFilter(e.target.value);
                setPage(1);
              }}
              className="text-xs border border-outline-variant rounded-md px-2.5 py-1.5 bg-surface-card text-on-surface"
            >
              <option value="ALL">All Drivers</option>
              <option value="EXPIRED">Expired Licenses Only</option>
            </select>
          </div>
        </div>
      </Card>

      {/* DataTable */}
      <DataTable
        columns={columns}
        data={data?.items || []}
        keyExtractor={(d) => d.id}
        isLoading={isLoading}
        emptyTitle="No Drivers Found"
        emptyDescription="No drivers match your criteria. Click '+ Register Driver' to onboard drivers."
        pagination={{
          currentPage: data?.page || 1,
          pageSize: data?.page_size || 10,
          totalItems: data?.total || 0,
          totalPages: data?.total_pages || 1,
          onPageChange: (newPage) => setPage(newPage),
        }}
      />

      {/* Register Driver Modal */}
      {createModalOpen && (
        <div className="fixed inset-0 z-50 bg-surface-card/40 backdrop-blur-sm flex items-center justify-center p-4">
          <div className="bg-surface-card rounded-xl shadow-xl w-full max-w-lg border border-outline-variant overflow-hidden">
            <div className="px-6 py-4 border-b border-outline-variant flex items-center justify-between">
              <div>
                <h3 className="text-base font-bold text-on-surface">Register Commercial Driver</h3>
                <p className="text-xs text-on-surface-muted mt-0.5">Add verified driver to carrier personnel roster</p>
              </div>
              <button onClick={() => setCreateModalOpen(false)} className="text-on-surface-subtle hover:text-on-surface-muted">
                <X className="w-5 h-5" />
              </button>
            </div>

            <form
              onSubmit={(e) => {
                e.preventDefault();
                if (!formData.transporter_id) {
                  toast.error("Validation Error", "Please select a carrier partner.");
                  return;
                }
                createMutation.mutate(formData);
              }}
              className="p-6 space-y-4"
            >
              <div className="space-y-1">
                <label className="text-xs font-semibold text-on-surface">Assign to Carrier Partner *</label>
                <select
                  required
                  value={formData.transporter_id}
                  onChange={(e) => setFormData({ ...formData, transporter_id: e.target.value })}
                  className="w-full text-sm border border-outline-variant rounded-md p-2 bg-surface-card text-on-surface"
                >
                  <option value="">-- Select Partnered Carrier --</option>
                  {carriersData?.items.map((c) => (
                    <option key={c.id} value={c.id}>
                      {c.name} ({c.code})
                    </option>
                  ))}
                </select>
              </div>

              <div className="grid grid-cols-2 gap-4">
                <div className="space-y-1">
                  <label className="text-xs font-semibold text-on-surface">First Name *</label>
                  <Input
                    required
                    value={formData.first_name}
                    onChange={(e) => setFormData({ ...formData, first_name: e.target.value })}
                  />
                </div>

                <div className="space-y-1">
                  <label className="text-xs font-semibold text-on-surface">Last Name *</label>
                  <Input
                    required
                    value={formData.last_name}
                    onChange={(e) => setFormData({ ...formData, last_name: e.target.value })}
                  />
                </div>

                <div className="space-y-1">
                  <label className="text-xs font-semibold text-on-surface">Mobile Phone *</label>
                  <Input
                    required
                    placeholder="+1-312-555-0100"
                    value={formData.phone}
                    onChange={(e) => setFormData({ ...formData, phone: e.target.value })}
                  />
                </div>

                <div className="space-y-1">
                  <label className="text-xs font-semibold text-on-surface">Driver License Number *</label>
                  <Input
                    required
                    placeholder="e.g. DL-99210-IL"
                    value={formData.license_number}
                    onChange={(e) => setFormData({ ...formData, license_number: e.target.value })}
                  />
                  <p className="text-[10px] text-on-surface-subtle">Masked automatically in general views for privacy.</p>
                </div>
              </div>

              <div className="space-y-1">
                <label className="text-xs font-semibold text-on-surface">License Expiration Date</label>
                <Input
                  type="date"
                  value={formData.license_expiry || ""}
                  onChange={(e) =>
                    setFormData({
                      ...formData,
                      license_expiry: e.target.value ? new Date(e.target.value).toISOString() : undefined,
                    })
                  }
                />
              </div>

              <div className="pt-4 border-t border-outline-variant flex items-center justify-end gap-3">
                <Button type="button" variant="outline" onClick={() => setCreateModalOpen(false)}>
                  Cancel
                </Button>
                <Button
                  type="submit"
                  disabled={createMutation.isPending}
                  className="bg-primary hover:bg-primary/90 text-white"
                >
                  {createMutation.isPending ? "Adding..." : "Register Driver"}
                </Button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Assign Vehicle Modal */}
      {assignModalOpen && selectedDriverForAssign && (
        <div className="fixed inset-0 z-50 bg-surface-card/40 backdrop-blur-sm flex items-center justify-center p-4">
          <div className="bg-surface-card rounded-xl shadow-xl w-full max-w-md border border-outline-variant overflow-hidden">
            <div className="px-6 py-4 border-b border-outline-variant flex items-center justify-between">
              <div>
                <h3 className="text-base font-bold text-on-surface">
                  Assign Vehicle: {selectedDriverForAssign.full_name}
                </h3>
                <p className="text-xs text-on-surface-muted mt-0.5">
                  License: {selectedDriverForAssign.license_number_masked}
                </p>
              </div>
              <button onClick={() => setAssignModalOpen(false)} className="text-on-surface-subtle hover:text-on-surface-muted">
                <X className="w-5 h-5" />
              </button>
            </div>

            <div className="p-6 space-y-4">
              {selectedDriverForAssign.is_license_expired && (
                <div className="bg-critical-container border border-rose-200 rounded-lg p-3 text-xs text-rose-800 flex items-center gap-2">
                  <AlertTriangle className="w-4 h-4 text-critical shrink-0" />
                  <span>
                    <strong>Warning:</strong> This driver has an expired commercial license and cannot be assigned to an active vehicle.
                  </span>
                </div>
              )}

              <div className="space-y-1">
                <label className="text-xs font-semibold text-on-surface">Select Vehicle ({selectedDriverForAssign.transporter_name})</label>
                <select
                  value={targetVehicleId}
                  onChange={(e) => setTargetVehicleId(e.target.value)}
                  className="w-full text-sm border border-outline-variant rounded-md p-2 bg-surface-card text-on-surface"
                >
                  <option value="">-- Unassign / No Vehicle --</option>
                  {vehiclesData?.items.map((v) => (
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
                    assignMutation.mutate({
                      driverId: selectedDriverForAssign.id,
                      vehicleId: targetVehicleId || null,
                    })
                  }
                  disabled={assignMutation.isPending || selectedDriverForAssign.is_license_expired}
                  className="bg-primary hover:bg-primary/90 text-white"
                >
                  {assignMutation.isPending ? "Assigning..." : "Save Assignment"}
                </Button>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default DriverListPage;
