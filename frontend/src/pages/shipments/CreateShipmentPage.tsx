import React from "react";
import { useNavigate } from "react-router-dom";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import * as z from "zod";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import {
  Package,
  MapPin,
  Calendar,
  AlertTriangle,
  ArrowLeft,
  CheckCircle2,
  FileText,
} from "lucide-react";
import { shipmentApi, ShipmentCreateRequest } from "@/api/shipments";
import { PageHeader } from "@/components/common/PageHeader";
import { FormField } from "@/components/common/FormField";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { Card, CardHeader, CardTitle, CardContent } from "@/components/ui/card";
import { useToast } from "@/context/ToastContext";

// Validation schema using Zod
const shipmentFormSchema = z
  .object({
    // Customer
    customer_name: z.string().min(2, "Customer name must be at least 2 characters"),
    customer_reference: z.string().optional(),

    // Origin
    origin_name: z.string().min(2, "Origin facility name is required"),
    origin_address: z.string().min(5, "Valid street address is required"),
    origin_city: z.string().min(2, "Origin city is required"),
    origin_state: z.string().min(2, "Origin state/province is required"),
    origin_postal_code: z.string().min(3, "Valid postal code is required"),
    origin_dock_number: z.string().optional(),
    origin_contact_name: z.string().min(2, "Origin dock contact person is required"),
    origin_contact_phone: z.string().min(7, "Valid contact telephone number is required"),

    // Destination
    destination_name: z.string().min(2, "Destination facility name is required"),
    destination_address: z.string().min(5, "Valid delivery street address is required"),
    destination_city: z.string().min(2, "Destination city is required"),
    destination_state: z.string().min(2, "Destination state/province is required"),
    destination_postal_code: z.string().min(3, "Valid postal code is required"),
    destination_dock_number: z.string().optional(),
    destination_contact_name: z.string().min(2, "Destination contact person is required"),
    destination_contact_phone: z.string().min(7, "Valid contact telephone number is required"),

    // Cargo Details
    goods_description: z.string().min(3, "Detailed cargo description is required"),
    cargo_category: z.string().default("GENERAL_FREIGHT"),
    total_weight_kg: z.coerce.number().positive("Cargo weight must be strictly positive (greater than 0 kg)"),
    package_count: z.coerce.number().int().positive("Package count must be at least 1 unit"),
    package_unit: z.string().default("PALLETS"),
    total_volume_cbm: z.coerce.number().min(0, "Volume cannot be negative").optional(),
    required_vehicle_type: z.string().default("53' Dry Van"),
    is_hazardous: z.boolean().default(false),

    // Schedule & Timings
    scheduled_pickup_time: z.string().min(1, "Pickup deadline date and time is required"),
    expected_delivery_time: z.string().min(1, "Expected delivery date and time is required"),

    // Priorities & Financials
    priority: z.string().default("STANDARD"),
    special_instructions: z.string().optional(),
    invoice_number: z.string().optional(),
    invoice_value: z.coerce.number().min(0, "Invoice value cannot be negative").optional(),
  })
  .refine(
    (data) => {
      if (!data.scheduled_pickup_time || !data.expected_delivery_time) return true;
      const pickup = new Date(data.scheduled_pickup_time).getTime();
      const delivery = new Date(data.expected_delivery_time).getTime();
      return delivery > pickup;
    },
    {
      message: "Expected delivery time must be strictly after the pickup deadline.",
      path: ["expected_delivery_time"],
    }
  );

type ShipmentFormData = z.infer<typeof shipmentFormSchema>;

