import { apiClient } from "@/lib/api-client";

export interface IntegrationConnection {
  id: string;
  organization_id: string;
  name: string;
  slug?: string;
  integration_type: string;
  adapter_type: string;
  is_active: boolean;
  base_url?: string;
  webhook_url?: string;
  webhook_secret_preview?: string;
  api_key_preview?: string;
  health_status: string;
  consecutive_failures: number;
  stats: Record<string, any>;
  last_synced_at?: string;
  sync_status: string;
  created_at: string;
  updated_at: string;
}

export interface WebhookEventItem {
  id: string;
  organization_id?: string;
  integration_id?: string;
  provider: string;
  source: string;
  event_name: string;
  external_event_id?: string;
  idempotency_key?: string;
  status: string;
  retry_count: number;
  max_retries: number;
  next_retry_at?: string;
  processed_at?: string;
  last_attempt_at?: string;
  error_message?: string;
  error_type?: string;
  is_dead_letter: boolean;
  replay_count: number;
  last_replayed_at?: string;
  last_replayed_by_id?: string;
  created_at: string;
  payload: Record<string, any>;
  normalized_payload: Record<string, any>;
}

export interface OutboxEventItem {
  id: string;
  organization_id: string;
  aggregate_type: string;
  aggregate_id: string;
  event_type: string;
  destination?: string;
  idempotency_key?: string;
  status: "PENDING" | "PROCESSING" | "PUBLISHED" | "FAILED" | "DEAD_LETTER";
  retry_count: number;
  max_retries: number;
  next_retry_at?: string;
  processed_at?: string;
  error_message?: string;
  is_dead_letter: boolean;
  replay_count: number;
  created_at: string;
  payload: Record<string, any>;
}

export interface IntegrationDashboardMetrics {
  total_webhooks: number;
  successful_webhooks: number;
  failed_webhooks: number;
  pending_webhooks: number;
  retry_webhooks: number;
  dlq_count: number;
  total_outbox: number;
  published_outbox: number;
  pending_outbox: number;
  failed_outbox: number;
  system_health: "HEALTHY" | "DEGRADED" | "CRITICAL";
  connections_count: number;
  healthy_connections_count: number;
  recent_errors: Array<{
    id: string;
    type: string;
    provider: string;
    error_message: string;
    error_type: string;
    timestamp: string;
    is_dead_letter: boolean;
    retry_count: number;
  }>;
}

export interface CreateConnectionPayload {
  name: string;
  slug?: string;
  integration_type: string;
  adapter_type: string;
  base_url?: string;
  api_key?: string;
  webhook_secret?: string;
  is_active?: boolean;
}

export const integrationsApi = {
  // Metrics
  getDashboardMetrics: async (): Promise<IntegrationDashboardMetrics> => {
    const res = await apiClient.get<IntegrationDashboardMetrics>("/integrations/monitoring/dashboard");
    return res as any;
  },

  // Connections
  listConnections: async (): Promise<IntegrationConnection[]> => {
    const res = await apiClient.get<IntegrationConnection[]>("/integrations/connections");
    return res as any;
  },

  createConnection: async (payload: CreateConnectionPayload): Promise<IntegrationConnection> => {
    const res = await apiClient.post<IntegrationConnection>("/integrations/connections", payload);
    return res as any;
  },

  updateConnection: async (id: string, payload: Partial<CreateConnectionPayload>): Promise<IntegrationConnection> => {
    const res = await apiClient.patch<IntegrationConnection>(`/integrations/connections/${id}`, payload);
    return res as any;
  },

  deleteConnection: async (id: string): Promise<void> => {
    await apiClient.delete(`/integrations/connections/${id}`);
  },

  regenerateSecret: async (id: string): Promise<{ webhook_secret: string; message: string }> => {
    const res = await apiClient.post<{ webhook_secret: string; message: string }>(
      `/integrations/connections/${id}/regenerate-secret`
    );
    return res as any;
  },

  // Feeds
  listWebhooks: async (params?: {
    status?: string;
    provider?: string;
    is_dead_letter?: boolean;
    limit?: number;
    offset?: number;
  }): Promise<WebhookEventItem[]> => {
    const res = await apiClient.get<WebhookEventItem[]>("/integrations/webhooks", { params });
    return res as any;
  },

  listOutbox: async (params?: {
    status?: string;
    aggregate_type?: string;
    is_dead_letter?: boolean;
    limit?: number;
    offset?: number;
  }): Promise<OutboxEventItem[]> => {
    const res = await apiClient.get<OutboxEventItem[]>("/integrations/outbox", { params });
    return res as any;
  },

  // DLQ & Replay
  listDLQ: async (eventSource: "webhook" | "outbox" = "webhook", limit = 50): Promise<any[]> => {
    const res = await apiClient.get<any[]>("/integrations/dlq", {
      params: { event_source: eventSource, limit },
    });
    return res as any;
  },

  replayEvent: async (eventSource: "webhook" | "outbox", eventId: string): Promise<any> => {
    const res = await apiClient.post(`/integrations/dlq/${eventSource}/${eventId}/replay`);
    return res as any;
  },

  replayBatch: async (eventSource: "webhook" | "outbox", eventIds: string[]): Promise<any> => {
    const res = await apiClient.post("/integrations/dlq/replay-batch", {
      event_source: eventSource,
      event_ids: eventIds,
    });
    return res as any;
  },

  // Maintenance Sweeps
  triggerOutboxProcess: async (): Promise<any> => {
    const res = await apiClient.post("/integrations/outbox/process");
    return res as any;
  },

  triggerWebhooksProcess: async (): Promise<any> => {
    const res = await apiClient.post("/integrations/webhooks/process");
    return res as any;
  },

  triggerRecoverHung: async (): Promise<any> => {
    const res = await apiClient.post("/integrations/recover-hung");
    return res as any;
  },
};
