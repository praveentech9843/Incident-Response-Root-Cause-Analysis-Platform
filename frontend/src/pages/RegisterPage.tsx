import React, { useState, useEffect } from "react";
import { useNavigate, Link } from "react-router-dom";
import { useAuth } from "../context/useAuth";
import type { UserRole } from "../services/api";
import {
  ShieldAlert,
  GitMerge,
  Cpu,
  CheckCircle2,
  Lock,
  User as UserIcon,
  Mail,
  Briefcase,
  Eye,
  EyeOff,
  Loader2,
  ArrowRight,
  AlertCircle,
} from "lucide-react";

export const RegisterPage: React.FC = () => {
  const { register, login, isAuthenticated } = useAuth();
  const navigate = useNavigate();

  const [username, setUsername] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [role, setRole] = useState<UserRole>("DEVELOPER");
  const [showPassword, setShowPassword] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (isAuthenticated) {
      navigate("/incidents", { replace: true });
    }
  }, [isAuthenticated, navigate]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!username.trim() || !email.trim() || !password) {
      setError("Please fill in all required fields.");
      return;
    }

    if (password.length < 8) {
      setError("Password must be at least 8 characters long.");
      return;
    }

    setError(null);
    setLoading(true);

    try {
      await register({
        username: username.trim(),
        email: email.trim(),
        password,
        role,
      });

      // Automatically sign in upon registration
      await login({
        username: username.trim(),
        password,
      });

      navigate("/incidents", { replace: true });
    } catch (err: unknown) {
      let message = "Registration failed. Please check your information.";
      if (err instanceof Error) {
        message = err.message.replace(/^HTTP \d+:?\s*/i, "");
      }
      setError(message);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="auth-page-wrapper">
      <div className="auth-ambient-glow" />

      <main className="auth-card-container">
        {/* Left Section: Branding & Highlights */}
        <section className="auth-brand-pane">
          <div>
            <div className="auth-brand-logo-row">
              <div className="auth-logo-icon">
                <ShieldAlert size={22} />
              </div>
              <span className="auth-brand-name">AI Incident Response & RCA</span>
            </div>

            <h1 className="auth-brand-headline">
              Join Your Engineering Incident Command Center.
            </h1>

            <p className="auth-brand-desc">
              Create an account to investigate live telemetry, review machine-learning root-cause
              diagnoses, and collaborate on real-time incident resolution.
            </p>

            <div className="auth-features-list">
              <div className="auth-feature-item">
                <div className="auth-feature-icon-box">
                  <GitMerge size={18} />
                </div>
                <div>
                  <h2 className="auth-feature-title">End-to-End Log Correlation</h2>
                  <p className="auth-feature-text">
                    Multi-service event tracing with automatic noise deduplication.
                  </p>
                </div>
              </div>

              <div className="auth-feature-item">
                <div className="auth-feature-icon-box">
                  <Cpu size={18} />
                </div>
                <div>
                  <h2 className="auth-feature-title">Automated RCA Engine</h2>
                  <p className="auth-feature-text">
                    Probabilistic cause scoring powered by deep runtime context.
                  </p>
                </div>
              </div>

              <div className="auth-feature-item">
                <div className="auth-feature-icon-box">
                  <CheckCircle2 size={18} />
                </div>
                <div>
                  <h2 className="auth-feature-title">Role-Based Access Control</h2>
                  <p className="auth-feature-text">
                    Fine-grained permissions for Developers, Viewers, and Administrators.
                  </p>
                </div>
              </div>
            </div>
          </div>

          <div
            style={{
              padding: "1rem",
              background: "#ffffff",
              borderRadius: "10px",
              border: "1px solid #dbeafe",
              fontSize: "0.8rem",
              color: "#475569",
            }}
          >
            🔒 <strong>Enterprise Security:</strong> User credentials are protected using memory-hard Argon2id hashing algorithms.
          </div>
        </section>

        {/* Right Section: Registration Card */}
        <section className="auth-form-pane">
          <div className="auth-form-header">
            <h2 className="auth-form-heading">Create Account</h2>
            <p className="auth-form-subtitle">Register to join your organization's workspace.</p>
          </div>

          {error && (
            <div
              className="alert alert-error"
              style={{
                marginBottom: "1.25rem",
                display: "flex",
                alignItems: "flex-start",
                gap: "0.5rem",
                fontSize: "0.85rem",
              }}
              role="alert"
            >
              <AlertCircle size={16} style={{ flexShrink: 0, marginTop: "2px" }} />
              <div>{error}</div>
            </div>
          )}

          <form onSubmit={handleSubmit} noValidate>
            {/* Username */}
            <div className="auth-form-group">
              <label htmlFor="reg-username" className="auth-label">
                Username
              </label>
              <div className="auth-input-wrapper">
                <UserIcon size={16} className="auth-input-icon" />
                <input
                  id="reg-username"
                  name="username"
                  type="text"
                  required
                  autoFocus
                  autoComplete="username"
                  className="auth-input"
                  placeholder="e.g. alex_chen"
                  value={username}
                  onChange={(e) => setUsername(e.target.value)}
                  disabled={loading}
                />
              </div>
            </div>

            {/* Email */}
            <div className="auth-form-group">
              <label htmlFor="reg-email" className="auth-label">
                Email Address
              </label>
              <div className="auth-input-wrapper">
                <Mail size={16} className="auth-input-icon" />
                <input
                  id="reg-email"
                  name="email"
                  type="email"
                  required
                  autoComplete="email"
                  className="auth-input"
                  placeholder="alex.chen@company.com"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  disabled={loading}
                />
              </div>
            </div>

            {/* Password */}
            <div className="auth-form-group">
              <label htmlFor="reg-password" className="auth-label">
                Password <span style={{ fontWeight: 400, color: "#94a3b8" }}>(min 8 characters)</span>
              </label>
              <div className="auth-input-wrapper">
                <Lock size={16} className="auth-input-icon" />
                <input
                  id="reg-password"
                  name="password"
                  type={showPassword ? "text" : "password"}
                  required
                  autoComplete="new-password"
                  className="auth-input"
                  placeholder="Choose a strong password"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  disabled={loading}
                />
                <button
                  type="button"
                  className="auth-toggle-password-btn"
                  onClick={() => setShowPassword(!showPassword)}
                  aria-label={showPassword ? "Hide password" : "Show password"}
                  tabIndex={0}
                >
                  {showPassword ? <EyeOff size={16} /> : <Eye size={16} />}
                </button>
              </div>
            </div>

            {/* Role Selection */}
            <div className="auth-form-group">
              <label htmlFor="reg-role" className="auth-label">
                Platform Role (RBAC)
              </label>
              <div className="auth-input-wrapper">
                <Briefcase size={16} className="auth-input-icon" />
                <select
                  id="reg-role"
                  name="role"
                  className="auth-input"
                  value={role}
                  onChange={(e) => setRole(e.target.value as UserRole)}
                  disabled={loading}
                  style={{ cursor: "pointer" }}
                >
                  <option value="DEVELOPER">DEVELOPER (Investigate, Root Cause, Verify)</option>
                  <option value="VIEWER">VIEWER (Read-Only Telemetry & Reports)</option>
                  <option value="ADMIN">ADMIN (Full Access, Integrations & Audit)</option>
                </select>
              </div>
            </div>

            {/* Submit */}
            <button
              type="submit"
              className="auth-submit-btn"
              disabled={loading}
            >
              {loading ? (
                <>
                  <Loader2 size={18} className="spin" />
                  <span>Creating Account...</span>
                </>
              ) : (
                <>
                  <span>Create Account</span>
                  <ArrowRight size={16} />
                </>
              )}
            </button>

            {/* Switch to Login */}
            <div className="auth-switch-link-wrapper">
              <span>Already have an account? </span>
              <Link to="/login" className="auth-switch-link">
                Sign in
              </Link>
            </div>
          </form>
        </section>
      </main>

      <footer className="auth-footer">
        <p style={{ margin: "0 0 4px" }}>
          © 2026 AI Incident Response & Root Cause Analysis Platform.
        </p>
        <p style={{ margin: 0, color: "#94a3b8", fontSize: "0.72rem" }}>
          Protected by Argon2 Hashing & JWT Authorization.
        </p>
      </footer>
    </div>
  );
};
