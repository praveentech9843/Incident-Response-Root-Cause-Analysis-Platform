import React, { useState, useEffect } from "react";
import { useNavigate, useLocation, Link } from "react-router-dom";
import { useAuth } from "../context/useAuth";
import {
  ShieldAlert,
  GitMerge,
  Cpu,
  CheckCircle2,
  Lock,
  User as UserIcon,
  Eye,
  EyeOff,
  Loader2,
  ArrowRight,
  AlertCircle,
} from "lucide-react";

export const LoginPage: React.FC = () => {
  const { login, isAuthenticated } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();

  // Retrieve destination if redirected from a protected route
  const fromLocation = (location.state as { from?: Location })?.from;
  const redirectPath = fromLocation?.pathname ? `${fromLocation.pathname}${fromLocation.search || ""}` : "/incidents";

  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  // If already logged in, navigate straight to dashboard or intended route
  useEffect(() => {
    if (isAuthenticated) {
      navigate(redirectPath, { replace: true });
    }
  }, [isAuthenticated, navigate, redirectPath]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!username.trim() || !password) {
      setError("Please enter both your username/email and password.");
      return;
    }

    setError(null);
    setLoading(true);

    try {
      await login({
        username: username.trim(),
        password,
      });
      // Redirect after successful authentication
      navigate(redirectPath, { replace: true });
    } catch (err: unknown) {
      let message = "Invalid credentials. Please verify your username and password.";
      if (err instanceof Error) {
        // Strip out noisy HTTP prefix if present
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
        {/* Left Section: Branding & Product Introduction */}
        <section className="auth-brand-pane">
          <div>
            <div className="auth-brand-logo-row">
              <div className="auth-logo-icon">
                <ShieldAlert size={22} />
              </div>
              <span className="auth-brand-name">AI Incident Response & RCA</span>
            </div>

            <h1 className="auth-brand-headline">
              Resolve Incidents Faster. Understand Root Causes.
            </h1>

            <p className="auth-brand-desc">
              Correlate distributed application logs, investigate cascading outages, review
              AI-generated causal hypotheses, and track runbook verification in one unified platform.
            </p>

            <div className="auth-features-list">
              <div className="auth-feature-item">
                <div className="auth-feature-icon-box">
                  <GitMerge size={18} />
                </div>
                <div>
                  <h2 className="auth-feature-title">Intelligent Incident Correlation</h2>
                  <p className="auth-feature-text">
                    Clusters noisy log streams across microservices into high-confidence incident groups.
                  </p>
                </div>
              </div>

              <div className="auth-feature-item">
                <div className="auth-feature-icon-box">
                  <Cpu size={18} />
                </div>
                <div>
                  <h2 className="auth-feature-title">Root Cause Analysis</h2>
                  <p className="auth-feature-text">
                    Ranks causal hypothesis chains with deep stack-trace parsing and anomaly attribution.
                  </p>
                </div>
              </div>

              <div className="auth-feature-item">
                <div className="auth-feature-icon-box">
                  <CheckCircle2 size={18} />
                </div>
                <div>
                  <h2 className="auth-feature-title">Investigation & Verification Tracking</h2>
                  <p className="auth-feature-text">
                    Structured developer workspaces with actionable remediation plans and immutable audit logs.
                  </p>
                </div>
              </div>
            </div>
          </div>

          {/* Tasteful Technical Illustration / Abstract Incident Monitoring Visual */}
          <div className="auth-telemetry-preview" aria-hidden="true">
            <div className="auth-preview-header">
              <span className="auth-preview-badge">
                <span className="auth-pulse-dot" />
                Live Telemetry Active
              </span>
              <span style={{ fontSize: "0.7rem", color: "#64748b", fontWeight: 500 }}>
                Cluster us-east-1
              </span>
            </div>

            <div className="auth-preview-incident-card">
              <div className="auth-preview-inc-title">
                INC-2048: Connection Pool Starvation & Latency Spike
              </div>
              <div className="auth-preview-inc-meta">
                <span style={{ color: "#dc2626", fontWeight: 600 }}>Critical</span>
                <span>Payment Gateway</span>
                <span style={{ color: "#2563eb", fontWeight: 600 }}>98% Match</span>
              </div>
            </div>

            <div className="auth-preview-stats-row">
              <div className="auth-preview-stat-box">
                <p className="auth-preview-stat-val">1.2M</p>
                <p className="auth-preview-stat-lbl">Logs Correlated</p>
              </div>
              <div className="auth-preview-stat-box">
                <p className="auth-preview-stat-val" style={{ color: "#16a34a" }}>-62%</p>
                <p className="auth-preview-stat-lbl">MTTR Reduction</p>
              </div>
              <div className="auth-preview-stat-box">
                <p className="auth-preview-stat-val">99.9%</p>
                <p className="auth-preview-stat-lbl">Detection Accuracy</p>
              </div>
            </div>
          </div>
        </section>

        {/* Right Section: Login Card */}
        <section className="auth-form-pane">
          <div className="auth-form-header">
            <h2 className="auth-form-heading">Welcome Back</h2>
            <p className="auth-form-subtitle">Sign in to continue to your workspace.</p>
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
            {/* Username or Email Input */}
            <div className="auth-form-group">
              <label htmlFor="username" className="auth-label">
                Username or Email
              </label>
              <div className="auth-input-wrapper">
                <UserIcon size={16} className="auth-input-icon" />
                <input
                  id="username"
                  name="username"
                  type="text"
                  required
                  autoFocus
                  autoComplete="username"
                  className="auth-input"
                  placeholder="developer@company.com or username"
                  value={username}
                  onChange={(e) => setUsername(e.target.value)}
                  disabled={loading}
                />
              </div>
            </div>

            {/* Password Input with Show/Hide Toggle */}
            <div className="auth-form-group">
              <label htmlFor="password" className="auth-label">
                Password
              </label>
              <div className="auth-input-wrapper">
                <Lock size={16} className="auth-input-icon" />
                <input
                  id="password"
                  name="password"
                  type={showPassword ? "text" : "password"}
                  required
                  autoComplete="current-password"
                  className="auth-input"
                  placeholder="Enter your password"
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

            {/* Submit Button */}
            <button
              type="submit"
              className="auth-submit-btn"
              disabled={loading}
            >
              {loading ? (
                <>
                  <Loader2 size={18} className="spin" />
                  <span>Signing In...</span>
                </>
              ) : (
                <>
                  <span>Sign In</span>
                  <ArrowRight size={16} />
                </>
              )}
            </button>

            {/* Switch to Registration */}
            <div className="auth-switch-link-wrapper">
              <span>Don't have an account? </span>
              <Link to="/register" className="auth-switch-link">
                Create an account
              </Link>
            </div>
          </form>
        </section>
      </main>

      {/* Footer on full viewport and mobile */}
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
