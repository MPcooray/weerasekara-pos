import { FormEvent, useState } from "react";
import { Eye, EyeOff, LockKeyhole } from "lucide-react";
import { login, type User } from "../../lib/api";

export function LoginScreen({ onAuthenticated }: { onAuthenticated: (user: User) => void }) {
  const [tenant, setTenant] = useState("weerasekara-optics");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [error, setError] = useState("");
  const [submitting, setSubmitting] = useState(false);
  async function submit(event: FormEvent) {
    event.preventDefault(); setError(""); setSubmitting(true);
    try { onAuthenticated(await login(tenant, email, password)); }
    catch (reason) { setError(reason instanceof Error ? reason.message : "Unable to sign in"); }
    finally { setSubmitting(false); }
  }
  return <main className="login-page">
    <section className="login-intro"><div className="brand brand--light"><span className="brand__mark">T</span><span><b>Tetrova</b><small>Optical POS</small></span></div><div><p className="kicker kicker--light">Weerasekara Optics</p><h1>Welcome back to<br /><em>clearer business.</em></h1><p>Customers, visits, and care history—all in one secure workspace.</p></div><small>Built by Tetrova Technologies · Sri Lanka</small></section>
    <section className="login-panel"><form className="login-card" onSubmit={submit}>
      <div className="login-card__icon"><LockKeyhole /></div><p className="eyebrow">Secure staff access</p><h2>Sign in</h2><p className="muted">Use your shop credentials to continue.</p>
      {error && <div className="alert alert--error" role="alert">{error}</div>}
      <label>Shop code<input required value={tenant} onChange={(e) => setTenant(e.target.value)} autoComplete="organization" /></label>
      <label>Email address<input required type="email" value={email} onChange={(e) => setEmail(e.target.value)} autoComplete="username" /></label>
      <label>Password<div className="password-field"><input required type={showPassword ? "text" : "password"} value={password} onChange={(e) => setPassword(e.target.value)} autoComplete="current-password" /><button type="button" aria-label={showPassword ? "Hide password" : "Show password"} onClick={() => setShowPassword((value) => !value)}>{showPassword ? <EyeOff size={18} /> : <Eye size={18} />}</button></div></label>
      <button className="button button--primary button--wide" disabled={submitting}>{submitting ? "Signing in…" : "Sign in securely"}</button>
    </form></section>
  </main>;
}
