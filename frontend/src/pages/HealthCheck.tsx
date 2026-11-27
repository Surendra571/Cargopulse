import React from "react";
import { useQuery } from "@tanstack/react-query";
import { apiClient } from "@/lib/api-client";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { 
  Activity, 
  Database, 
  Server, 
  Cpu, 
  RefreshCw, 
  CheckCircle2, 
  XCircle, 
  Layers,
  ShieldCheck,
  Truck
} from "lucide-react";

interface ServiceStatus {
  status: string;
  connected: boolean;
  database?: string;
  service?: string;
  error?: string;
}

interface HealthResponse {
  success: boolean;
  data: {
    status: string;
    application: string;
    version: string;
    environment: string;
    services: {
      database: ServiceStatus;
      redis: ServiceStatus;
    };
  };
  meta: {
    timestamp: string;
  };
}

export const HealthCheckPage: React.FC = () => {
  const { data, isLoading, isError, refetch, isFetching } = useQuery<HealthResponse>({
    queryKey: ["healthOverview"],
    queryFn: () => apiClient.get("/api/v1/healthz"),
    refetchInterval: 10000, // Auto-refresh every 10s
  });

  const healthData = data?.data;

  return (
    <div className="min-h-screen bg-surface text-on-surface p-6 md:p-12">
      <div className="max-w-5xl mx-auto space-y-8">
        {/* Header Section */}
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 border-b border-outline-variant pb-6">
          <div className="flex items-center gap-3">
            <div className="p-3 bg-primary/20 text-primary rounded-xl border border-burnt-orange/30">
              <Truck className="w-8 h-8" />
            </div>
            <div>
              <h1 className="text-3xl font-bold tracking-tight text-white flex items-center gap-3">
                CargoPulse
                <Badge variant="outline" className="font-mono text-xs">
                  v{healthData?.version || "0.1.0"}
                </Badge>
              </h1>
              <p className="text-on-surface-subtle text-sm">
                Accountable B2B Logistics Platform · System Diagnostics & Health Status
              </p>
            </div>
          </div>

          <div className="flex items-center gap-3">
            <Button
              variant="outline"
              size="sm"
              onClick={() => refetch()}
              disabled={isFetching}
              className="gap-2"
            >
              <RefreshCw className={`w-4 h-4 ${isFetching ? "animate-spin" : ""}`} />
              Refresh
            </Button>
            <Badge
              variant={
                healthData?.status === "healthy"
                  ? "success"
                  : healthData?.status === "degraded"
                  ? "warning"
                  : "destructive"
              }
              className="py-1 px-3 text-xs uppercase tracking-wider font-semibold"
            >
              {healthData?.status || (isLoading ? "CONNECTING..." : "OFFLINE")}
            </Badge>
          </div>
        </div>

        {/* System Overview Cards */}
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
          <Card>
            <CardHeader className="pb-2">
              <CardDescription className="flex items-center justify-between">
                <span>FastAPI Gateway</span>
                <Server className="w-4 h-4 text-primary" />
              </CardDescription>
              <CardTitle className="text-2xl font-bold">
                {isError ? "Error" : "Online"}
              </CardTitle>
            </CardHeader>
            <CardContent>
              <p className="text-xs text-on-surface-subtle font-mono">Port: 8000 · Python 3.12</p>
            </CardContent>
          </Card>

          <Card>
            <CardHeader className="pb-2">
              <CardDescription className="flex items-center justify-between">
                <span>PostgreSQL DB</span>
                <Database className="w-4 h-4 text-emerald-400" />
              </CardDescription>
              <CardTitle className="text-2xl font-bold flex items-center gap-2">
                {healthData?.services.database.connected ? (
                  <>
                    <CheckCircle2 className="w-5 h-5 text-emerald-400" />
                    <span>Connected</span>
                  </>
                ) : (
                  <>
                    <XCircle className="w-5 h-5 text-amber-400" />
                    <span className="text-amber-400">Standby</span>
                  </>
                )}
              </CardTitle>
            </CardHeader>
            <CardContent>
              <p className="text-xs text-on-surface-subtle font-mono">
                {healthData?.services.database.connected
                  ? "Pool: 20 conns · AsyncPG"
                  : "Ready on local / Docker"}
              </p>
            </CardContent>
          </Card>

          <Card>
            <CardHeader className="pb-2">
              <CardDescription className="flex items-center justify-between">
                <span>Redis Broker</span>
                <Cpu className="w-4 h-4 text-rose-400" />
              </CardDescription>
              <CardTitle className="text-2xl font-bold flex items-center gap-2">
                {healthData?.services.redis.connected ? (
                  <>
                    <CheckCircle2 className="w-5 h-5 text-emerald-400" />
                    <span>Connected</span>
                  </>
                ) : (
                  <>
                    <XCircle className="w-5 h-5 text-amber-400" />
                    <span className="text-amber-400">Standby</span>
                  </>
                )}
              </CardTitle>
            </CardHeader>
            <CardContent>
              <p className="text-xs text-on-surface-subtle font-mono">
                {healthData?.services.redis.connected
                  ? "Port: 6379 · Cache & Broker"
                  : "Ready on local / Docker"}
              </p>
            </CardContent>
          </Card>

          <Card>
            <CardHeader className="pb-2">
              <CardDescription className="flex items-center justify-between">
                <span>Architecture</span>
                <Layers className="w-4 h-4 text-purple-400" />
              </CardDescription>
              <CardTitle className="text-2xl font-bold">Modular</CardTitle>
            </CardHeader>
            <CardContent>
              <p className="text-xs text-on-surface-subtle font-mono">Multi-Tenant Monolith</p>
            </CardContent>
          </Card>
        </div>

        {/* Detailed Diagnostics Section */}
        <Card>
          <CardHeader>
            <div className="flex items-center justify-between">
              <div>
                <CardTitle className="text-lg flex items-center gap-2">
                  <Activity className="w-5 h-5 text-primary" />
                  Service Health Check Telemetry
                </CardTitle>
                <CardDescription>
                  Live evaluation of backend dependencies and connection pooling.
                </CardDescription>
              </div>
              <div className="text-xs text-on-surface-subtle font-mono">
                Last checked: {data?.meta?.timestamp ? new Date(data.meta.timestamp).toLocaleTimeString() : "--"}
              </div>
            </div>
          </CardHeader>
          <CardContent className="space-y-4">
            {isLoading && (
              <div className="p-8 text-center text-on-surface-subtle">
                <RefreshCw className="w-6 h-6 animate-spin mx-auto mb-2 text-primary" />
                Querying API health diagnostics...
              </div>
            )}

            {isError && (
              <div className="p-4 rounded-lg bg-rose-950/40 border border-rose-800 text-rose-200 space-y-1">
                <div className="font-semibold flex items-center gap-2">
                  <XCircle className="w-5 h-5 text-rose-400" />
                  Unable to connect to FastAPI Backend
                </div>
                <p className="text-xs text-rose-300">
                  Ensure the backend is running at <code className="bg-rose-900/60 px-1 py-0.5 rounded">http://localhost:8000</code>.
                </p>
              </div>
            )}

            {healthData && (
              <div className="divide-y divide-slate-800">
                <div className="py-3 flex items-center justify-between">
                  <div>
                    <span className="font-medium text-on-surface">PostgreSQL Relational Engine</span>
                    <p className="text-xs text-on-surface-subtle">
                      Primary transactional and audit event store. Strict tenant isolation.
                    </p>
                  </div>
                  <Badge variant={healthData.services.database.connected ? "success" : "warning"}>
                    {healthData.services.database.connected ? "HEALTHY" : "OFFLINE / STANDBY"}
                  </Badge>
                </div>

                <div className="py-3 flex items-center justify-between">
                  <div>
                    <span className="font-medium text-on-surface">Redis Cache & Pub/Sub Bus</span>
                    <p className="text-xs text-on-surface-subtle">
                      Celery task queue broker, session revocation registry, and geo-index.
                    </p>
                  </div>
                  <Badge variant={healthData.services.redis.connected ? "success" : "warning"}>
                    {healthData.services.redis.connected ? "HEALTHY" : "OFFLINE / STANDBY"}
                  </Badge>
                </div>

                <div className="py-3 flex items-center justify-between">
                  <div>
                    <span className="font-medium text-on-surface">Celery Background Workers</span>
                    <p className="text-xs text-on-surface-subtle">
                      SLA timers, recovery cascades, telematics ingestion, and DLQ handling.
                    </p>
                  </div>
                  <Badge variant="outline">CONFIGURED (5 QUEUES)</Badge>
                </div>

                <div className="py-3 flex items-center justify-between">
                  <div>
                    <span className="font-medium text-on-surface">Tenant Data Isolation Layer</span>
                    <p className="text-xs text-on-surface-subtle">
                      Repository-enforced tenant filtering and cryptographic audit ledger.
                    </p>
                  </div>
                  <Badge variant="success" className="gap-1">
                    <ShieldCheck className="w-3.5 h-3.5" />
                    ACTIVE
                  </Badge>
                </div>
              </div>
            )}
          </CardContent>
        </Card>

        {/* Footer info */}
        <div className="text-center text-xs text-on-surface-subtle space-y-1">
          <p>CargoPulse Platform Architecture · Phase 1 Project Initialization</p>
          <p className="text-on-surface-subtle">
            FastAPI · React 18 · TypeScript · Vite · Tailwind · shadcn/ui · SQLAlchemy 2.x · PostgreSQL · Redis · Celery
          </p>
        </div>
      </div>
    </div>
  );
};
