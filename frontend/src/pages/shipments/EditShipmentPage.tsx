import React, { useEffect } from "react";
import { useParams, useNavigate } from "react-router-dom";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import * as z from "zod";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import {
  Package,
  MapPin,
  AlertTriangle,
  ArrowLeft,
  CheckCircle2,
  FileText,
  Lock,
} from "lucide-react";
import { shipmentApi, ShipmentUpdateRequest } from "@/api/shipments";
import { PageHeader } from "@/components/common/PageHeader";
import { FormField } from "@/components/common/FormField";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { Card, CardHeader, CardTitle, CardContent } from "@/components/ui/card";
import { LoadingState } from "@/components/common/LoadingState";
import { ErrorState } from "@/components/common/ErrorState";
import { useToast } from "@/context/ToastContext";

const editFormSchema = z
  .object({
    customer_name: z.string().min(2, "Customer name must be at least 2 characters").optional(),
    customer_reference: z.string().optional(),
    origin_name: z.string().min(2, "Facility name required").optional(),
    origin_address: z.string().min(5, "Address required").optional(),
    origin_city: z.string().min(2, "City required").optional(),
    origin_state: z.string().min(2, "State required").optional(),
    origin_postal_code: z.string().min(3, "Postal required").optional(),
    origin_dock_number: z.string().optional(),
    origin_contact_name: z.string().min(2, "Contact required").optional(),
    origin_contact_phone: z.string().min(7, "Phone required").optional(),

    destination_name: z.string().min(2, "Facility name required").optional(),
    destination_address: z.string().min(5, "Address required").optional(),
    destination_city: z.string().min(2, "City required").optional(),
    destination_state: z.string().min(2, "State required").optional(),
    destination_postal_code: z.string().min(3, "Postal required").optional(),
    destination_dock_number: z.string().optional(),
    destination_contact_name: z.string().min(2, "Contact required").optional(),
    destination_contact_phone: z.string().min(7, "Phone required").optional(),

    goods_description: z.string().min(3, "Description required").optional(),
    cargo_category: z.string().optional(),
    total_weight_kg: z.coerce.number().positive("Must be > 0 kg").optional(),
    package_count: z.coerce.number().int().positive("Must be > 0").optional(),
    package_unit: z.string().optional(),
    total_volume_cbm: z.coerce.number().min(0).optional(),
    required_vehicle_type: z.string().optional(),
    is_hazardous: z.boolean().optional(),

    scheduled_pickup_time: z.string().optional(),
    expected_delivery_time: z.string().optional(),

    priority: z.string().optional(),
    special_instructions: z.string().optional(),
    invoice_number: z.string().optional(),
    invoice_value: z.coerce.number().min(0).optional(),
  });

type EditFormData = z.infer<typeof editFormSchema>;