export const CreateShipmentPage: React.FC = () => {
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const { toast } = useToast();

  // Helper default dates (pickup tomorrow, delivery 3 days from now)
  const defaultPickup = new Date();
  defaultPickup.setDate(defaultPickup.getDate() + 1);
  defaultPickup.setHours(9, 0, 0, 0);

  const defaultDelivery = new Date();
  defaultDelivery.setDate(defaultDelivery.getDate() + 3);
  defaultDelivery.setHours(17, 0, 0, 0);

  const formatLocalISO = (d: Date) => {
    const tzOffset = d.getTimezoneOffset() * 60000;
    return new Date(d.getTime() - tzOffset).toISOString().slice(0, 16);
  };

  const {
    register,
    handleSubmit,
    watch,
    formState: { errors },
  } = useForm<ShipmentFormData>({
    resolver: zodResolver(shipmentFormSchema),
    defaultValues: {
      cargo_category: "GENERAL_FREIGHT",
      package_unit: "PALLETS",
      required_vehicle_type: "53' Dry Van",
      priority: "STANDARD",
      is_hazardous: false,
      scheduled_pickup_time: formatLocalISO(defaultPickup),
      expected_delivery_time: formatLocalISO(defaultDelivery),
    },
  });

  const isHazardous = watch("is_hazardous");

  const createMutation = useMutation({
    mutationFn: (data: ShipmentCreateRequest) => shipmentApi.createShipment(data),
    onSuccess: (shipment) => {
      toast.success(
        "Shipment Created Successfully",
        `Shipment ${shipment.tracking_number} has been registered and is ready for dispatch matching.`
      );
      queryClient.invalidateQueries({ queryKey: ["shipments"] });
      navigate(`/shipments/${shipment.id}`);
    },
    onError: (err: any) => {
      const msg = err.response?.data?.detail || "Failed to create shipment. Please check the inputs.";
      toast.error(
        "Creation Error",
        typeof msg === "string" ? msg : JSON.stringify(msg)
      );
    },
  });

  const onSubmit = (formData: ShipmentFormData) => {
    // Convert local datetime strings to ISO UTC format for API
    const payload: ShipmentCreateRequest = {
      ...formData,
      scheduled_pickup_time: new Date(formData.scheduled_pickup_time).toISOString(),
      expected_delivery_time: new Date(formData.expected_delivery_time).toISOString(),
      customer_reference: formData.customer_reference || undefined,
      origin_dock_number: formData.origin_dock_number || undefined,
      destination_dock_number: formData.destination_dock_number || undefined,
      special_instructions: formData.special_instructions || undefined,
      invoice_number: formData.invoice_number || undefined,
      total_volume_cbm: formData.total_volume_cbm || undefined,
      invoice_value: formData.invoice_value || undefined,
    };

    createMutation.mutate(payload);
  };

  return (
    <div className="p-6 max-w-6xl mx-auto space-y-6">
      {/* Top Header */}
      <PageHeader
        title="Create Outbound Shipment"
        subtitle="Book a new verified freight consignment with lane specifications, dock timings, and carrier requirements."
        breadcrumbs={[
          { label: "Dashboard", href: "/overview" },
          { label: "Shipments", href: "/shipments" },
          { label: "New Shipment", href: "/shipments/create" },
        ]}
        actions={
          <Button
            variant="outline"
            size="sm"
            onClick={() => navigate("/shipments")}
            className="h-9 gap-1.5 text-xs text-on-surface-muted"
          >
            <ArrowLeft className="h-3.5 w-3.5" />
            Back to Shipments
          </Button>
        }
      />

      <form onSubmit={handleSubmit(onSubmit)} className="space-y-6">
        {/* Section 1: Customer & Commercial References */}
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
            <FormField
              label="Customer / Consignor Name"
              required
              error={errors.customer_name?.message}
            >
              <Input
                {...register("customer_name")}
                placeholder="e.g. Apex Industrial Systems"
                className="text-xs h-9"
              />
            </FormField>

            <FormField
              label="Customer Reference / PO #"
              error={errors.customer_reference?.message}
              hint="Optional customer PO or contract reference"
            >
              <Input
                {...register("customer_reference")}
                placeholder="e.g. PO-2026-8809"
                className="text-xs h-9"
              />
            </FormField>

            <FormField
              label="Priority Level"
              required
              error={errors.priority?.message}
            >
              <select
                {...register("priority")}
                className="w-full text-xs h-9 bg-surface-card border border-outline-variant rounded-md px-3 text-on-surface focus:outline-hidden focus:ring-1 focus:ring-burnt-orange"
              >
                <option value="STANDARD">Standard (Regular Freight)</option>
                <option value="EXPEDITED">Expedited (Time Sensitive)</option>
                <option value="CRITICAL">Critical (High Priority Line-Down)</option>
              </select>
            </FormField>
          </CardContent>
        </Card>

        {/* Section 2: Origin & Destination Routing */}
        <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
          {/* Origin Dock */}
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
              <FormField
                label="Facility / Plant Name"
                required
                error={errors.origin_name?.message}
              >
                <Input
                  {...register("origin_name")}
                  placeholder="e.g. Acme Central Plant"
                  className="text-xs h-9"
                />
              </FormField>

              <FormField
                label="Street Address"
                required
                error={errors.origin_address?.message}
              >
                <Input
                  {...register("origin_address")}
                  placeholder="e.g. 100 Industrial Parkway"
                  className="text-xs h-9"
                />
              </FormField>

              <div className="grid grid-cols-3 gap-2">
                <FormField label="City" required error={errors.origin_city?.message}>
                  <Input {...register("origin_city")} placeholder="City" className="text-xs h-9" />
                </FormField>
                <FormField label="State / Prov" required error={errors.origin_state?.message}>
                  <Input {...register("origin_state")} placeholder="State" className="text-xs h-9" />
                </FormField>
                <FormField label="Postal Code" required error={errors.origin_postal_code?.message}>
                  <Input {...register("origin_postal_code")} placeholder="Postal" className="text-xs h-9" />
                </FormField>
              </div>

              <div className="grid grid-cols-3 gap-2">
                <FormField label="Dock #" error={errors.origin_dock_number?.message}>
                  <Input {...register("origin_dock_number")} placeholder="e.g. Dock 4B" className="text-xs h-9" />
                </FormField>
                <FormField label="Dock Contact" required error={errors.origin_contact_name?.message}>
                  <Input {...register("origin_contact_name")} placeholder="Contact Name" className="text-xs h-9" />
                </FormField>
                <FormField label="Phone" required error={errors.origin_contact_phone?.message}>
                  <Input {...register("origin_contact_phone")} placeholder="Telephone" className="text-xs h-9" />
                </FormField>
              </div>
            </CardContent>
          </Card>

          {/* Destination Consignee */}
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
              <FormField
                label="Facility / Receiver Name"
                required
                error={errors.destination_name?.message}
              >
                <Input
                  {...register("destination_name")}
                  placeholder="e.g. Apex Distribution Hub"
                  className="text-xs h-9"
                />
              </FormField>

              <FormField
                label="Street Address"
                required
                error={errors.destination_address?.message}
              >
                <Input
                  {...register("destination_address")}
                  placeholder="e.g. 450 Logistics Way"
                  className="text-xs h-9"
                />
              </FormField>

              <div className="grid grid-cols-3 gap-2">
                <FormField label="City" required error={errors.destination_city?.message}>
                  <Input {...register("destination_city")} placeholder="City" className="text-xs h-9" />
                </FormField>
                <FormField label="State / Prov" required error={errors.destination_state?.message}>
                  <Input {...register("destination_state")} placeholder="State" className="text-xs h-9" />
                </FormField>
                <FormField label="Postal Code" required error={errors.destination_postal_code?.message}>
                  <Input {...register("destination_postal_code")} placeholder="Postal" className="text-xs h-9" />
                </FormField>
              </div>

              <div className="grid grid-cols-3 gap-2">
                <FormField label="Dock / Bay #" error={errors.destination_dock_number?.message}>
                  <Input {...register("destination_dock_number")} placeholder="e.g. Bay 2" className="text-xs h-9" />
                </FormField>
                <FormField label="Receiving Contact" required error={errors.destination_contact_name?.message}>
                  <Input {...register("destination_contact_name")} placeholder="Contact Name" className="text-xs h-9" />
                </FormField>
                <FormField label="Phone" required error={errors.destination_contact_phone?.message}>
                  <Input {...register("destination_contact_phone")} placeholder="Telephone" className="text-xs h-9" />
                </FormField>
              </div>
            </CardContent>
          </Card>
        </div>

        {/* Section 3: Cargo Specifications & Equipment */}
        <Card className="bg-surface-card border-outline-variant shadow-xs">
          <CardHeader className="pb-3 border-b border-outline-variant">
            <div className="flex items-center gap-2">
              <Package className="h-4 w-4 text-primary" />
              <CardTitle className="text-sm font-semibold text-on-surface">
                2. Cargo Specifications & Equipment Requirements
              </CardTitle>
            </div>
          </CardHeader>
          <CardContent className="pt-4 space-y-4">
            <FormField
              label="Detailed Cargo Description"
              required
              error={errors.goods_description?.message}
            >
              <Input
                {...register("goods_description")}
                placeholder="e.g. Precision CNC Machined Transmission Housings & Mounts"
                className="text-xs h-9"
              />
            </FormField>

            <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
              <FormField
                label="Cargo Category"
                required
                error={errors.cargo_category?.message}
              >
                <select
                  {...register("cargo_category")}
                  className="w-full text-xs h-9 bg-surface-card border border-outline-variant rounded-md px-3 text-on-surface focus:outline-hidden focus:ring-1 focus:ring-burnt-orange"
                >
                  <option value="GENERAL_FREIGHT">General Freight</option>
                  <option value="AUTOMOTIVE">Automotive Parts</option>
                  <option value="ELECTRONICS">Electronics & Tech</option>
                  <option value="PERISHABLES">Perishables & Food</option>
                  <option value="HEAVY_MACHINERY">Heavy Machinery</option>
                  <option value="PHARMACEUTICALS">Pharmaceuticals</option>
                  <option value="RAW_MATERIALS">Raw Materials</option>
                  <option value="HAZARDOUS">Hazardous Materials (HAZMAT)</option>
                </select>
              </FormField>

              <FormField
                label="Total Weight (kg)"
                required
                error={errors.total_weight_kg?.message}
                hint="Must be strictly positive (> 0 kg)"
              >
                <Input
                  type="number"
                  step="0.1"
                  {...register("total_weight_kg")}
                  placeholder="e.g. 4500"
                  className="text-xs h-9 font-mono"
                />
              </FormField>

              <FormField
                label="Package Count"
                required
                error={errors.package_count?.message}
              >
                <Input
                  type="number"
                  {...register("package_count")}
                  placeholder="e.g. 8"
                  className="text-xs h-9 font-mono"
                />
              </FormField>

              <FormField
                label="Packaging Unit"
                required
                error={errors.package_unit?.message}
              >
                <select
                  {...register("package_unit")}
                  className="w-full text-xs h-9 bg-surface-card border border-outline-variant rounded-md px-3 text-on-surface focus:outline-hidden focus:ring-1 focus:ring-burnt-orange"
                >
                  <option value="PALLETS">Pallets</option>
                  <option value="BOXES">Boxes</option>
                  <option value="CARTONS">Cartons</option>
                  <option value="CRATES">Crates</option>
                  <option value="DRUMS">Drums</option>
                  <option value="UNITS">Loose Units</option>
                </select>
              </FormField>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-3 gap-4 pt-1">
              <FormField
                label="Required Equipment / Vehicle"
                required
                error={errors.required_vehicle_type?.message}
              >
                <select
                  {...register("required_vehicle_type")}
                  className="w-full text-xs h-9 bg-surface-card border border-outline-variant rounded-md px-3 text-on-surface focus:outline-hidden focus:ring-1 focus:ring-burnt-orange"
                >
                  <option value="53' Dry Van">53' Dry Van</option>
                  <option value="Flatbed 48'">Flatbed 48'</option>
                  <option value="Refrigerated 53'">Refrigerated 53'</option>
                  <option value="Box Truck 26'">Box Truck 26'</option>
                  <option value="Step Deck">Step Deck</option>
                  <option value="Container Chassis">Container Chassis</option>
                </select>
              </FormField>

              <FormField
                label="Total Volume (CBM)"
                error={errors.total_volume_cbm?.message}
                hint="Optional cubic meters"
              >
                <Input
                  type="number"
                  step="0.01"
                  {...register("total_volume_cbm")}
                  placeholder="e.g. 14.5"
                  className="text-xs h-9 font-mono"
                />
              </FormField>

              <div className="flex items-center gap-3 pt-5">
                <input
                  type="checkbox"
                  id="is_hazardous"
                  {...register("is_hazardous")}
                  className="h-4 w-4 rounded border-outline-strong text-primary focus:ring-burnt-orange"
                />
                <label htmlFor="is_hazardous" className="text-xs font-semibold text-on-surface cursor-pointer">
                  Contains Hazardous Materials (HAZMAT)
                </label>
              </div>
            </div>

            {isHazardous && (
              <div className="p-3 bg-warning-container border border-amber-200 rounded-lg flex items-center gap-2 text-xs text-amber-800">
                <AlertTriangle className="h-4 w-4 text-warning shrink-0" />
                <span>
                  Shipments marked as HAZMAT require specialized transporter endorsements and UN safety placards during transport.
                </span>
              </div>
            )}
          </CardContent>
        </Card>

        {/* Section 4: Schedule, Timings & Dock Instructions */}
        <Card className="bg-surface-card border-outline-variant shadow-xs">
          <CardHeader className="pb-3 border-b border-outline-variant">
            <div className="flex items-center gap-2">
              <Calendar className="h-4 w-4 text-primary" />
              <CardTitle className="text-sm font-semibold text-on-surface">
                3. Pickup & Delivery Deadlines
              </CardTitle>
            </div>
          </CardHeader>
          <CardContent className="pt-4 space-y-4">
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <FormField
                label="Scheduled Pickup Deadline"
                required
                error={errors.scheduled_pickup_time?.message}
                hint="Transporter must arrive at shipper facility before this cutoff"
              >
                <Input
                  type="datetime-local"
                  {...register("scheduled_pickup_time")}
                  className="text-xs h-9 font-mono"
                />
              </FormField>

              <FormField
                label="Expected Delivery Deadline (ETA)"
                required
                error={errors.expected_delivery_time?.message}
                hint="Consignee delivery appointment cutoff (must be strictly after pickup)"
              >
                <Input
                  type="datetime-local"
                  {...register("expected_delivery_time")}
                  className="text-xs h-9 font-mono"
                />
              </FormField>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-3 gap-4 pt-2">
              <div className="md:col-span-2">
                <FormField
                  label="Special Handling Instructions"
                  error={errors.special_instructions?.message}
                  hint="Dock appointment requirements, load securing instructions, or gate pass notes"
                >
                  <textarea
                    {...register("special_instructions")}
                    rows={3}
                    placeholder="e.g. Driver must wear safety vest and steel toe boots. Strapped securely, no double-stacking allowed."
                    className="w-full text-xs rounded-md border border-outline-variant p-2 text-on-surface focus:outline-hidden focus:ring-1 focus:ring-burnt-orange"
                  />
                </FormField>
              </div>

              <div className="space-y-3">
                <FormField
                  label="Invoice / Commercial Value ($)"
                  error={errors.invoice_value?.message}
                >
                  <Input
                    type="number"
                    step="0.01"
                    {...register("invoice_value")}
                    placeholder="e.g. 75000.00"
                    className="text-xs h-9 font-mono"
                  />
                </FormField>

                <FormField
                  label="Commercial Invoice #"
                  error={errors.invoice_number?.message}
                >
                  <Input
                    {...register("invoice_number")}
                    placeholder="e.g. INV-2026-991"
                    className="text-xs h-9"
                  />
                </FormField>
              </div>
            </div>
          </CardContent>
        </Card>

        {/* Action Controls */}
        <div className="flex items-center justify-end gap-3 pt-2">
          <Button
            type="button"
            variant="outline"
            onClick={() => navigate("/shipments")}
            disabled={createMutation.isPending}
            className="h-10 px-5 text-xs text-on-surface"
          >
            Cancel
          </Button>

          <Button
            type="submit"
            disabled={createMutation.isPending}
            className="h-10 px-6 text-xs bg-primary hover:bg-burnt-orange text-white font-semibold shadow-xs gap-2"
          >
            <CheckCircle2 className="h-4 w-4" />
            {createMutation.isPending ? "Creating Shipment..." : "Register Shipment"}
          </Button>
        </div>
      </form>
    </div>
  );
};

export default CreateShipmentPage;
