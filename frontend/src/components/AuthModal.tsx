import React, { useState } from "react";
import { useAuth } from "../context/useAuth";
import type { UserRole } from "../services/api";

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
      <div className="modal-card" style={{ maxWidth: 440, width: "100%", margin: "auto" }}>
        <div className="modal-header">
          <h3>{isRegisterMode ? "Create Platform Account" : "Platform Authentication"}</h3>
          <button type="button" className="btn-close" onClick={onClose}>
            ×
          </button>
        </div>

        <form onSubmit={handleSubmit} style={{ display: "flex", flexDirection: "column", gap: 14 }}>
          {error && <div className="alert alert-error" style={{ fontSize: "0.85rem" }}>{error}</div>}
          {successMsg && <div className="alert alert-success" style={{ fontSize: "0.85rem" }}>{successMsg}</div>}

          <div>
            <label style={{ display: "block", fontSize: "0.85rem", marginBottom: 4, fontWeight: 500 }}>
              Username
            </label>
            <input
              type="text"
              required
              className="input-field"
              placeholder="e.g. dev_sarah or admin"
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              style={{ width: "100%", padding: "8px 10px", borderRadius: 6, border: "1px solid #334155", background: "#0f172a", color: "#f8fafc" }}
            />
          </div>

          {isRegisterMode && (
            <div>
              <label style={{ display: "block", fontSize: "0.85rem", marginBottom: 4, fontWeight: 500 }}>
                Email Address
              </label>
              <input
                type="email"
                required
                className="input-field"
                placeholder="developer@example.com"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                style={{ width: "100%", padding: "8px 10px", borderRadius: 6, border: "1px solid #334155", background: "#0f172a", color: "#f8fafc" }}
              />
            </div>
          )}

          <div>
            <label style={{ display: "block", fontSize: "0.85rem", marginBottom: 4, fontWeight: 500 }}>
              Password
            </label>
            <input
              type="password"
              required
              className="input-field"
              placeholder="Min 8 characters"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              style={{ width: "100%", padding: "8px 10px", borderRadius: 6, border: "1px solid #334155", background: "#0f172a", color: "#f8fafc" }}
            />
          </div>

          {isRegisterMode && (
            <div>
              <label style={{ display: "block", fontSize: "0.85rem", marginBottom: 4, fontWeight: 500 }}>
                Role (RBAC)
              </label>
              <select
                value={role}
                onChange={(e) => setRole(e.target.value as UserRole)}
                style={{ width: "100%", padding: "8px 10px", borderRadius: 6, border: "1px solid #334155", background: "#0f172a", color: "#f8fafc" }}
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
