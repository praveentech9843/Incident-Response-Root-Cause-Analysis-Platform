import React from "react";
import { Navigate, useLocation, Outlet } from "react-router-dom";
import { useAuth } from "../context/useAuth";
import { Loader2 } from "lucide-react";

interface ProtectedRouteProps {
  children?: React.ReactNode;
}

export const ProtectedRoute: React.FC<ProtectedRouteProps> = ({ children }) => {
  const { isAuthenticated, loading } = useAuth();
  const location = useLocation();

  if (loading) {
    return (
      <div
        style={{
          minHeight: "100vh",
          display: "flex",
          flexDirection: "column",
          alignItems: "center",
          justifyContent: "center",
          backgroundColor: "var(--bg-canvas, #f3f6fc)",
          gap: "1rem",
          color: "#0f172a",
        }}
      >
        <Loader2 size={36} className="spin" color="#2563eb" />
        <div style={{ textAlign: "center" }}>
          <p style={{ fontWeight: 600, margin: 0, fontSize: "1rem" }}>
            Verifying Authentication Session...
          </p>
          <span style={{ fontSize: "0.825rem", color: "#64748b" }}>
            Validating secure JWT credentials with incident platform
          </span>
        </div>
      </div>
    );
  }

  if (!isAuthenticated) {
    return <Navigate to="/login" state={{ from: location }} replace />;
  }

  return children ? <>{children}</> : <Outlet />;
};
