import { useState, type FormEvent } from "react";
import { Link, useLocation, useNavigate } from "react-router-dom";
import { AuthCard } from "../components/AuthCard";
import { Button } from "../components/Button";
import { FormField } from "../components/FormField";
import { useAuth } from "../context/AuthContext";
import { ApiError } from "../lib/api";

export function LoginPage() {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const { login } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  const justRegistered = Boolean((location.state as { registered?: boolean } | null)?.registered);

  async function handleSubmit(event: FormEvent) {
    event.preventDefault();
    setError(null);
    setSubmitting(true);
    try {
      await login(email, password);
      await navigate("/profile");
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Login failed. Please try again.");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <AuthCard eyebrow="Welcome back" title="Log in">
      <form onSubmit={handleSubmit} noValidate className="flex flex-col gap-5">
        {justRegistered && (
          <p className="rounded-sm border border-success/30 bg-success/10 px-3 py-2 text-sm text-success">
            Account created. Please log in.
          </p>
        )}
        {error && (
          <p
            role="alert"
            className="rounded-sm border border-danger/30 bg-danger/10 px-3 py-2 text-sm text-danger"
          >
            {error}
          </p>
        )}
        <FormField
          id="email"
          label="Email"
          type="email"
          value={email}
          onChange={(e) => setEmail(e.target.value)}
          required
          placeholder="you@example.com"
        />
        <FormField
          id="password"
          label="Password"
          type="password"
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          required
          placeholder="Your password"
        />
        <Button type="submit" loading={submitting} loadingText="Logging in...">
          Log in
        </Button>
      </form>
      <p className="text-center text-sm text-ink-soft">
        Need an account?{" "}
        <Link to="/register" className="font-medium text-primary underline underline-offset-2">
          Register
        </Link>
      </p>
    </AuthCard>
  );
}
