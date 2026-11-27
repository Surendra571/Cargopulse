import React from "react";
import { BrowserRouter, Routes, Route, Navigate } from "react-router-dom";
import { QueryClientProvider } from "@tanstack/react-query";
import { queryClient } from "@/lib/query-client";
import { AuthProvider } from "@/context/AuthContext";
import { ToastProvider } from "@/context/ToastContext";
import { ProtectedRoute } from "@/components/auth/ProtectedRoute";
import { PublicOnlyRoute } from "@/components/auth/PublicOnlyRoute";
import { AppLayout } from "@/components/layout/AppLayout";
import { LoginPage } from "@/pages/auth/LoginPage";
import { RegisterPage } from "@/pages/auth/RegisterPage";
import { ForgotPasswordPage } from "@/pages/auth/ForgotPasswordPage";
import { ResetPasswordPage } from "@/pages/auth/ResetPasswordPage";
import { ProfilePage } from "@/pages/auth/ProfilePage";
import { ChangePasswordPage } from "@/pages/auth/ChangePasswordPage";
import { OrganizationProfilePage } from "@/pages/organization/OrganizationProfilePage";
import { UserManagementPage } from "@/pages/organization/UserManagementPage";
import { OverviewPage } from "@/pages/dashboard/OverviewPage";
import { ShipmentListPage } from "@/pages/shipments/ShipmentListPage";
import { CreateShipmentPage } from "@/pages/shipments/CreateShipmentPage";
import { ShipmentDetailPage } from "@/pages/shipments/ShipmentDetailPage";
import { EditShipmentPage } from "@/pages/shipments/EditShipmentPage";
import { TransporterListPage } from "@/pages/transporters/TransporterListPage";
import { TransporterDetailPage } from "@/pages/transporters/TransporterDetailPage";
import { VehicleListPage } from "@/pages/vehicles/VehicleListPage";
import { DriverListPage } from "@/pages/drivers/DriverListPage";
import { MatchingPage } from "@/pages/matching/MatchingPage";
import { BookingListPage } from "@/pages/bookings/BookingListPage";
import { BookingDetailPage } from "@/pages/bookings/BookingDetailPage";
import { PickupMonitoringPage } from "@/pages/monitoring/PickupMonitoringPage";
import { RecoveryCenterPage } from "@/pages/monitoring/RecoveryCenterPage";
import { TrackingListPage } from "@/pages/tracking/TrackingListPage";
import { TrackingDetailPage } from "@/pages/tracking/TrackingDetailPage";
import { ExceptionListPage } from "@/pages/exceptions/ExceptionListPage";
import { ExceptionDetailPage } from "@/pages/exceptions/ExceptionDetailPage";
import { AICoordinatorPage } from "@/pages/ai/AICoordinatorPage";
import { ReconciliationPage } from "@/pages/reconciliation/ReconciliationPage";
import { AnalyticsPage } from "@/pages/analytics/AnalyticsPage";
import { AuditTrailPage } from "@/pages/audit/AuditTrailPage";
import { PODListPage } from "@/pages/pod/PODListPage";
import { PODReviewPage } from "@/pages/pod/PODReviewPage";
import { DriverPODPage } from "@/pages/pod/DriverPODPage";
import { IntegrationDashboardPage } from "@/pages/integrations/IntegrationDashboardPage";
import { HealthCheckPage } from "@/pages/HealthCheck";

export const App: React.FC = () => {
  return (
    <QueryClientProvider client={queryClient}>
      <AuthProvider>
        <ToastProvider>
          <BrowserRouter>
            <Routes>
              {/* Public utility route */}
              <Route path="/health" element={<HealthCheckPage />} />

              {/* Public-only authentication routes (redirect to /overview if logged in) */}
              <Route element={<PublicOnlyRoute />}>
                <Route path="/login" element={<LoginPage />} />
                <Route path="/register" element={<RegisterPage />} />
                <Route path="/forgot-password" element={<ForgotPasswordPage />} />
                <Route path="/reset-password" element={<ResetPasswordPage />} />
              </Route>

              {/* Protected enterprise console routes wrapped in AppLayout */}
              <Route element={<ProtectedRoute />}>
                <Route element={<AppLayout />}>
                  {/* Core Overview */}
                  <Route path="/overview" element={<OverviewPage />} />

                  {/* Operational Logistics Modules */}
                  <Route path="/shipments" element={<ShipmentListPage />} />
                  <Route path="/shipments/create" element={<CreateShipmentPage />} />
                  <Route path="/shipments/:id" element={<ShipmentDetailPage />} />
                  <Route path="/shipments/:id/edit" element={<EditShipmentPage />} />
                  <Route path="/transporters" element={<TransporterListPage />} />
                  <Route path="/transporters/:id" element={<TransporterDetailPage />} />
                  <Route path="/vehicles" element={<VehicleListPage />} />
                  <Route path="/drivers" element={<DriverListPage />} />
                  <Route path="/matching" element={<MatchingPage />} />
                  <Route path="/shipments/:id/match" element={<MatchingPage />} />
                  <Route path="/bookings" element={<BookingListPage />} />
                  <Route path="/bookings/:id" element={<BookingDetailPage />} />
                  <Route path="/pickup-monitoring" element={<PickupMonitoringPage />} />
                  <Route path="/recovery" element={<RecoveryCenterPage />} />
                  <Route path="/tracking" element={<TrackingListPage />} />
                  <Route path="/tracking/:id" element={<TrackingDetailPage />} />

                  {/* Intelligence & Exceptions */}
                  <Route path="/exceptions" element={<ExceptionListPage />} />
                  <Route path="/exceptions/:id" element={<ExceptionDetailPage />} />
                  <Route path="/ai-coordinator" element={<AICoordinatorPage />} />
                  <Route path="/proof-of-delivery" element={<PODListPage />} />
                  <Route path="/pod" element={<PODListPage />} />
                  <Route path="/pod/review/:shipmentId" element={<PODReviewPage />} />
                  <Route path="/pod/submit/:shipmentId" element={<DriverPODPage />} />
                  <Route path="/reconciliation" element={<ReconciliationPage />} />
                  <Route path="/analytics" element={<AnalyticsPage />} />

                  {/* Admin & Security */}
                  <Route path="/integrations" element={<IntegrationDashboardPage initialTab="overview" />} />
                  <Route path="/integrations/dashboard" element={<IntegrationDashboardPage initialTab="overview" />} />
                  <Route path="/integrations/webhooks" element={<IntegrationDashboardPage initialTab="webhooks" />} />
                  <Route path="/integrations/retry-queue" element={<IntegrationDashboardPage initialTab="outbox" />} />
                  <Route path="/integrations/dlq" element={<IntegrationDashboardPage initialTab="dlq" />} />
                  <Route path="/audit-trail" element={<AuditTrailPage />} />

                  {/* Settings & User Management */}
                  <Route path="/profile" element={<ProfilePage />} />
                  <Route path="/change-password" element={<ChangePasswordPage />} />
                  <Route path="/organization" element={<OrganizationProfilePage />} />
                  <Route path="/organization/users" element={<UserManagementPage />} />
                </Route>
              </Route>

              {/* Root & Fallback Redirection */}
              <Route path="/" element={<Navigate to="/overview" replace />} />
              <Route path="*" element={<Navigate to="/overview" replace />} />
            </Routes>
          </BrowserRouter>
        </ToastProvider>
      </AuthProvider>
    </QueryClientProvider>
  );
};

export default App;
