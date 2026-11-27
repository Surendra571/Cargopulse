import React, { useState, useEffect } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import {
  Truck,
  Plus,
  Search,
  AlertTriangle,
  CheckCircle,
  Trash2,
  RefreshCw,
  Building2,
  Users,
  X,
} from "lucide-react";
import {
  listVehicles,
  listTransporters,
  createVehicle,
  deleteVehicle,
  VehicleListItem,
  VehicleCreatePayload,
} from "@/api/transporters";
import { PageHeader } from "@/components/common/PageHeader";
import { DataTable, ColumnDef } from "@/components/common/DataTable";
import { StatusBadge } from "@/components/common/StatusBadge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Card } from "@/components/ui/card";
import { useToast } from "@/context/ToastContext";

export const VehicleListPage: React.FC = () => {
  const queryClient = useQueryClient();
  const { toast } = useToast();

  const [page, setPage] = useState(1);
  const [pageSize] = useState(10);
  const [searchTerm, setSearchTerm] = useState("");
  const [debouncedSearch, setDebouncedSearch] = useState("");
  const [selectedTransporterId, setSelectedTransporterId] = useState("ALL");
  const [selectedVehicleType, setSelectedVehicleType] = useState("ALL");
  const [availabilityFilter, setAvailabilityFilter] = useState("ALL");
  const [expiredDocsFilter, setExpiredDocsFilter] = useState("ALL");

  // Create Modal
  const [createModalOpen, setCreateModalOpen] = useState(false);
  const [formData, setFormData] = useState<VehicleCreatePayload>({
    transporter_id: "",
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

  // Debounce search
  useEffect(() => {
    const timer = setTimeout(() => {
      setDebouncedSearch(searchTerm);
      setPage(1);
    }, 350);
    return () => clearTimeout(timer);
  }, [searchTerm]);

  // Fetch carriers for dropdown filter & creation
  const { data: carriersData } = useQuery({
    queryKey: ["transporters-dropdown"],
    queryFn: () => listTransporters({ page: 1, page_size: 100 }),
  });

  const queryParams = {
    page,
    page_size: pageSize,
    search: debouncedSearch || undefined,
    transporter_id: selectedTransporterId !== "ALL" ? selectedTransporterId : undefined,
    vehicle_type: selectedVehicleType !== "ALL" ? selectedVehicleType : undefined,
    is_available: availabilityFilter === "AVAILABLE" ? true : availabilityFilter === "UNAVAILABLE" ? false : undefined,
    has_expired_documents: expiredDocsFilter === "EXPIRED" ? true : undefined,
  };

  const { data, isLoading, refetch } = useQuery({
    queryKey: ["vehicles", queryParams],
    queryFn: () => listVehicles(queryParams),
  });

  const createMutation = useMutation({
    mutationFn: (payload: VehicleCreatePayload) => createVehicle(payload),
    onSuccess: (v) => {
      toast.success("Vehicle Registered", `Equipment ${v.license_plate} added to fleet.`);
      queryClient.invalidateQueries({ queryKey: ["vehicles"] });
      queryClient.invalidateQueries({ queryKey: ["transporters"] });
      setCreateModalOpen(false);
      resetForm();
    },
    onError: (err: any) => {
      toast.error("Registration Failed", err.response?.data?.detail || "Could not register vehicle.");
    },
  });

  const deleteMutation = useMutation({
    mutationFn: (id: string) => deleteVehicle(id),
    onSuccess: () => {
      toast.success("Vehicle Removed", "Equipment removed from carrier fleet.");
      queryClient.invalidateQueries({ queryKey: ["vehicles"] });
    },
    onError: (err: any) => {
      toast.error("Action Failed", err.response?.data?.detail || "Could not delete vehicle.");
    },
  });

  const resetForm = () => {
    setFormData({
      transporter_id: carriersData?.items[0]?.id || "",
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
  };

  const items = data?.items || [];
  const totalCount = data?.total || 0;
  const availableCount = items.filter((v) => v.is_available && !v.has_expired_documents).length;
  const expiredDocsCount = items.filter((v) => v.has_expired_documents).length;

  const columns: ColumnDef<VehicleListItem>[] = [
    {
      id: "license_plate",
      header: "Plate & Carrier",
      cell: (v) => (
        <div>
          <div className="flex items-center gap-1.5 font-mono font-bold text-on-surface text-sm">
            <Truck className="w-4 h-4 text-primary" />
            {v.license_plate}
          </div>
          <div className="flex items-center gap-1 text-xs text-on-surface-muted mt-0.5">
            <Building2 className="w-3 h-3 text-on-surface-subtle" />
            <span>{v.transporter_name}</span>
          </div>
        </div>
      ),
    },
    {
      id: "vehicle_type",
      header: "Vehicle Type",
      cell: (v) => (
        <span className="text-xs font-semibold text-on-surface bg-surface-container px-2 py-0.5 rounded">
          {v.vehicle_type}
        </span>
      ),
    },
    {
      id: "capacity_kg",
      header: "Payload Capacity",
      cell: (v) => (
        <div className="text-xs">
          <p className="font-semibold text-on-surface">{v.capacity_kg.toLocaleString()} kg</p>
          {v.volume_cbm && <p className="text-on-surface-subtle">{v.volume_cbm} CBM</p>}
        </div>
      ),
    },
    {
      id: "insurance_expiry",
      header: "Compliance Expirations",
      cell: (v) => (
        <div className="text-xs space-y-1">
          <div className="flex items-center gap-1">
            <span className="text-on-surface-muted">Insurance:</span>
            {v.insurance_expiry ? (
              <span
                className={`font-medium ${
                  new Date(v.insurance_expiry) < new Date() ? "text-critical font-bold" : "text-on-surface"
                }`}
              >
                {new Date(v.insurance_expiry).toLocaleDateString()}
              </span>
            ) : (
              <span className="text-on-surface-subtle italic">Not set</span>
            )}
          </div>
          <div className="flex items-center gap-1">
            <span className="text-on-surface-muted">Fitness:</span>
            {v.fitness_expiry ? (
              <span
                className={`font-medium ${
                  new Date(v.fitness_expiry) < new Date() ? "text-critical font-bold" : "text-on-surface"
                }`}
              >
                {new Date(v.fitness_expiry).toLocaleDateString()}
              </span>
            ) : (
              <span className="text-on-surface-subtle italic">Not set</span>
            )}
          </div>
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
            <span className="text-[10px] font-bold text-on-critical-container bg-critical-container px-1 py-0.5 rounded border border-rose-200">
              Ineligible for Load
            </span>
          )}
        </div>
      ),
    },
    {
      id: "assigned_driver_name",
      header: "Assigned Driver",
      cell: (v) => (
        <div className="text-xs">
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
      id: "actions",
      header: "Actions",
      cell: (v) => (
        <Button
          variant="ghost"
          size="sm"
          onClick={() => {
            if (confirm(`Remove vehicle ${v.license_plate} from fleet?`)) {
              deleteMutation.mutate(v.id);
            }
          }}
          className="h-8 px-2 text-critical hover:bg-critical-container"
        >
          <Trash2 className="w-4 h-4" />
        </Button>
      ),
    },
  ];

  return (
    <div className="space-y-6">
      <PageHeader
        title="Fleet Vehicles Management"
        subtitle="Track commercial equipment across all partnered carriers, monitor registration certificates, and prevent dispatch of non-compliant vehicles."
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
              Register Vehicle
            </Button>
          </div>
        }
      />

      {/* Metrics Row */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <Card className="p-4 flex items-center justify-between border-outline-variant">
          <div>
            <p className="text-xs font-semibold text-on-surface-muted uppercase tracking-wider">Total Fleet Equipment</p>
            <h3 className="text-2xl font-bold text-on-surface mt-1">{totalCount}</h3>
            <p className="text-xs text-on-surface-subtle mt-0.5">Commercial units active</p>
          </div>
          <div className="w-10 h-10 rounded-lg bg-primary-container text-primary flex items-center justify-center">
            <Truck className="w-5 h-5" />
          </div>
        </Card>

        <Card className="p-4 flex items-center justify-between border-outline-variant">
          <div>
            <p className="text-xs font-semibold text-on-surface-muted uppercase tracking-wider">Ready for Dispatch</p>
            <h3 className="text-2xl font-bold text-success mt-1">{availableCount}</h3>
            <p className="text-xs text-on-surface-subtle mt-0.5">Available & compliant</p>
          </div>
          <div className="w-10 h-10 rounded-lg bg-success-container text-success flex items-center justify-center">
            <CheckCircle className="w-5 h-5" />
          </div>
        </Card>

        <Card className="p-4 flex items-center justify-between border-outline-variant">
          <div>
            <p className="text-xs font-semibold text-on-surface-muted uppercase tracking-wider">Expired Documents</p>
            <h3 className="text-2xl font-bold text-critical mt-1">{expiredDocsCount}</h3>
            <p className="text-xs text-on-surface-subtle mt-0.5">Insurance / fitness lapsed</p>
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
              placeholder="Search plate, carrier, telematics..."
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
              <span>Type:</span>
            </div>
            <select
              value={selectedVehicleType}
              onChange={(e) => {
                setSelectedVehicleType(e.target.value);
                setPage(1);
              }}
              className="text-xs border border-outline-variant rounded-md px-2.5 py-1.5 bg-surface-card text-on-surface"
            >
              <option value="ALL">All Types</option>
              <option value="53' Dry Van">53' Dry Van</option>
              <option value="48' Flatbed">48' Flatbed</option>
              <option value="Reefer 53'">Reefer 53'</option>
              <option value="Box Truck 26'">Box Truck 26'</option>
              <option value="Step Deck 53'">Step Deck 53'</option>
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
              <span>Compliance:</span>
            </div>
            <select
              value={expiredDocsFilter}
              onChange={(e) => {
                setExpiredDocsFilter(e.target.value);
                setPage(1);
              }}
              className="text-xs border border-outline-variant rounded-md px-2.5 py-1.5 bg-surface-card text-on-surface"
            >
              <option value="ALL">All Records</option>
              <option value="EXPIRED">Expired Documents Only</option>
            </select>
          </div>
        </div>
      </Card>

      {/* DataTable */}
      <DataTable
        columns={columns}
        data={data?.items || []}
        keyExtractor={(v) => v.id}
        isLoading={isLoading}
        emptyTitle="No Vehicles Found"
        emptyDescription="No vehicles match your query. Click '+ Register Vehicle' to onboard equipment."
        pagination={{
          currentPage: data?.page || 1,
          pageSize: data?.page_size || 10,
          totalItems: data?.total || 0,
          totalPages: data?.total_pages || 1,
          onPageChange: (newPage) => setPage(newPage),
        }}
      />

      {/* Register Vehicle Modal */}
      {createModalOpen && (
        <div className="fixed inset-0 z-50 bg-surface-card/40 backdrop-blur-sm flex items-center justify-center p-4">
          <div className="bg-surface-card rounded-xl shadow-xl w-full max-w-lg border border-outline-variant overflow-hidden">
            <div className="px-6 py-4 border-b border-outline-variant flex items-center justify-between">
              <div>
                <h3 className="text-base font-bold text-on-surface">Register Fleet Vehicle</h3>
                <p className="text-xs text-on-surface-muted mt-0.5">Map commercial equipment to a partnered carrier</p>
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
                  <label className="text-xs font-semibold text-on-surface">License Plate *</label>
                  <Input
                    required
                    placeholder="e.g. IL-TRK-9901"
                    value={formData.license_plate}
                    onChange={(e) => setFormData({ ...formData, license_plate: e.target.value.toUpperCase() })}
                  />
                </div>

                <div className="space-y-1">
                  <label className="text-xs font-semibold text-on-surface">Vehicle Type *</label>
                  <select
                    value={formData.vehicle_type}
                    onChange={(e) => setFormData({ ...formData, vehicle_type: e.target.value })}
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
                    value={formData.capacity_kg}
                    onChange={(e) => setFormData({ ...formData, capacity_kg: parseFloat(e.target.value) || 0 })}
                  />
                </div>

                <div className="space-y-1">
                  <label className="text-xs font-semibold text-on-surface">Volume (CBM)</label>
                  <Input
                    type="number"
                    min="0"
                    value={formData.volume_cbm || ""}
                    onChange={(e) =>
                      setFormData({
                        ...formData,
                        volume_cbm: e.target.value ? parseFloat(e.target.value) : undefined,
                      })
                    }
                  />
                </div>

                <div className="space-y-1">
                  <label className="text-xs font-semibold text-on-surface">Insurance Expiry Date</label>
                  <Input
                    type="date"
                    value={formData.insurance_expiry || ""}
                    onChange={(e) =>
                      setFormData({
                        ...formData,
                        insurance_expiry: e.target.value ? new Date(e.target.value).toISOString() : undefined,
                      })
                    }
                  />
                </div>

                <div className="space-y-1">
                  <label className="text-xs font-semibold text-on-surface">Fitness Expiry Date</label>
                  <Input
                    type="date"
                    value={formData.fitness_expiry || ""}
                    onChange={(e) =>
                      setFormData({
                        ...formData,
                        fitness_expiry: e.target.value ? new Date(e.target.value).toISOString() : undefined,
                      })
                    }
                  />
                </div>
              </div>

              <div className="space-y-1">
                <label className="text-xs font-semibold text-on-surface">Telematics Device ID / GPS Tracker</label>
                <Input
                  placeholder="e.g. SAMSARA-9901-TRK"
                  value={formData.telematics_device_id || ""}
                  onChange={(e) => setFormData({ ...formData, telematics_device_id: e.target.value })}
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
                  {createMutation.isPending ? "Adding..." : "Register Vehicle"}
                </Button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
};

export default VehicleListPage;
