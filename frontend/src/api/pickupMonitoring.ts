import { apiClient } from "@/lib/api-client";

// ============================================================================
// Enums & Types
// ============================================================================

export type CommitmentStatus =
  | "PENDING"
  | "REMINDER_SENT"
  | "AT_RISK"
  | "ARRIVED"
  | "STARTED"
  | "COMPLETED"
  | "MISSED"
  | "CANCELLED";

export type RecoveryStrategy =
  | "REASSIGN_TRANSPORTER"
  | "EXPEDITE_SERVICE"
  | "REROUTE_SHIPMENT"
  | "SPLIT_CONSIGNMENT"
  | "CUSTOMER_NOTIFICATION"
  | "MANUAL_INTERVENTION";

export type RecoveryStatus =
  | "OPEN"
  | "PROPOSED"
  | "APPROVED"
  | "EXECUTING"
  | "RESOLVED"
  | "FAILED";

export interface CommitmentVehicleSummary {
  id: string;
  license_plate: string;
  vehicle_type: string;
  capacity_kg: number;
}

export interface CommitmentDriverSummary {
  id: string;
  first_name: string;
  last_name: string;
  phone: string;
  license_number: string;
}

export interface CommitmentTransporterSummary {
  id: string;
  name: string;
  code: string;
  phone: string;
  reliability_score: number;
}

export interface CommitmentShipmentSummary {
  id: string;
  tracking_number: string;
  status: string;
  customer_name?: string | null;
  origin_city: string;
  destination_city: string;
  pickup_deadline: string;
  total_weight_kg: number;
}

export interface PickupCommitment {
  id: string;
  organization_id: string;
  shipment_id: string;
  transporter_id: string;
  booking_id?: string | null;
  assigned_vehicle_id?: string | null;
  assigned_driver_id?: string | null;
  pickup_deadline: string;
  expected_arrival?: string | null;
  status: CommitmentStatus;
  reminder_sent_at?: string | null;
  at_risk_flagged_at?: string | null;
  arrival_reported_at?: string | null;
  pickup_started_at?: string | null;
  pickup_completed_at?: string | null;
  missed_detected_at?: string | null;
  is_breached: boolean;
  exception_id?: string | null;
  commitment_metadata?: Record<string, any>;
  created_at: string;
  updated_at: string;

  shipment?: CommitmentShipmentSummary | null;
  transporter?: CommitmentTransporterSummary | null;
  vehicle?: CommitmentVehicleSummary | null;
  driver?: CommitmentDriverSummary | null;
}

export interface PickupCommitmentListResponse {
  items: PickupCommitment[];
  total: number;
  page: number;
  page_size: number;
  pages: number;
}

export interface RecoveryCase {
  id: string;
  organization_id: string;
  exception_id: string;
  shipment_id?: string | null;
  case_number: string;
  strategy: RecoveryStrategy;
  status: RecoveryStatus;
  approval_status: string;
  proposed_solution: string;
  estimated_cost_impact: number;
  original_transporter_id?: string | null;
  replacement_transporter_id?: string | null;
  replacement_booking_id?: string | null;
  approved_by_user_id?: string | null;
  approved_at?: string | null;
  resolved_at?: string | null;
  resolution_summary?: string | null;
  ai_generated: boolean;
  failure_data?: Record<string, any> | null;
  alternatives_data?: Array<{
    transporter_id: string;
    transporter_name: string;
    reliability_score: number;
    match_score: number;
    estimated_cost: number;
    fit_reason: string;
  }> | null;
  created_at: string;
  updated_at: string;
}

export interface RecoveryCaseListResponse {
  items: RecoveryCase[];
  total: number;
  page: number;
  page_size: number;
  pages: number;
}

export interface PickupScanResponse {
  scanned_count: number;
  reminders_sent: number;
  at_risk_flagged: number;
  missed_detected: number;
  exceptions_created: number;
  recovery_cases_opened: number;
  simulated_now: string;
}

export interface SimulateScenarioResponse {
  scenario_id: string;
  status: string;
  shipment_id: string;
  tracking_number: string;
  transporter_a_name: string;
  transporter_c_name: string;
  pickup_deadline: string;
  milestones: Array<{
    step: string;
    description: string;
    status: string;
    timestamp?: string;
  }>;
  recovery_case_number: string;
  replacement_booking_ref: string;
  assignment_history: Array<{
    transporter_name: string;
    status: string;
    reason?: string;
  }>;
}

