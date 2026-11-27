import React, { useEffect, useState } from "react";
import { apiClient } from "@/lib/api-client";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Card, CardHeader, CardTitle, CardDescription, CardContent, CardFooter } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Building2, Save, Settings as SettingsIcon, CheckCircle2, AlertCircle } from "lucide-react";

interface OrganizationDetails {
  id: string;
  name: string;
  slug: string;
  org_type: string;
  is_active: boolean;
  billing_email?: string | null;
  tax_identifier?: string | null;
  settings?: Record<string, any>;
  created_at: string;
}

export const OrganizationProfilePage: React.FC = () => {
  const [org, setOrg] = useState<OrganizationDetails | null>(null);
  const [loading, setLoading] = useState(true);
  const [savingProfile, setSavingProfile] = useState(false);
  const [savingSettings, setSavingSettings] = useState(false);
  const [message, setMessage] = useState<{ type: "success" | "error"; text: string } | null>(null);

  // Profile Form state
  const [name, setName] = useState("");
  const [billingEmail, setBillingEmail] = useState("");
  const [taxIdentifier, setTaxIdentifier] = useState("");

  // Operational Settings state
  const [defaultSlaHours, setDefaultSlaHours] = useState<number>(4);
  const [autoDispatch, setAutoDispatch] = useState<boolean>(true);
  const [requirePodVerification, setRequirePodVerification] = useState<boolean>(true);

  useEffect(() => {
    fetchOrgDetails();
  }, []);

  const fetchOrgDetails = async () => {
    try {
      setLoading(true);
      const res: any = await apiClient.get("/api/v1/organizations/me");
      setOrg(res);
      setName(res.name || "");
      setBillingEmail(res.billing_email || "");
      setTaxIdentifier(res.tax_identifier || "");

      const settings = res.settings || {};
      if (settings.default_sla_hours !== undefined) setDefaultSlaHours(settings.default_sla_hours);
      if (settings.auto_dispatch !== undefined) setAutoDispatch(settings.auto_dispatch);
      if (settings.require_pod_verification !== undefined) setRequirePodVerification(settings.require_pod_verification);
    } catch (err: any) {
      setMessage({ type: "error", text: err.response?.data?.detail || "Failed to load organization profile." });
    } finally {
      setLoading(false);
    }
  };

  const handleProfileSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setSavingProfile(true);
    setMessage(null);
    try {
      const res: any = await apiClient.put("/api/v1/organizations/me", {
        name,
        billing_email: billingEmail || null,
        tax_identifier: taxIdentifier || null,
      });
      setOrg(res);
      setMessage({ type: "success", text: "Organization profile updated successfully." });
    } catch (err: any) {
      setMessage({ type: "error", text: err.response?.data?.detail || "Failed to update organization profile." });
    } finally {
      setSavingProfile(false);
    }
  };

  const handleSettingsSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setSavingSettings(true);
    setMessage(null);
    try {
      const updatedSettings = {
        default_sla_hours: Number(defaultSlaHours),
        auto_dispatch: autoDispatch,
        require_pod_verification: requirePodVerification,
      };
      await apiClient.patch("/api/v1/organizations/me/settings", {
        settings: updatedSettings,
      });
      setMessage({ type: "success", text: "Operational settings updated successfully." });
    } catch (err: any) {
      setMessage({ type: "error", text: err.response?.data?.detail || "Failed to update settings." });
    } finally {
      setSavingSettings(false);
    }
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center min-h-[50vh]">
        <div className="h-8 w-8 animate-spin rounded-full border-4 border-burnt-orange border-t-transparent" />
      </div>
    );
  }

  return (
    <div className="max-w-5xl mx-auto px-4 py-8 space-y-6">
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4 pb-4 border-b border-outline-variant">
        <div>
          <h1 className="text-2xl font-bold tracking-tight text-white flex items-center gap-2">
            <Building2 className="h-6 w-6 text-primary" />
            Organization Profile
          </h1>
          <p className="text-sm text-on-surface-subtle mt-1">
            Manage company details, tenant isolation boundaries, and operational dispatch settings.
          </p>
        </div>
        <div className="flex items-center gap-2">
          <Badge variant="outline" className="border-burnt-orange/40 text-primary font-medium">
            {org?.org_type}
          </Badge>
          <Badge variant="outline" className="border-emerald-500/40 text-emerald-400 font-medium">
            Tenant Active
          </Badge>
        </div>
      </div>

      {message && (
        <Alert
          className={
            message.type === "success"
              ? "border-emerald-500/30 bg-emerald-950/20 text-emerald-300"
              : "border-rose-500/30 bg-rose-950/20 text-rose-300"
          }
        >
          {message.type === "success" ? (
            <CheckCircle2 className="h-4 w-4 text-emerald-400" />
          ) : (
            <AlertCircle className="h-4 w-4 text-rose-400" />
          )}
          <AlertDescription>{message.text}</AlertDescription>
        </Alert>
      )}

      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        {/* Profile Card */}
        <Card className="border-outline-variant bg-surface-card/60">
          <form onSubmit={handleProfileSubmit}>
            <CardHeader>
              <CardTitle className="text-lg font-semibold text-white">General Information</CardTitle>
              <CardDescription className="text-on-surface-subtle">
                Update legal business name and billing contacts.
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="space-y-2">
                <Label htmlFor="org-name" className="text-on-surface-muted">
                  Legal Organization Name
                </Label>
                <Input
                  id="org-name"
                  value={name}
                  onChange={(e) => setName(e.target.value)}
                  required
                  className="bg-surface border-outline-strong text-on-surface"
                />
              </div>

              <div className="space-y-2">
                <Label htmlFor="org-slug" className="text-on-surface-muted">
                  Tenant Identifier (Slug)
                </Label>
                <Input
                  id="org-slug"
                  value={org?.slug || ""}
                  disabled
                  className="bg-surface/50 border-outline-variant text-on-surface-subtle cursor-not-allowed font-mono text-xs"
                />
                <p className="text-[11px] text-on-surface-subtle">Immutable multi-tenant partition key.</p>
              </div>

              <div className="space-y-2">
                <Label htmlFor="billing-email" className="text-on-surface-muted">
                  Billing Email
                </Label>
                <Input
                  id="billing-email"
                  type="email"
                  value={billingEmail}
                  onChange={(e) => setBillingEmail(e.target.value)}
                  className="bg-surface border-outline-strong text-on-surface"
                  placeholder="billing@company.com"
                />
              </div>

              <div className="space-y-2">
                <Label htmlFor="tax-id" className="text-on-surface-muted">
                  GSTIN / Tax Identifier
                </Label>
                <Input
                  id="tax-id"
                  value={taxIdentifier}
                  onChange={(e) => setTaxIdentifier(e.target.value)}
                  className="bg-surface border-outline-strong text-on-surface font-mono text-sm"
                  placeholder="27AABCU9603R1ZM"
                />
              </div>
            </CardContent>
            <CardFooter className="border-t border-outline-variant pt-4 flex justify-end">
              <Button
                type="submit"
                disabled={savingProfile}
                className="bg-primary hover:bg-burnt-orange text-white flex items-center gap-2"
              >
                <Save className="h-4 w-4" />
                {savingProfile ? "Saving..." : "Save Profile"}
              </Button>
            </CardFooter>
          </form>
        </Card>

        {/* Operational Settings Card */}
        <Card className="border-outline-variant bg-surface-card/60">
          <form onSubmit={handleSettingsSubmit}>
            <CardHeader>
              <CardTitle className="text-lg font-semibold text-white flex items-center gap-2">
                <SettingsIcon className="h-4 w-4 text-primary" />
                Operational Settings
              </CardTitle>
              <CardDescription className="text-on-surface-subtle">
                Configure pickup SLAs, automated dispatch, and compliance checks.
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="space-y-2">
                <Label htmlFor="sla-hours" className="text-on-surface-muted">
                  Default Pickup Commitment SLA (Hours)
                </Label>
                <Input
                  id="sla-hours"
                  type="number"
                  min="1"
                  max="72"
                  value={defaultSlaHours}
                  onChange={(e) => setDefaultSlaHours(Number(e.target.value))}
                  className="bg-surface border-outline-strong text-on-surface"
                />
                <p className="text-[11px] text-on-surface-subtle">
                  Allowed elapsed time between dispatch commitment and driver arrival at pickup.
                </p>
              </div>

              <div className="pt-2 space-y-4">
                <label className="flex items-center gap-3 cursor-pointer">
                  <input
                    type="checkbox"
                    checked={autoDispatch}
                    onChange={(e) => setAutoDispatch(e.target.checked)}
                    className="h-4 w-4 rounded border-outline-strong bg-surface text-primary focus:ring-burnt-orange"
                  />
                  <div>
                    <span className="text-sm font-medium text-on-surface">Autonomous Transporter Dispatch</span>
                    <p className="text-xs text-on-surface-subtle">
                      Auto-broadcast pending shipments to top-ranked matched carriers.
                    </p>
                  </div>
                </label>

                <label className="flex items-center gap-3 cursor-pointer">
                  <input
                    type="checkbox"
                    checked={requirePodVerification}
                    onChange={(e) => setRequirePodVerification(e.target.checked)}
                    className="h-4 w-4 rounded border-outline-strong bg-surface text-primary focus:ring-burnt-orange"
                  />
                  <div>
                    <span className="text-sm font-medium text-on-surface">Strict Proof of Delivery Audit</span>
                    <p className="text-xs text-on-surface-subtle">
                      Require operations manager verification before marking shipment reconciled.
                    </p>
                  </div>
                </label>
              </div>
            </CardContent>
            <CardFooter className="border-t border-outline-variant pt-4 flex justify-end">
              <Button
                type="submit"
                disabled={savingSettings}
                className="bg-primary hover:bg-burnt-orange text-white flex items-center gap-2"
              >
                <Save className="h-4 w-4" />
                {savingSettings ? "Saving..." : "Save Settings"}
              </Button>
            </CardFooter>
          </form>
        </Card>
      </div>
    </div>
  );
};
