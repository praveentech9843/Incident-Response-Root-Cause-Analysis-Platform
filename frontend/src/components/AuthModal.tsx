import React, { useState } from "react";
import { useAuth } from "../context/useAuth";
import type { UserRole } from "../services/api";
import { ShieldAlert, X } from "lucide-react";

interface AuthModalProps {
  isOpen: boolean;
  onClose: () => void;
}

export const AuthModal: React.FC<AuthModalProps> = ({ isOpen, onClose }) => {
  const { login, register } = useAuth();
  const [isRegisterMode, setIsRegisterMode] = useState(false);
  const [username, setUsername] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [role, setRole] = useState<UserRole>("DEVELOPER");
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [successMsg, setSuccessMsg] = useState<string | null>(null);

  if (!isOpen) return null;

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    setSuccessMsg(null);
    setLoading(true);

    try {
      if (isRegisterMode) {
        await register({
          username: username.trim(),
          email: email.trim(),
          password,
          role,
        });
        setSuccessMsg("Registration successful! Logging you in...");
        // Automatically log in
        await login({ username: username.trim(), password });
        onClose();
      } else {
        await login({ username: username.trim(), password });
        onClose();
      }
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Authentication failed");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="modal-backdrop">
      <div className="modal-card" style={{ maxWidth: 440, width: "100%", margin: "auto", background: "#ffffff", borderRadius: 12, boxShadow: "0 20px 25px -5px rgba(0,0,0,0.1), 0 8px 10px -6px rgba(0,0,0,0.04)" }}>
        <div className="modal-header" style={{ display: "flex", justifyContent: "space-between", alignItems: "center", borderBottom: "1px solid #e2e8f0", padding: "16px 20px" }}>
          <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
            <div style={{ width: 32, height: 32, borderRadius: 8, background: "#eff6ff", color: "#1d4ed8", display: "flex", alignItems: "center", justifyContent: "center" }}>
              <ShieldAlert size={18} />
            </div>
            <h3 style={{ margin: 0, fontSize: "1.05rem", fontWeight: 700, color: "#0f172a" }}>
              {isRegisterMode ? "Create Platform Account" : "Platform Authentication"}
            </h3>
          </div>
          <button type="button" className="btn-close" onClick={onClose} style={{ background: "transparent", border: "none", cursor: "pointer", color: "#64748b", padding: 4 }}>
            <X size={18} />
          </button>
        </div>

        <form onSubmit={handleSubmit} style={{ display: "flex", flexDirection: "column", gap: 14, padding: "20px" }}>
          {error && <div className="alert alert-error" style={{ fontSize: "0.85rem" }}>{error}</div>}
          {successMsg && <div className="alert alert-success" style={{ fontSize: "0.85rem" }}>{successMsg}</div>}

          <div>
            <label style={{ display: "block", fontSize: "0.825rem", marginBottom: 4, fontWeight: 600, color: "#334155" }}>
              Username
            </label>
            <input
              type="text"
              required
              className="input-field"
              placeholder="e.g. dev_sarah or admin"
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              style={{ width: "100%", padding: "8px 12px", borderRadius: 8, border: "1px solid #cbd5e1", background: "#ffffff", color: "#0f172a", fontSize: "0.875rem" }}
            />
          </div>

          {isRegisterMode && (
            <div>
              <label style={{ display: "block", fontSize: "0.825rem", marginBottom: 4, fontWeight: 600, color: "#334155" }}>
                Email Address
              </label>
              <input
                type="email"
                required
                className="input-field"
                placeholder="developer@example.com"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                style={{ width: "100%", padding: "8px 12px", borderRadius: 8, border: "1px solid #cbd5e1", background: "#ffffff", color: "#0f172a", fontSize: "0.875rem" }}
              />
            </div>
          )}

          <div>
            <label style={{ display: "block", fontSize: "0.825rem", marginBottom: 4, fontWeight: 600, color: "#334155" }}>
              Password
            </label>
            <input
              type="password"
              required
              className="input-field"
              placeholder="Min 8 characters"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              style={{ width: "100%", padding: "8px 12px", borderRadius: 8, border: "1px solid #cbd5e1", background: "#ffffff", color: "#0f172a", fontSize: "0.875rem" }}
            />
          </div>

          {isRegisterMode && (
            <div>
              <label style={{ display: "block", fontSize: "0.825rem", marginBottom: 4, fontWeight: 600, color: "#334155" }}>
                Role (RBAC)
              </label>
              <select
                value={role}
                onChange={(e) => setRole(e.target.value as UserRole)}
                style={{ width: "100%", padding: "8px 12px", borderRadius: 8, border: "1px solid #cbd5e1", background: "#ffffff", color: "#0f172a", fontSize: "0.875rem" }}
              >
                <option value="DEVELOPER">DEVELOPER (Investigate & Resolve)</option>
                <option value="VIEWER">VIEWER (Read-Only)</option>
                <option value="ADMIN">ADMIN (Full Access & Integrations)</option>
              </select>
            </div>
          )}

          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginTop: 8 }}>
            <button
              type="button"
              className="btn btn-secondary btn-sm"
              onClick={() => {
                setIsRegisterMode(!isRegisterMode);
                setError(null);
              }}
            >
              {isRegisterMode ? "Switch to Sign In" : "Need an account? Register"}
            </button>

            <button
              type="submit"
              className="btn btn-primary btn-sm"
              disabled={loading}
            >
              {loading ? "Processing..." : isRegisterMode ? "Register & Login" : "Sign In"}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
};