// ============================================================================
// API Methods
// ============================================================================

export const pickupMonitoringApi = {
  listCommitments: async (params?: {
    page?: number;
    page_size?: number;
    status?: string;
    shipment_id?: string;
    transporter_id?: string;
    is_breached?: boolean;
  }): Promise<PickupCommitmentListResponse> => {
    const res = await apiClient.get<PickupCommitmentListResponse>(
      "/pickup-monitoring/commitments",
      { params }
    );
    return res as any;
  },

  getCommitment: async (commitmentId: string): Promise<PickupCommitment> => {
    const res = await apiClient.get<PickupCommitment>(
      `/pickup-monitoring/commitments/${commitmentId}`
    );
    return res as any;
  },

  reportArrival: async (
    commitmentId: string,
    data?: {
      arrived_at?: string;
      dock_number?: string;
      notes?: string;
      telematics_latitude?: number;
      telematics_longitude?: number;
    }
  ): Promise<PickupCommitment> => {
    const res = await apiClient.post<PickupCommitment>(
      `/pickup-monitoring/commitments/${commitmentId}/arrival`,
      data || {}
    );
    return res as any;
  },

  startPickup: async (
    commitmentId: string,
    data?: {
      started_at?: string;
      bay_number?: string;
      notes?: string;
    }
  ): Promise<PickupCommitment> => {
    const res = await apiClient.post<PickupCommitment>(
      `/pickup-monitoring/commitments/${commitmentId}/start-pickup`,
      data || {}
    );
    return res as any;
  },

  completePickup: async (
    commitmentId: string,
    data?: {
      completed_at?: string;
      bill_of_lading_number?: string;
      loaded_weight_kg?: number;
      seal_number?: string;
      notes?: string;
    }
  ): Promise<PickupCommitment> => {
    const res = await apiClient.post<PickupCommitment>(
      `/pickup-monitoring/commitments/${commitmentId}/complete-pickup`,
      data || {}
    );
    return res as any;
  },

  failPickup: async (
    commitmentId: string,
    data: {
      failure_reason: string;
      penalty_amount?: number;
      notes?: string;
    }
  ): Promise<PickupCommitment> => {
    const res = await apiClient.post<PickupCommitment>(
      `/pickup-monitoring/commitments/${commitmentId}/fail-pickup`,
      data
    );
    return res as any;
  },

  scanCommitments: async (simulatedNow?: string): Promise<PickupScanResponse> => {
    const res = await apiClient.post<PickupScanResponse>(
      "/pickup-monitoring/scan",
      {},
      { params: simulatedNow ? { simulated_now: simulatedNow } : undefined }
    );
    return res as any;
  },

  listRecoveryCases: async (params?: {
    page?: number;
    page_size?: number;
    status?: string;
    approval_status?: string;
    shipment_id?: string;
  }): Promise<RecoveryCaseListResponse> => {
    const res = await apiClient.get<RecoveryCaseListResponse>(
      "/pickup-monitoring/recovery-cases",
      { params }
    );
    return res as any;
  },

  getRecoveryCase: async (caseId: string): Promise<RecoveryCase> => {
    const res = await apiClient.get<RecoveryCase>(
      `/pickup-monitoring/recovery-cases/${caseId}`
    );
    return res as any;
  },

  approveRecovery: async (
    caseId: string,
    data: {
      replacement_transporter_id: string;
      agreed_rate?: number;
      vehicle_id?: string;
      driver_id?: string;
      notes?: string;
    }
  ): Promise<RecoveryCase> => {
    const res = await apiClient.post<RecoveryCase>(
      `/pickup-monitoring/recovery-cases/${caseId}/approve`,
      data
    );
    return res as any;
  },

  simulateScenario: async (data?: {
    customer_name?: string;
    scheduled_hour_offset?: number;
  }): Promise<SimulateScenarioResponse> => {
    const res = await apiClient.post<SimulateScenarioResponse>(
      "/pickup-monitoring/simulate-scenario",
      data || {}
    );
    return res as any;
  },
};