export const EditShipmentPage: React.FC = () => {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const { toast } = useToast();

  const { data: shipment, isLoading, isError, refetch } = useQuery({
    queryKey: ["shipment", id],
    queryFn: () => shipmentApi.getShipment(id!),
    enabled: Boolean(id),
  });

  const formatLocalISO = (isoStr?: string | null) => {
    if (!isoStr) return "";
    const d = new Date(isoStr);
    const tzOffset = d.getTimezoneOffset() * 60000;
    return new Date(d.getTime() - tzOffset).toISOString().slice(0, 16);
  };

  const {
    register,
    handleSubmit,
    reset,
    formState: { errors },
  } = useForm<EditFormData>({
    resolver: zodResolver(editFormSchema),
  });

  useEffect(() => {
    if (shipment) {
      reset({
        customer_name: shipment.customer_name || "",
        customer_reference: shipment.customer_reference || "",
        origin_name: shipment.origin_name,
        origin_address: shipment.origin_address,
        origin_city: shipment.origin_city,
        origin_state: shipment.origin_state,
        origin_postal_code: shipment.origin_postal_code,
        origin_dock_number: shipment.origin_dock_number || "",
        origin_contact_name: shipment.origin_contact_name,
        origin_contact_phone: shipment.origin_contact_phone,

        destination_name: shipment.destination_name,
        destination_address: shipment.destination_address,
        destination_city: shipment.destination_city,
        destination_state: shipment.destination_state,
        destination_postal_code: shipment.destination_postal_code,
        destination_dock_number: shipment.destination_dock_number || "",
        destination_contact_name: shipment.destination_contact_name,
        destination_contact_phone: shipment.destination_contact_phone,

        goods_description: shipment.goods_description,
        cargo_category: shipment.cargo_category,
        total_weight_kg: shipment.total_weight_kg,
        package_count: shipment.package_count,
        package_unit: shipment.package_unit,
        total_volume_cbm: shipment.total_volume_cbm || undefined,
        required_vehicle_type: shipment.required_vehicle_type,
        is_hazardous: shipment.is_hazardous,

        scheduled_pickup_time: formatLocalISO(shipment.scheduled_pickup_time),
        expected_delivery_time: formatLocalISO(shipment.expected_delivery_time),

        priority: shipment.priority,
        special_instructions: shipment.special_instructions || "",
        invoice_number: shipment.invoice_number || "",
        invoice_value: shipment.invoice_value || undefined,
      });
    }
  }, [shipment, reset]);

  const isDispatched = shipment && ["DISPATCHED", "AT_PICKUP", "IN_TRANSIT", "OUT_FOR_DELIVERY", "DELIVERED"].includes(shipment.status);
  const isCancelled = shipment?.status === "CANCELLED";

  const updateMutation = useMutation({
    mutationFn: (data: ShipmentUpdateRequest) => shipmentApi.updateShipment(id!, data),
    onSuccess: (updated) => {
      toast.success(
        "Shipment Updated",
        `Shipment ${updated.tracking_number} has been updated. Changes are saved to audit history.`
      );
      queryClient.invalidateQueries({ queryKey: ["shipment", id] });
      queryClient.invalidateQueries({ queryKey: ["shipments"] });
      navigate(`/shipments/${id}`);
    },
    onError: (err: any) => {
      const msg = err.response?.data?.detail || "Failed to update shipment.";
      toast.error(
        "Update Failed",
        typeof msg === "string" ? msg : JSON.stringify(msg)
      );
    },
  });

  const onSubmit = (formData: EditFormData) => {
    if (isCancelled) {
      toast.warning("Action Not Allowed", "Cancelled shipments cannot be modified.");
      return;
    }

    const payload: ShipmentUpdateRequest = {
      ...formData,
      scheduled_pickup_time: formData.scheduled_pickup_time
        ? new Date(formData.scheduled_pickup_time).toISOString()
        : undefined,
      expected_delivery_time: formData.expected_delivery_time
        ? new Date(formData.expected_delivery_time).toISOString()
        : undefined,
      customer_reference: formData.customer_reference || undefined,
      origin_dock_number: formData.origin_dock_number || undefined,
      destination_dock_number: formData.destination_dock_number || undefined,
      special_instructions: formData.special_instructions || undefined,
      invoice_number: formData.invoice_number || undefined,
    };

    updateMutation.mutate(payload);
  };

  if (isLoading) return <LoadingState text="Retrieving operational details..." />;
  if (isError || !shipment) return <ErrorState title="Shipment Not Found" message="The requested shipment could not be loaded." onRetry={() => refetch()} />;

  return (
    <div className="p-6 max-w-6xl mx-auto space-y-6">
      <PageHeader
        title={`Edit Shipment ${shipment.tracking_number}`}
        subtitle="Update operational specifications, special instructions, and dock requirements."
        breadcrumbs={[
          { label: "Dashboard", href: "/overview" },
          { label: "Shipments", href: "/shipments" },
          { label: shipment.tracking_number, href: `/shipments/${id}` },
          { label: "Edit", href: `/shipments/${id}/edit` },
        ]}
        actions={
          <Button
            variant="outline"
            size="sm"
            onClick={() => navigate(`/shipments/${id}`)}
            className="h-9 gap-1.5 text-xs text-on-surface-muted"
          >
            <ArrowLeft className="h-3.5 w-3.5" />
            Back to Details
          </Button>
        }
      />

      {isDispatched && (
        <div className="p-4 bg-warning-container border border-amber-200 rounded-xl flex items-start gap-3 text-xs text-amber-800">
          <Lock className="h-4 w-4 text-warning shrink-0 mt-0.5" />
          <div>
            <span className="font-bold">Shipment In Transit / Dispatched:</span> Core routing, scheduled dates, and cargo physical dimensions are locked to protect carrier commitments. You may still update handling instructions and commercial references.
          </div>
        </div>
      )}

      {isCancelled && (
        <div className="p-4 bg-critical-container border border-rose-200 rounded-xl flex items-start gap-3 text-xs text-rose-800">
          <AlertTriangle className="h-4 w-4 text-critical shrink-0 mt-0.5" />
          <div>
            <span className="font-bold">Cancelled Shipment:</span> This shipment has been officially cancelled. No further modifications can be submitted.
          </div>
        </div>
      )}

      <form onSubmit={handleSubmit(onSubmit)} className="space-y-6">
        {/* Section 1: Customer & References */}
        <Card className="bg-surface-card border-outline-variant shadow-xs">
          <CardHeader className="pb-3 border-b border-outline-variant">
            <div className="flex items-center gap-2">
              <FileText className="h-4 w-4 text-primary" />
              <CardTitle className="text-sm font-semibold text-on-surface">
                1. Customer & Commercial References
              </CardTitle>
            </div>
          </CardHeader>
          <CardContent className="pt-4 grid grid-cols-1 md:grid-cols-3 gap-4">
            <FormField label="Customer / Consignor Name" error={errors.customer_name?.message}>
              <Input {...register("customer_name")} disabled={Boolean(isDispatched || isCancelled)} className="text-xs h-9" />
            </FormField>
            <FormField label="Customer Reference / PO #" error={errors.customer_reference?.message}>
              <Input {...register("customer_reference")} disabled={Boolean(isCancelled)} className="text-xs h-9" />
            </FormField>
            <FormField label="Priority Level">
              <select
                {...register("priority")}
                disabled={Boolean(isCancelled)}
                className="w-full text-xs h-9 bg-surface-card border border-outline-variant rounded-md px-3 text-on-surface focus:outline-hidden focus:ring-1 focus:ring-burnt-orange"
              >
                <option value="STANDARD">Standard</option>
                <option value="EXPEDITED">Expedited</option>
                <option value="CRITICAL">Critical</option>
              </select>
            </FormField>
          </CardContent>
        </Card>

        {/* Section 2: Origin & Destination */}
        <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
          <Card className="bg-surface-card border-outline-variant shadow-xs">
            <CardHeader className="pb-3 border-b border-outline-variant bg-surface-container-low/50">
              <div className="flex items-center gap-2">
                <MapPin className="h-4 w-4 text-primary" />
                <CardTitle className="text-sm font-semibold text-on-surface">
                  Origin (Shipper Dock)
                </CardTitle>
              </div>
            </CardHeader>
            <CardContent className="pt-4 space-y-3.5">
              <FormField label="Facility Name" error={errors.origin_name?.message}>
                <Input {...register("origin_name")} disabled={Boolean(isDispatched || isCancelled)} className="text-xs h-9" />
              </FormField>
              <FormField label="Street Address" error={errors.origin_address?.message}>
                <Input {...register("origin_address")} disabled={Boolean(isDispatched || isCancelled)} className="text-xs h-9" />
              </FormField>
              <div className="grid grid-cols-3 gap-2">
                <FormField label="City"><Input {...register("origin_city")} disabled={Boolean(isDispatched || isCancelled)} className="text-xs h-9" /></FormField>
                <FormField label="State"><Input {...register("origin_state")} disabled={Boolean(isDispatched || isCancelled)} className="text-xs h-9" /></FormField>
                <FormField label="Postal"><Input {...register("origin_postal_code")} disabled={Boolean(isDispatched || isCancelled)} className="text-xs h-9" /></FormField>
              </div>
              <div className="grid grid-cols-3 gap-2">
                <FormField label="Dock #"><Input {...register("origin_dock_number")} disabled={Boolean(isCancelled)} className="text-xs h-9" /></FormField>
                <FormField label="Contact"><Input {...register("origin_contact_name")} disabled={Boolean(isCancelled)} className="text-xs h-9" /></FormField>
                <FormField label="Phone"><Input {...register("origin_contact_phone")} disabled={Boolean(isCancelled)} className="text-xs h-9" /></FormField>
              </div>
            </CardContent>
          </Card>

          <Card className="bg-surface-card border-outline-variant shadow-xs">
            <CardHeader className="pb-3 border-b border-outline-variant bg-surface-container-low/50">
              <div className="flex items-center gap-2">
                <MapPin className="h-4 w-4 text-success" />
                <CardTitle className="text-sm font-semibold text-on-surface">
                  Destination (Consignee Dock)
                </CardTitle>
              </div>
            </CardHeader>
            <CardContent className="pt-4 space-y-3.5">
              <FormField label="Facility Name" error={errors.destination_name?.message}>
                <Input {...register("destination_name")} disabled={Boolean(isDispatched || isCancelled)} className="text-xs h-9" />
              </FormField>
              <FormField label="Street Address" error={errors.destination_address?.message}>
                <Input {...register("destination_address")} disabled={Boolean(isDispatched || isCancelled)} className="text-xs h-9" />
              </FormField>
              <div className="grid grid-cols-3 gap-2">
                <FormField label="City"><Input {...register("destination_city")} disabled={Boolean(isDispatched || isCancelled)} className="text-xs h-9" /></FormField>
                <FormField label="State"><Input {...register("destination_state")} disabled={Boolean(isDispatched || isCancelled)} className="text-xs h-9" /></FormField>
                <FormField label="Postal"><Input {...register("destination_postal_code")} disabled={Boolean(isDispatched || isCancelled)} className="text-xs h-9" /></FormField>
              </div>
              <div className="grid grid-cols-3 gap-2">
                <FormField label="Dock / Bay #"><Input {...register("destination_dock_number")} disabled={Boolean(isCancelled)} className="text-xs h-9" /></FormField>
                <FormField label="Contact"><Input {...register("destination_contact_name")} disabled={Boolean(isCancelled)} className="text-xs h-9" /></FormField>
                <FormField label="Phone"><Input {...register("destination_contact_phone")} disabled={Boolean(isCancelled)} className="text-xs h-9" /></FormField>
              </div>
            </CardContent>
          </Card>
        </div>

        {/* Section 3: Cargo & Equipment */}
        <Card className="bg-surface-card border-outline-variant shadow-xs">
          <CardHeader className="pb-3 border-b border-outline-variant">
            <div className="flex items-center gap-2">
              <Package className="h-4 w-4 text-primary" />
              <CardTitle className="text-sm font-semibold text-on-surface">
                2. Cargo Specifications & Handling
              </CardTitle>
            </div>
          </CardHeader>
          <CardContent className="pt-4 space-y-4">
            <FormField label="Cargo Description" error={errors.goods_description?.message}>
              <Input {...register("goods_description")} disabled={Boolean(isDispatched || isCancelled)} className="text-xs h-9" />
            </FormField>

            <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
              <FormField label="Weight (kg)" error={errors.total_weight_kg?.message}>
                <Input type="number" step="0.1" {...register("total_weight_kg")} disabled={Boolean(isDispatched || isCancelled)} className="text-xs h-9 font-mono" />
              </FormField>
              <FormField label="Package Count" error={errors.package_count?.message}>
                <Input type="number" {...register("package_count")} disabled={Boolean(isDispatched || isCancelled)} className="text-xs h-9 font-mono" />
              </FormField>
              <FormField label="Packaging Unit">
                <select {...register("package_unit")} disabled={Boolean(isDispatched || isCancelled)} className="w-full text-xs h-9 bg-surface-card border border-outline-variant rounded-md px-3 text-on-surface">
                  <option value="PALLETS">Pallets</option>
                  <option value="BOXES">Boxes</option>
                  <option value="CARTONS">Cartons</option>
                  <option value="CRATES">Crates</option>
                  <option value="DRUMS">Drums</option>
                  <option value="UNITS">Loose Units</option>
                </select>
              </FormField>
            </div>

            <FormField label="Special Handling Instructions">
              <textarea
                {...register("special_instructions")}
                disabled={Boolean(isCancelled)}
                rows={3}
                className="w-full text-xs rounded-md border border-outline-variant p-2 text-on-surface focus:outline-hidden focus:ring-1 focus:ring-burnt-orange"
              />
            </FormField>
          </CardContent>
        </Card>

        {/* Action Controls */}
        <div className="flex items-center justify-end gap-3 pt-2">
          <Button
            type="button"
            variant="outline"
            onClick={() => navigate(`/shipments/${id}`)}
            disabled={updateMutation.isPending}
            className="h-10 px-5 text-xs text-on-surface"
          >
            Cancel
          </Button>

          {!isCancelled && (
            <Button
              type="submit"
              disabled={updateMutation.isPending}
              className="h-10 px-6 text-xs bg-primary hover:bg-burnt-orange text-white font-semibold shadow-xs gap-2"
            >
              <CheckCircle2 className="h-4 w-4" />
              {updateMutation.isPending ? "Saving Changes..." : "Save Changes"}
            </Button>
          )}
        </div>
      </form>
    </div>
  );
};

export default EditShipmentPage;
