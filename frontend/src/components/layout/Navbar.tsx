import React from "react";
import { Link, useNavigate } from "react-router-dom";
import { useAuth } from "@/context/AuthContext";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import {
  LogOut,
  User as UserIcon,
  KeyRound,
  Activity,
  Building2,
  Users,
} from "lucide-react";

export const Navbar: React.FC = () => {
  const { user, isAuthenticated, logout } = useAuth();
  const navigate = useNavigate();

  const handleLogout = async () => {
    await logout();
    navigate("/login");
  };

  const hasOrgAccess =
    user?.is_superadmin ||
    user?.permissions?.some(
      (p) => p.startsWith("organization:") || p === "admin:all" || p === "*:*"
    );

  const hasUsersAccess =
    user?.is_superadmin ||
    user?.permissions?.some(
      (p) => p.startsWith("users:") || p === "admin:all" || p === "*:*"
    );

  return (
    <header className="sticky top-0 z-40 border-b border-outline-variant bg-surface/80 backdrop-blur-md">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 h-16 flex items-center justify-between">
        <div className="flex items-center gap-6">
          <Link to="/" className="flex items-center gap-2">
            <div className="h-8 w-8 rounded-lg bg-blue-600 flex items-center justify-center font-bold text-white shadow-lg shadow-blue-500/20">
              CP
            </div>
            <span className="text-lg font-bold tracking-tight text-white">CargoPulse</span>
          </Link>
          <span className="hidden md:inline-flex text-xs font-semibold px-2 py-0.5 rounded border border-burnt-orange/30 bg-blue-950/50 text-primary">
            Accountable B2B Logistics
          </span>

          {isAuthenticated && (
            <div className="hidden lg:flex items-center gap-1 ml-4 border-l border-outline-variant pl-4">
              {hasOrgAccess && (
                <Link to="/organization">
                  <Button variant="ghost" size="sm" className="h-8 text-xs text-on-surface-muted hover:text-white">
                    <Building2 className="h-3.5 w-3.5 mr-1.5 text-primary" />
                    Organization
                  </Button>
                </Link>
              )}
              {hasUsersAccess && (
                <Link to="/organization/users">
                  <Button variant="ghost" size="sm" className="h-8 text-xs text-on-surface-muted hover:text-white">
                    <Users className="h-3.5 w-3.5 mr-1.5 text-primary" />
                    Users & RBAC
                  </Button>
                </Link>
              )}
            </div>
          )}
        </div>

        <nav className="flex items-center gap-3">
          <Link
            to="/health"
            className="flex items-center gap-1.5 text-xs text-slate-400 hover:text-on-surface transition-colors mr-2"
          >
            <Activity className="h-3.5 w-3.5" />
            <span className="hidden sm:inline">System Health</span>
          </Link>

          {isAuthenticated && user ? (
            <div className="flex items-center gap-2 sm:gap-3">
              <div className="hidden sm:flex flex-col items-end">
                <span className="text-xs font-medium text-on-surface">
                  {user.first_name} {user.last_name}
                </span>
                <span className="text-[11px] text-slate-400">
                  {user.organization_name}
                </span>
              </div>
              <Badge variant="outline" className="border-burnt-orange/40 text-primary text-[11px]">
                {user.organization_type}
              </Badge>
              <Link to="/profile">
                <Button variant="ghost" size="sm" className="h-8 px-2 text-on-surface-muted">
                  <UserIcon className="h-4 w-4 sm:mr-1.5" />
                  <span className="hidden sm:inline">Profile</span>
                </Button>
              </Link>
              <Link to="/change-password">
                <Button variant="ghost" size="sm" className="h-8 px-2 text-on-surface-muted">
                  <KeyRound className="h-4 w-4 sm:mr-1.5" />
                  <span className="hidden sm:inline">Password</span>
                </Button>
              </Link>
              <Button
                variant="outline"
                size="sm"
                onClick={handleLogout}
                className="h-8 px-2.5 text-rose-400 border-rose-900/50 hover:bg-rose-950/30"
              >
                <LogOut className="h-3.5 w-3.5 sm:mr-1.5" />
                <span className="hidden sm:inline">Logout</span>
              </Button>
            </div>
          ) : (
            <div className="flex items-center gap-2">
              <Link to="/login">
                <Button variant="ghost" size="sm">
                  Sign in
                </Button>
              </Link>
              <Link to="/register">
                <Button size="sm" className="bg-blue-600 hover:bg-blue-700">
                  Register Organization
                </Button>
              </Link>
            </div>
          )}
        </nav>
      </div>
    </header>
  );
};
