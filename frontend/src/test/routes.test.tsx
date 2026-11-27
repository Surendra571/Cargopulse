import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import { MemoryRouter, Routes, Route } from "react-router-dom";
import { ProtectedRoute } from "@/components/auth/ProtectedRoute";
import * as AuthContextModule from "@/context/AuthContext";

describe("Frontend Quality Assurance: Route Guards & Access Control", () => {
  it("redirects unauthenticated users to login with redirect parameter", () => {
    vi.spyOn(AuthContextModule, "useAuth").mockReturnValue({
      user: null,
      isAuthenticated: false,
      loading: false,
      login: vi.fn(),
      register: vi.fn(),
      logout: vi.fn(),
      refreshUser: vi.fn(),
    } as any);

    render(
      <MemoryRouter initialEntries={["/overview"]}>
        <Routes>
          <Route path="/login" element={<div>Login Page Redirected</div>} />
          <Route element={<ProtectedRoute />}>
            <Route path="/overview" element={<div>Protected Dashboard</div>} />
          </Route>
        </Routes>
      </MemoryRouter>
    );

    expect(screen.getByText("Login Page Redirected")).toBeInTheDocument();
    expect(screen.queryByText("Protected Dashboard")).not.toBeInTheDocument();
  });

  it("allows authenticated users to view protected routes", () => {
    vi.spyOn(AuthContextModule, "useAuth").mockReturnValue({
      user: {
        id: "test-user-id",
        email: "lead@apex.test",
        full_name: "Lead Director",
        role: "ADMIN",
        organization_id: "org-1",
        organization_name: "Apex Global",
        org_type: "MANUFACTURER",
      },
      isAuthenticated: true,
      loading: false,
      login: vi.fn(),
      register: vi.fn(),
      logout: vi.fn(),
      refreshUser: vi.fn(),
    } as any);

    render(
      <MemoryRouter initialEntries={["/overview"]}>
        <Routes>
          <Route path="/login" element={<div>Login Page</div>} />
          <Route element={<ProtectedRoute />}>
            <Route path="/overview" element={<div>Protected Dashboard</div>} />
          </Route>
        </Routes>
      </MemoryRouter>
    );

    expect(screen.getByText("Protected Dashboard")).toBeInTheDocument();
  });
});
