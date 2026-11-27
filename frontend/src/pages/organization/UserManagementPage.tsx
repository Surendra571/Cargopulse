import React, { useEffect, useState } from "react";
import { useAuth } from "@/context/AuthContext";
import { apiClient } from "@/lib/api-client";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Card, CardHeader, CardTitle, CardDescription, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Alert, AlertDescription } from "@/components/ui/alert";
import {
  Users,
  UserPlus,
  Shield,
  Search,
  CheckCircle2,
  AlertCircle,
  UserCheck,
  UserX,
  Trash2,
  X,
} from "lucide-react";

interface TenantUser {
  id: string;
  email: string;
  first_name: string;
  last_name: string;
  phone?: string | null;
  is_active: boolean;
  is_superadmin: boolean;
  roles: string[];
  role_ids: string[];
  created_at: string;
  last_login_at?: string | null;
}

interface RoleOption {
  id: string;
  name: string;
  role_type: string;
  description?: string;
}

export const UserManagementPage: React.FC = () => {
  const { user: currentUser } = useAuth();
  const [users, setUsers] = useState<TenantUser[]>([]);
  const [roles, setRoles] = useState<RoleOption[]>([]);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState("");
  const [statusFilter, setStatusFilter] = useState<string>("ALL");
  const [message, setMessage] = useState<{ type: "success" | "error"; text: string } | null>(null);

  // Modal states
  const [showInviteModal, setShowInviteModal] = useState(false);
  const [showRoleModal, setShowRoleModal] = useState(false);
  const [selectedUser, setSelectedUser] = useState<TenantUser | null>(null);

  // Invite form state
  const [inviteEmail, setInviteEmail] = useState("");
  const [inviteFirstName, setInviteFirstName] = useState("");
  const [inviteLastName, setInviteLastName] = useState("");
  const [invitePhone, setInvitePhone] = useState("");
  const [inviteRoleIds, setInviteRoleIds] = useState<string[]>([]);
  const [invitePassword, setInvitePassword] = useState("");
  const [submittingInvite, setSubmittingInvite] = useState(false);

  // Edit role form state
  const [editRoleIds, setEditRoleIds] = useState<string[]>([]);
  const [submittingRoles, setSubmittingRoles] = useState(false);

  useEffect(() => {
    loadData();
  }, []);

  const loadData = async () => {
    try {
      setLoading(true);
      const [usersRes, rolesRes]: [any, any] = await Promise.all([
        apiClient.get("/api/v1/organizations/me/users"),
        apiClient.get("/api/v1/organizations/me/roles"),
      ]);
      setUsers(usersRes);
      setRoles(rolesRes);
    } catch (err: any) {
      setMessage({ type: "error", text: err.response?.data?.detail || "Failed to load users or roles." });
    } finally {
      setLoading(false);
    }
  };

  const handleInviteSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (inviteRoleIds.length === 0) {
      setMessage({ type: "error", text: "Please assign at least one role to the user." });
      return;
    }

    setSubmittingInvite(true);
    setMessage(null);
    try {
      const res: any = await apiClient.post("/api/v1/organizations/me/users", {
        email: inviteEmail,
        first_name: inviteFirstName,
        last_name: inviteLastName,
        phone: invitePhone || null,
        role_ids: inviteRoleIds,
        initial_password: invitePassword || null,
      });
      setUsers([res, ...users]);
      setShowInviteModal(false);
      resetInviteForm();
      setMessage({ type: "success", text: `User ${inviteEmail} provisioned successfully.` });
    } catch (err: any) {
      setMessage({ type: "error", text: err.response?.data?.detail || "Failed to invite user." });
    } finally {
      setSubmittingInvite(false);
    }
  };

  const resetInviteForm = () => {
    setInviteEmail("");
    setInviteFirstName("");
    setInviteLastName("");
    setInvitePhone("");
    setInviteRoleIds([]);
    setInvitePassword("");
  };

  const openRoleModal = (targetUser: TenantUser) => {
    setSelectedUser(targetUser);
    setEditRoleIds(targetUser.role_ids || []);
    setShowRoleModal(true);
  };

  const handleRoleUpdate = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!selectedUser) return;
    if (editRoleIds.length === 0) {
      setMessage({ type: "error", text: "User must have at least one assigned role." });
      return;
    }

    setSubmittingRoles(true);
    setMessage(null);
    try {
      const res: any = await apiClient.put(
        `/api/v1/organizations/me/users/${selectedUser.id}/roles`,
        { role_ids: editRoleIds }
      );
      setUsers(users.map((u) => (u.id === selectedUser.id ? res : u)));
      setShowRoleModal(false);
      setMessage({ type: "success", text: `Updated roles for ${selectedUser.email}.` });
    } catch (err: any) {
      setMessage({ type: "error", text: err.response?.data?.detail || "Failed to update user roles." });
    } finally {
      setSubmittingRoles(false);
    }
  };

  const toggleUserStatus = async (targetUser: TenantUser) => {
    const newStatus = !targetUser.is_active;
    const confirmMsg = newStatus
      ? `Activate account for ${targetUser.email}?`
      : `Deactivate account for ${targetUser.email}? Active refresh sessions will be revoked immediately.`;

    if (!window.confirm(confirmMsg)) return;

    try {
      const res: any = await apiClient.patch(
        `/api/v1/organizations/me/users/${targetUser.id}/status`,
        { is_active: newStatus }
      );
      setUsers(users.map((u) => (u.id === targetUser.id ? res : u)));
      setMessage({
        type: "success",
        text: `Account for ${targetUser.email} has been ${newStatus ? "activated" : "deactivated"}.`,
      });
    } catch (err: any) {
      setMessage({ type: "error", text: err.response?.data?.detail || "Failed to update user status." });
    }
  };

  const handleRevokeUser = async (targetUser: TenantUser) => {
    if (
      !window.confirm(
        `Are you sure you want to permanently revoke access for ${targetUser.email}? All active sessions will be terminated.`
      )
    ) {
      return;
    }

    try {
      await apiClient.delete(`/api/v1/organizations/me/users/${targetUser.id}`);
      setUsers(users.filter((u) => u.id !== targetUser.id));
      setMessage({ type: "success", text: `Access for ${targetUser.email} permanently revoked.` });
    } catch (err: any) {
      setMessage({ type: "error", text: err.response?.data?.detail || "Failed to revoke user access." });
    }
  };

  const filteredUsers = users.filter((u) => {
    const matchesSearch =
      u.email.toLowerCase().includes(search.toLowerCase()) ||
      u.first_name.toLowerCase().includes(search.toLowerCase()) ||
      u.last_name.toLowerCase().includes(search.toLowerCase());
    const matchesStatus =
      statusFilter === "ALL" ||
      (statusFilter === "ACTIVE" && u.is_active) ||
      (statusFilter === "INACTIVE" && !u.is_active);
    return matchesSearch && matchesStatus;
  });

  return (
    <div className="max-w-6xl mx-auto px-4 py-8 space-y-6">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4 pb-4 border-b border-outline-variant">
        <div>
          <h1 className="text-2xl font-bold tracking-tight text-white flex items-center gap-2">
            <Users className="h-6 w-6 text-primary" />
            User & RBAC Management
          </h1>
          <p className="text-sm text-on-surface-subtle mt-1">
            Manage organization members, assign role permissions, and govern tenant access controls.
          </p>
        </div>
        <Button
          onClick={() => setShowInviteModal(true)}
          className="bg-primary hover:bg-burnt-orange text-white flex items-center gap-2"
        >
          <UserPlus className="h-4 w-4" />
          Invite User
        </Button>
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

      {/* Filters & Search */}
      <div className="flex flex-col sm:flex-row gap-3 items-center justify-between">
        <div className="relative w-full sm:w-80">
          <Search className="absolute left-3 top-2.5 h-4 w-4 text-on-surface-muted" />
          <Input
            placeholder="Search by name or email..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="pl-9 bg-surface-card border-outline-variant text-on-surface"
          />
        </div>
        <div className="flex items-center gap-2 self-start sm:self-auto">
          <Button
            size="sm"
            variant={statusFilter === "ALL" ? "default" : "outline"}
            onClick={() => setStatusFilter("ALL")}
            className={statusFilter === "ALL" ? "bg-primary" : "border-outline-variant text-on-surface-subtle"}
          >
            All ({users.length})
          </Button>
          <Button
            size="sm"
            variant={statusFilter === "ACTIVE" ? "default" : "outline"}
            onClick={() => setStatusFilter("ACTIVE")}
            className={statusFilter === "ACTIVE" ? "bg-emerald-600" : "border-outline-variant text-on-surface-subtle"}
          >
            Active ({users.filter((u) => u.is_active).length})
          </Button>
          <Button
            size="sm"
            variant={statusFilter === "INACTIVE" ? "default" : "outline"}
            onClick={() => setStatusFilter("INACTIVE")}
            className={statusFilter === "INACTIVE" ? "bg-surface-container-high" : "border-outline-variant text-on-surface-subtle"}
          >
            Inactive ({users.filter((u) => !u.is_active).length})
          </Button>
        </div>
      </div>

      {/* User Roster Table */}
      <Card className="border-outline-variant bg-surface-card/60 overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full text-left text-sm text-on-surface-muted">
            <thead className="bg-surface/80 text-xs uppercase tracking-wider text-on-surface-subtle border-b border-outline-variant">
              <tr>
                <th className="px-4 py-3">Member</th>
                <th className="px-4 py-3">Assigned Roles</th>
                <th className="px-4 py-3">Status</th>
                <th className="px-4 py-3">Joined Date</th>
                <th className="px-4 py-3 text-right">Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-800/60">
              {loading ? (
                <tr>
                  <td colSpan={5} className="text-center py-12">
                    <div className="h-6 w-6 animate-spin rounded-full border-2 border-burnt-orange border-t-transparent mx-auto" />
                  </td>
                </tr>
              ) : filteredUsers.length === 0 ? (
                <tr>
                  <td colSpan={5} className="text-center py-8 text-on-surface-muted">
                    No users found matching current filters.
                  </td>
                </tr>
              ) : (
                filteredUsers.map((u) => {
                  const isSelf = u.id === currentUser?.id;
                  return (
                    <tr key={u.id} className="hover:bg-surface-container/30 transition-colors">
                      <td className="px-4 py-3.5">
                        <div className="font-medium text-on-surface flex items-center gap-2">
                          <span>
                            {u.first_name} {u.last_name}
                          </span>
                          {isSelf && (
                            <Badge variant="outline" className="text-[10px] border-burnt-orange/40 text-primary">
                              You
                            </Badge>
                          )}
                          {u.is_superadmin && (
                            <Badge variant="outline" className="text-[10px] border-amber-500/40 text-amber-400">
                              Superadmin
                            </Badge>
                          )}
                        </div>
                        <div className="text-xs text-on-surface-subtle font-mono mt-0.5">{u.email}</div>
                      </td>
                      <td className="px-4 py-3.5">
                        <div className="flex flex-wrap gap-1.5">
                          {u.roles.map((r) => (
                            <Badge
                              key={r}
                              variant="secondary"
                              className="text-xs bg-surface-container text-on-surface border border-outline-strong"
                            >
                              {r}
                            </Badge>
                          ))}
                        </div>
                      </td>
                      <td className="px-4 py-3.5">
                        {u.is_active ? (
                          <Badge variant="outline" className="border-emerald-500/40 text-emerald-400 text-xs">
                            Active
                          </Badge>
                        ) : (
                          <Badge variant="outline" className="border-rose-500/40 text-rose-400 text-xs">
                            Inactive
                          </Badge>
                        )}
                      </td>
                      <td className="px-4 py-3.5 text-xs text-on-surface-subtle">
                        {new Date(u.created_at).toLocaleDateString()}
                      </td>
                      <td className="px-4 py-3.5 text-right space-x-2">
                        <Button
                          size="sm"
                          variant="ghost"
                          onClick={() => openRoleModal(u)}
                          className="h-8 px-2 text-on-surface-muted hover:text-white"
                          title="Manage Roles"
                        >
                          <Shield className="h-3.5 w-3.5 mr-1" />
                          Roles
                        </Button>

                        {!isSelf && (
                          <>
                            <Button
                              size="sm"
                              variant="ghost"
                              onClick={() => toggleUserStatus(u)}
                              className={`h-8 px-2 ${
                                u.is_active
                                  ? "text-amber-400 hover:text-amber-300"
                                  : "text-emerald-400 hover:text-emerald-300"
                              }`}
                              title={u.is_active ? "Deactivate Account" : "Activate Account"}
                            >
                              {u.is_active ? <UserX className="h-3.5 w-3.5" /> : <UserCheck className="h-3.5 w-3.5" />}
                            </Button>

                            <Button
                              size="sm"
                              variant="ghost"
                              onClick={() => handleRevokeUser(u)}
                              className="h-8 px-2 text-rose-400 hover:text-rose-300"
                              title="Revoke Access Permanently"
                            >
                              <Trash2 className="h-3.5 w-3.5" />
                            </Button>
                          </>
                        )}
                      </td>
                    </tr>
                  );
                })
              )}
            </tbody>
          </table>
        </div>
      </Card>

      {/* Invite User Modal */}
      {showInviteModal && (
        <div className="fixed inset-0 z-50 bg-black/70 backdrop-blur-sm flex items-center justify-center p-4">
          <Card className="w-full max-w-lg border-outline-variant bg-surface-card shadow-2xl">
            <CardHeader className="flex flex-row items-center justify-between pb-3">
              <div>
                <CardTitle className="text-lg font-bold text-white flex items-center gap-2">
                  <UserPlus className="h-5 w-5 text-primary" />
                  Invite Member to Organization
                </CardTitle>
                <CardDescription className="text-on-surface-subtle text-xs">
                  Provision tenant credentials and assign initial operational permissions.
                </CardDescription>
              </div>
              <Button
                variant="ghost"
                size="sm"
                onClick={() => setShowInviteModal(false)}
                className="h-8 w-8 p-0 text-on-surface-subtle"
              >
                <X className="h-4 w-4" />
              </Button>
            </CardHeader>
            <form onSubmit={handleInviteSubmit}>
              <CardContent className="space-y-4">
                <div className="grid grid-cols-2 gap-3">
                  <div className="space-y-1.5">
                    <Label className="text-xs text-on-surface-muted">First Name</Label>
                    <Input
                      value={inviteFirstName}
                      onChange={(e) => setInviteFirstName(e.target.value)}
                      required
                      className="bg-surface border-outline-strong text-on-surface"
                    />
                  </div>
                  <div className="space-y-1.5">
                    <Label className="text-xs text-on-surface-muted">Last Name</Label>
                    <Input
                      value={inviteLastName}
                      onChange={(e) => setInviteLastName(e.target.value)}
                      required
                      className="bg-surface border-outline-strong text-on-surface"
                    />
                  </div>
                </div>

                <div className="space-y-1.5">
                  <Label className="text-xs text-on-surface-muted">Work Email Address</Label>
                  <Input
                    type="email"
                    value={inviteEmail}
                    onChange={(e) => setInviteEmail(e.target.value)}
                    required
                    className="bg-surface border-outline-strong text-on-surface"
                  />
                </div>

                <div className="space-y-1.5">
                  <Label className="text-xs text-on-surface-muted">Phone (Optional)</Label>
                  <Input
                    type="tel"
                    value={invitePhone}
                    onChange={(e) => setInvitePhone(e.target.value)}
                    className="bg-surface border-outline-strong text-on-surface"
                  />
                </div>

                <div className="space-y-2">
                  <Label className="text-xs text-on-surface-muted">Assign Roles (select at least one)</Label>
                  <div className="space-y-2 max-h-40 overflow-y-auto p-2 rounded border border-outline-variant bg-surface">
                    {roles.map((r) => {
                      const checked = inviteRoleIds.includes(r.id);
                      return (
                        <label key={r.id} className="flex items-start gap-2.5 text-xs text-on-surface-muted cursor-pointer">
                          <input
                            type="checkbox"
                            checked={checked}
                            onChange={(e) => {
                              if (e.target.checked) {
                                setInviteRoleIds([...inviteRoleIds, r.id]);
                              } else {
                                setInviteRoleIds(inviteRoleIds.filter((id) => id !== r.id));
                              }
                            }}
                            className="mt-0.5 rounded border-outline-strong bg-surface-card text-primary focus:ring-burnt-orange"
                          />
                          <div>
                            <span className="font-semibold text-on-surface">{r.name}</span>
                            {r.description && <p className="text-[11px] text-on-surface-subtle">{r.description}</p>}
                          </div>
                        </label>
                      );
                    })}
                  </div>
                </div>

                <div className="space-y-1.5">
                  <Label className="text-xs text-on-surface-muted">Initial Password (Optional)</Label>
                  <Input
                    type="password"
                    placeholder="Auto-generated if left blank"
                    value={invitePassword}
                    onChange={(e) => setInvitePassword(e.target.value)}
                    className="bg-surface border-outline-strong text-on-surface"
                  />
                  <p className="text-[11px] text-on-surface-subtle">
                    If omitted, a secure temporary access key will be generated.
                  </p>
                </div>
              </CardContent>

              <div className="p-4 border-t border-outline-variant flex justify-end gap-2">
                <Button
                  type="button"
                  variant="outline"
                  onClick={() => setShowInviteModal(false)}
                  className="border-outline-variant text-on-surface-subtle"
                >
                  Cancel
                </Button>
                <Button
                  type="submit"
                  disabled={submittingInvite}
                  className="bg-primary hover:bg-burnt-orange text-white"
                >
                  {submittingInvite ? "Inviting..." : "Confirm Invitation"}
                </Button>
              </div>
            </form>
          </Card>
        </div>
      )}

      {/* Edit User Roles Modal */}
      {showRoleModal && selectedUser && (
        <div className="fixed inset-0 z-50 bg-black/70 backdrop-blur-sm flex items-center justify-center p-4">
          <Card className="w-full max-w-md border-outline-variant bg-surface-card shadow-2xl">
            <CardHeader className="flex flex-row items-center justify-between pb-3">
              <div>
                <CardTitle className="text-lg font-bold text-white flex items-center gap-2">
                  <Shield className="h-5 w-5 text-primary" />
                  Update Roles
                </CardTitle>
                <CardDescription className="text-on-surface-subtle text-xs">
                  Modifying permissions for {selectedUser.first_name} ({selectedUser.email})
                </CardDescription>
              </div>
              <Button
                variant="ghost"
                size="sm"
                onClick={() => setShowRoleModal(false)}
                className="h-8 w-8 p-0 text-on-surface-subtle"
              >
                <X className="h-4 w-4" />
              </Button>
            </CardHeader>
            <form onSubmit={handleRoleUpdate}>
              <CardContent className="space-y-4">
                <div className="space-y-2 max-h-60 overflow-y-auto p-2 rounded border border-outline-variant bg-surface">
                  {roles.map((r) => {
                    const checked = editRoleIds.includes(r.id);
                    return (
                      <label key={r.id} className="flex items-start gap-2.5 text-xs text-on-surface-muted cursor-pointer py-1">
                        <input
                          type="checkbox"
                          checked={checked}
                          onChange={(e) => {
                            if (e.target.checked) {
                              setEditRoleIds([...editRoleIds, r.id]);
                            } else {
                              setEditRoleIds(editRoleIds.filter((id) => id !== r.id));
                            }
                          }}
                          className="mt-0.5 rounded border-outline-strong bg-surface-card text-primary focus:ring-burnt-orange"
                        />
                        <div>
                          <span className="font-semibold text-on-surface">{r.name}</span>
                          {r.description && <p className="text-[11px] text-on-surface-subtle">{r.description}</p>}
                        </div>
                      </label>
                    );
                  })}
                </div>
              </CardContent>

              <div className="p-4 border-t border-outline-variant flex justify-end gap-2">
                <Button
                  type="button"
                  variant="outline"
                  onClick={() => setShowRoleModal(false)}
                  className="border-outline-variant text-on-surface-subtle"
                >
                  Cancel
                </Button>
                <Button
                  type="submit"
                  disabled={submittingRoles}
                  className="bg-primary hover:bg-burnt-orange text-white"
                >
                  {submittingRoles ? "Saving..." : "Save Role Assignments"}
                </Button>
              </div>
            </form>
          </Card>
        </div>
      )}
    </div>
  );
};
