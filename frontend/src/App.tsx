import React from "react";
import { BrowserRouter, Routes, Route, Navigate } from "react-router-dom";
import { AuthProvider } from "./context/AuthContext";
import { ProtectedRoute } from "./components/ProtectedRoute";
import { AppLayout } from "./components/AppLayout";
import { LoginPage } from "./pages/LoginPage";
import { RegisterPage } from "./pages/RegisterPage";
import { IncidentsPage } from "./pages/IncidentsPage";
import { LiveLogsPage } from "./pages/LiveLogsPage";
import { IntegrationsPage } from "./pages/IntegrationsPage";
import { AlertsPage } from "./pages/AlertsPage";
import { AuditLogPage } from "./pages/AuditLogPage";
import { ObservabilityPage } from "./pages/ObservabilityPage";

export const App: React.FC = () => {
  return (
    <AuthProvider>
      <BrowserRouter>
        <Routes>
          {/* Public Authentication Routes */}
          <Route path="/login" element={<LoginPage />} />
          <Route path="/register" element={<RegisterPage />} />

          {/* Root route: if authenticated, redirect to /incidents; if not, ProtectedRoute will redirect to /login */}
          <Route
            path="/"
            element={
              <ProtectedRoute>
                <Navigate to="/incidents" replace />
              </ProtectedRoute>
            }
          />

          {/* Protected Application Routes with Global AppLayout */}
          <Route
            element={
              <ProtectedRoute>
                <AppLayout />
              </ProtectedRoute>
            }
          >
            <Route path="/incidents" element={<IncidentsPage />} />
            <Route path="/incidents/:id" element={<IncidentsPage />} />
            <Route path="/logs" element={<LiveLogsPage />} />
            <Route path="/integrations" element={<IntegrationsPage />} />
            <Route path="/alerts" element={<AlertsPage />} />
            <Route path="/audit" element={<AuditLogPage />} />
            <Route path="/observability" element={<ObservabilityPage />} />
            <Route path="/health" element={<Navigate to="/observability" replace />} />
          </Route>

          {/* Fallback route */}
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </BrowserRouter>
    </AuthProvider>
  );
};

export default App;
