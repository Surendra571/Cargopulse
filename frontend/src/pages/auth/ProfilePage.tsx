import React from "react";
import { Link } from "react-router-dom";
import { useAuth } from "@/context/AuthContext";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import {
  Building2,
  KeyRound,
  Shield,
  ShieldCheck,
  User,
  CheckCircle,
} from "lucide-react";

export const ProfilePage: React.FC = () => {
  const { user } = useAuth();

  if (!user) {
    return null;
  }

  return (
    <div className="max-w-5xl mx-auto py-8 px-4 sm:px-6 lg:px-8 space-y-6">
      {/* Header Profile Summary */}
      <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4 p-6 rounded-xl border border-outline-variant bg-surface-card/60 backdrop-blur-sm">
        <div className="flex items-center gap-4">
          <div className="h-16 w-16 rounded-2xl bg-gradient-to-tr from-blue-600 to-indigo-600 flex items-center justify-center text-white text-2xl font-bold shadow-lg shadow-blue-500/20">
            {user.first_name[0]}
            {user.last_name ? user.last_name[0] : ""}
          </div>
          <div>
            <div className="flex items-center gap-2">
              <h1 className="text-2xl font-bold text-white">
                {user.first_name} {user.last_name}
              </h1>
              {user.is_active && (
                <span className="inline-flex items-center gap-1 text-[11px] font-medium text-emerald-400 bg-emerald-950/50 border border-emerald-500/30 px-2 py-0.5 rounded-full">
                  <CheckCircle className="h-3 w-3" />
                  Active
                </span>
              )}
            </div>
            <p className="text-sm text-on-surface-subtle flex items-center gap-2 mt-0.5">
              <span>{user.email}</span>
              <span>•</span>
              <span className="text-on-surface-muted font-medium">{user.organization_name}</span>
            </p>
          </div>
        </div>

        <div className="flex items-center gap-3 w-full sm:w-auto">
          <Link to="/change-password" className="w-full sm:w-auto">
            <Button variant="outline" size="sm" className="w-full sm:w-auto">
              <KeyRound className="h-4 w-4 mr-2" />
              Change Password
            </Button>
          </Link>
        </div>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        {/* User Account Information */}
        <Card className="border-outline-variant bg-surface-card/80">
          <CardHeader>
            <CardTitle className="text-base font-semibold text-white flex items-center gap-2">
              <User className="h-4 w-4 text-primary" />
              User Information
            </CardTitle>
            <CardDescription className="text-xs text-on-surface-subtle">
              Personal account metadata and identity credentials.
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-4 text-sm">
            <div className="flex justify-between py-2 border-b border-outline-variant/60">
              <span className="text-on-surface-subtle">User ID</span>
              <span className="font-mono text-xs text-on-surface-muted">{user.id}</span>
            </div>
            <div className="flex justify-between py-2 border-b border-outline-variant/60">
              <span className="text-on-surface-subtle">Work Email</span>
              <span className="text-on-surface">{user.email}</span>
            </div>
            <div className="flex justify-between py-2 border-b border-outline-variant/60">
              <span className="text-on-surface-subtle">Phone Number</span>
              <span className="text-on-surface-muted">{user.phone || "Not provided"}</span>
            </div>
            <div className="flex justify-between py-2 border-b border-outline-variant/60">
              <span className="text-on-surface-subtle">Superadmin Status</span>
              <span className="text-on-surface-muted">{user.is_superadmin ? "Yes" : "Standard"}</span>
            </div>
          </CardContent>
        </Card>

        {/* Tenant Organization Information */}
        <Card className="border-outline-variant bg-surface-card/80">
          <CardHeader>
            <CardTitle className="text-base font-semibold text-white flex items-center gap-2">
              <Building2 className="h-4 w-4 text-primary" />
              Organization & Tenant Scope
            </CardTitle>
            <CardDescription className="text-xs text-on-surface-subtle">
              Multi-tenant organization affiliation and tier configuration.
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-4 text-sm">
            <div className="flex justify-between py-2 border-b border-outline-variant/60">
              <span className="text-on-surface-subtle">Organization Name</span>
              <span className="font-medium text-on-surface">{user.organization_name}</span>
            </div>
            <div className="flex justify-between py-2 border-b border-outline-variant/60">
              <span className="text-on-surface-subtle">Organization Slug</span>
              <span className="font-mono text-xs text-on-surface-muted">{user.organization_slug}</span>
            </div>
            <div className="flex justify-between py-2 border-b border-outline-variant/60">
              <span className="text-on-surface-subtle">Business Model Type</span>
              <Badge variant="outline" className="border-burnt-orange/40 text-primary">
                {user.organization_type}
              </Badge>
            </div>
            <div className="flex justify-between py-2 border-b border-outline-variant/60">
              <span className="text-on-surface-subtle">Tenant ID</span>
              <span className="font-mono text-xs text-on-surface-muted">{user.organization_id}</span>
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Roles & Permissions */}
      <Card className="border-outline-variant bg-surface-card/80">
        <CardHeader>
          <CardTitle className="text-base font-semibold text-white flex items-center gap-2">
            <ShieldCheck className="h-4 w-4 text-primary" />
            Roles & Operational Capabilities
          </CardTitle>
          <CardDescription className="text-xs text-on-surface-subtle">
            Granular access control policies bound to this user session.
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-6 text-sm">
          <div>
            <h4 className="text-xs font-semibold uppercase tracking-wider text-on-surface-subtle mb-3">
              Assigned Roles
            </h4>
            <div className="flex flex-wrap gap-2">
              {user.roles.length > 0 ? (
                user.roles.map((role) => (
                  <Badge key={role} className="bg-primary/20 text-primary border-burnt-orange/40">
                    {role}
                  </Badge>
                ))
              ) : (
                <span className="text-xs text-on-surface-muted">No roles assigned</span>
              )}
            </div>
          </div>

          <div>
            <h4 className="text-xs font-semibold uppercase tracking-wider text-on-surface-subtle mb-3">
              Effective Permissions
            </h4>
            <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 gap-2">
              {user.permissions.length > 0 ? (
                user.permissions.map((perm) => (
                  <div
                    key={perm}
                    className="flex items-center gap-1.5 px-2.5 py-1.5 rounded border border-outline-variant bg-surface text-xs font-mono text-on-surface-muted"
                  >
                    <Shield className="h-3 w-3 text-primary shrink-0" />
                    <span className="truncate">{perm}</span>
                  </div>
                ))
              ) : (
                <span className="text-xs text-on-surface-muted">No specific permissions granted</span>
              )}
            </div>
          </div>
        </CardContent>
      </Card>
    </div>
  );
};
