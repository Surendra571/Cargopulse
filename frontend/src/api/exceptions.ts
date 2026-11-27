import { apiClient } from "@/lib/api-client";

// ============================================================================
// Enums & Types
// ============================================================================

export type ExceptionType =
  | "PICKUP_OVERDUE"
  | "BOOKING_REJECTED"
  | "BOOKING_EXPIRED"
  | "VEHICLE_UNAVAILABLE"
  | "TRACKING_STALE"
  | "DELIVERY_DELAYED"
  | "POD_MISSING"
  | "DELIVERY_DISCREPANCY"
  | "WEBHOOK_FAILURE"
  | "INTEGRATION_FAILURE"
  | "MISSED_PICKUP"
  | "DOCUMENTS_MISSING"
  | "CAPACITY_UNAVAILABLE"
  | "EQUIPMENT_MISMATCH"
  | "ROUTE_DEVIATION"
  | "DAMAGE_REPORTED"
  | "BILLING_DISPUTE"
  | "COMPLIANCE_BREACH"
  | "CUSTOMS_HOLD";

export type ExceptionSeverity = "LOW" | "MEDIUM" | "HIGH" | "CRITICAL";

export type ExceptionPriority = "LOW" | "MEDIUM" | "HIGH" | "CRITICAL";

export type ExceptionStatus =
  | "OPEN"
  | "ACKNOWLEDGED"
  | "INVESTIGATING"
  | "RESOLVING"
  | "RESOLVED"
  | "CLOSED";

export interface ExceptionUserSummary {
  id: string;
  full_name: string;
  email: string;
}

export interface ExceptionShipmentSummary {
  id: string;
  tracking_number: string;
  status: string;
  origin_city: string;
  destination_city: string;
}

export interface ExceptionTransporterSummary {
  id: string;
  name: string;
  code: string;
}

export interface ExceptionRecord {
  id: string;
  organization_id: string;
  shipment_id?: string | null;
  transporter_id?: string | null;
  exception_type: ExceptionType;
  severity: ExceptionSeverity;
  priority: ExceptionPriority;
  status: ExceptionStatus;
  title: string;
  description: string;
  root_cause?: string | null;
  escalation_level: number;
  escalated_at?: string | null;
  reported_at: string;
  acknowledged_at?: string | null;
  acknowledged_by_user_id?: string | null;
  resolved_at?: string | null;
  resolution_notes?: string | null;
  closed_at?: string | null;
  closed_by_user_id?: string | null;
  closure_reason?: string | null;
  reported_by_user_id?: string | null;
  assigned_owner_id?: string | null;
  context_data?: Record<string, any>;
  created_at: string;
  updated_at: string;

  shipment?: ExceptionShipmentSummary | null;
  transporter?: ExceptionTransporterSummary | null;
  assigned_owner?: ExceptionUserSummary | null;
}

export interface ExceptionDetail extends ExceptionRecord {
  recovery_cases: Array<Record<string, any>>;
  audit_trail: Array<{
    id: string;
    action: string;
    details: string;
    user_name: string;
    timestamp: string;
  }>;
}

export interface ExceptionListResponse {
  items: ExceptionRecord[];
  total: number;
  page: number;
  page_size: number;
  pages: number;
}

export interface ExceptionMetrics {
  total_exceptions: number;
  open_exceptions: number;
  investigating_exceptions: number;
  resolved_exceptions: number;
  closed_exceptions: number;
  critical_count: number;
  high_count: number;
  medium_count: number;
  low_count: number;
  by_type: Record<string, number>;
  mean_resolution_hours: number;
}

// ============================================================================
// API Methods
// ============================================================================

export const exceptionsApi = {
  listExceptions: async (params?: {
    page?: number;
    page_size?: number;
    status?: string;
    severity?: string;
    priority?: string;
    exception_type?: string;
    shipment_id?: string;
    transporter_id?: string;
    assigned_owner_id?: string;
    search?: string;
  }): Promise<ExceptionListResponse> => {
    const res = await apiClient.get<ExceptionListResponse>("/exceptions", { params });
    return res as any;
  },

  getMetrics: async (): Promise<ExceptionMetrics> => {
    const res = await apiClient.get<ExceptionMetrics>("/exceptions/metrics");
    return res as any;
  },

  getException: async (id: string): Promise<ExceptionDetail> => {
    const res = await apiClient.get<ExceptionDetail>(`/exceptions/${id}`);
    return res as any;
  },

  createException: async (data: {
    shipment_id?: string;
    transporter_id?: string;
    exception_type: ExceptionType;
    severity?: ExceptionSeverity;
    priority?: ExceptionPriority;
    title: string;
    description: string;
    assigned_owner_id?: string;
    context_data?: Record<string, any>;
  }): Promise<ExceptionRecord> => {
    const res = await apiClient.post<ExceptionRecord>("/exceptions", data);
    return res as any;
  },

  updateException: async (
    id: string,
    data: {
      title?: string;
      description?: string;
      severity?: ExceptionSeverity;
      priority?: ExceptionPriority;
      assigned_owner_id?: string;
    }
  ): Promise<ExceptionRecord> => {
    const res = await apiClient.patch<ExceptionRecord>(`/exceptions/${id}`, data);
    return res as any;
  },

  acknowledgeException: async (
    id: string,
    notes?: string
  ): Promise<ExceptionRecord> => {
    const res = await apiClient.post<ExceptionRecord>(
      `/exceptions/${id}/acknowledge`,
      { notes }
    );
    return res as any;
  },

  assignException: async (
    id: string,
    assignedOwnerId: string,
    notes?: string
  ): Promise<ExceptionRecord> => {
    const res = await apiClient.post<ExceptionRecord>(
      `/exceptions/${id}/assign`,
      { assigned_owner_id: assignedOwnerId, notes }
    );
    return res as any;
  },

  escalateException: async (
    id: string,
    data: {
      target_severity?: ExceptionSeverity;
      escalation_reason: string;
    }
  ): Promise<ExceptionRecord> => {
    const res = await apiClient.post<ExceptionRecord>(
      `/exceptions/${id}/escalate`,
      data
    );
    return res as any;
  },

  resolveException: async (
    id: string,
    data: {
      root_cause: string;
      resolution_notes: string;
    }
  ): Promise<ExceptionRecord> => {
    const res = await apiClient.post<ExceptionRecord>(
      `/exceptions/${id}/resolve`,
      data
    );
    return res as any;
  },

  closeException: async (
    id: string,
    data: {
      closure_reason: string;
    }
  ): Promise<ExceptionRecord> => {
    const res = await apiClient.post<ExceptionRecord>(
      `/exceptions/${id}/close`,
      data
    );
    return res as any;
  },
};
