import React, { createContext, useContext, useEffect, useState } from "react";
import { apiClient, setAccessToken } from "@/lib/api-client";

export interface User {
  id: string;
  email: string;
  first_name: string;
  last_name: string;
  phone?: string | null;
  is_active: boolean;
  is_superadmin: boolean;
  organization_id: string;
  organization_name: string;
  organization_slug: string;
  organization_type: "MANUFACTURER" | "CARRIER" | "THIRD_PARTY_LOGISTICS" | "BROKER";
  roles: string[];
  permissions: string[];
}

export interface RegisterPayload {
  full_name: string;
  email: string;
  password: string;
  confirm_password: string;
  organization_name: string;
  org_type: string;
  accept_terms: boolean;
}

export interface LoginPayload {
  email: string;
  password: string;
}

interface AuthContextType {
  user: User | null;
  isAuthenticated: boolean;
  loading: boolean;
  login: (payload: LoginPayload) => Promise<User>;
  register: (payload: RegisterPayload) => Promise<User>;
  logout: () => Promise<void>;
  refreshProfile: () => Promise<void>;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

export const AuthProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState<boolean>(true);

  // Bootstrap session check on app start
  useEffect(() => {
    let isMounted = true;

    async function initAuth() {
      // Skip silent refresh when no CSRF/session cookie exists to avoid 401 console errors on /login
      if (!document.cookie.includes("cargopulse_csrf_token=")) {
        if (isMounted) {
          setAccessToken(null);
          setUser(null);
          setLoading(false);
        }
        return;
      }

      try {
        // Attempt silent refresh using HttpOnly cookie session
        const res: any = await apiClient.post("/api/v1/auth/refresh");
        if (res?.access_token && isMounted) {
          setAccessToken(res.access_token);
          if (res.user) {
            setUser(res.user);
          } else {
            // Fetch fresh profile
            const profile: any = await apiClient.get("/api/v1/auth/me");
            setUser(profile);
          }
        }
      } catch (err) {
        // No active session cookie or expired
        if (isMounted) {
          setAccessToken(null);
          setUser(null);
        }
      } finally {
        if (isMounted) {
          setLoading(false);
        }
      }
    }

    initAuth();
    return () => {
      isMounted = false;
    };
  }, []);

  const login = async (payload: LoginPayload): Promise<User> => {
    const res: any = await apiClient.post("/api/v1/auth/login", payload);
    setAccessToken(res.access_token);
    setUser(res.user);
    return res.user;
  };

  const register = async (payload: RegisterPayload): Promise<User> => {
    const res: any = await apiClient.post("/api/v1/auth/register", payload);
    setAccessToken(res.access_token);
    setUser(res.user);
    return res.user;
  };

  const logout = async (): Promise<void> => {
    try {
      await apiClient.post("/api/v1/auth/logout");
    } catch (err) {
      // Ignore network errors during logout
    } finally {
      setAccessToken(null);
      setUser(null);
    }
  };

  const refreshProfile = async (): Promise<void> => {
    const profile: any = await apiClient.get("/api/v1/auth/me");
    setUser(profile);
  };

  return (
    <AuthContext.Provider
      value={{
        user,
        isAuthenticated: !!user,
        loading,
        login,
        register,
        logout,
        refreshProfile,
      }}
    >
      {children}
    </AuthContext.Provider>
  );
};

export function useAuth(): AuthContextType {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error("useAuth must be used within an AuthProvider");
  }
  return context;
}
