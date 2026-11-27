import React from "react";
import { Navigate, Outlet } from "react-router-dom";
import { useAuth } from "@/context/AuthContext";
import { Loader2 } from "lucide-react";

export const PublicOnlyRoute: React.FC = () => {
  const { isAuthenticated, loading } = useAuth();

  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-surface text-on-surface">
        <Loader2 className="h-8 w-8 animate-spin text-primary" />
      </div>
    );
  }

  if (isAuthenticated) {
    return <Navigate to="/overview" replace />;
  }

  return (
    <div className="min-h-screen bg-surface text-on-surface flex flex-col font-sans selection:bg-blue-600 selection:text-white">
      {/* Brand Header for Public/Auth Screens */}
      <header className="h-16 border-b border-outline-variant/80 px-6 flex items-center justify-between bg-surface-card/60 backdrop-blur-md">
        <div className="flex items-center gap-3">
          <div className="w-8 h-8 rounded-lg bg-gradient-to-tr from-blue-700 via-blue-600 to-teal-400 flex items-center justify-center shadow-md shadow-blue-500/20">
            <span className="font-black text-white text-base tracking-wider">CP</span>
          </div>
          <div>
            <span className="text-base font-bold text-white tracking-tight">CargoPulse</span>
            <span className="hidden sm:inline-block text-xs text-slate-400 ml-2 font-medium">
              Accountable B2B Logistics Platform
            </span>
          </div>
        </div>
      </header>

      {/* Auth Content Area */}
      <main className="flex-1 flex items-center justify-center p-4">
        <Outlet />
      </main>

      {/* Minimal Footer */}
      <footer className="py-4 text-center text-xs text-on-surface0 border-t border-slate-900">
        <p>&copy; {new Date().getFullYear()} CargoPulse Inc. Enterprise-grade accountable logistics. All rights reserved.</p>
      </footer>
    </div>
  );
};
