import { useState, type FormEvent } from 'react';
import { Link, Navigate, useNavigate } from 'react-router-dom';
import { ApiError, type ApiSchemas } from '../api/client';
import { useAuth } from '../auth/useAuth';
import { Button } from '../components/ui/Button';
import { Input } from '../components/ui/Input';

interface FieldErrors {
  email?: string;
  password?: string;
  form?: string;
}

const EMAIL_PATTERN = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;

function mapValidationErrors(detail: unknown, errors: FieldErrors): void {
  const body = detail as ApiSchemas['HTTPValidationError'] | null;
  if (!body || !Array.isArray(body.detail)) return;
  for (const item of body.detail) {
    const field = item.loc[item.loc.length - 1];
    if (field === 'email' && !errors.email) errors.email = item.msg;
    if (field === 'password' && !errors.password) errors.password = item.msg;
  }
}

export function RegisterPage() {
  const { isAuthenticated, register } = useAuth();
  const navigate = useNavigate();
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [errors, setErrors] = useState<FieldErrors>({});
  const [submitting, setSubmitting] = useState(false);

  if (isAuthenticated) {
    return <Navigate to="/" replace />;
  }

  function validate(): FieldErrors {
    const next: FieldErrors = {};
    if (!email.trim()) {
      next.email = 'Email is required';
    } else if (!EMAIL_PATTERN.test(email.trim())) {
      next.email = 'Enter a valid email address';
    }
    if (!password) {
      next.password = 'Password is required';
    } else if (password.length < 8) {
      next.password = 'Password must be at least 8 characters';
    }
    return next;
  }

  async function handleSubmit(event: FormEvent) {
    event.preventDefault();
    const nextErrors = validate();
    setErrors(nextErrors);
    if (Object.keys(nextErrors).length > 0) return;

    setSubmitting(true);
    try {
      await register(email.trim(), password);
      navigate('/', { replace: true });
    } catch (error) {
      if (error instanceof ApiError) {
        if (error.status === 409) {
          setErrors({ email: 'This email is already registered' });
        } else if (error.status === 422) {
          const next: FieldErrors = {};
          mapValidationErrors(error.detail, next);
          setErrors(next);
        } else {
          setErrors({ form: error.message });
        }
      } else {
        setErrors({ form: 'Something went wrong. Please try again.' });
      }
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="flex min-h-screen items-center justify-center bg-slate-950 px-4">
      <form
        onSubmit={handleSubmit}
        noValidate
        className="w-full max-w-sm space-y-4 rounded-xl border border-slate-800 bg-slate-900 p-6"
      >
        <h1 className="text-xl font-semibold text-slate-100">Create your account</h1>
        {errors.form && (
          <p role="alert" className="rounded-md bg-red-950/50 p-3 text-sm text-red-300">
            {errors.form}
          </p>
        )}
        <Input
          label="Email"
          type="email"
          autoComplete="email"
          value={email}
          onChange={(event) => setEmail(event.target.value)}
          error={errors.email}
          required
        />
        <Input
          label="Password"
          type="password"
          autoComplete="new-password"
          value={password}
          onChange={(event) => setPassword(event.target.value)}
          error={errors.password}
          hint="At least 8 characters"
          required
        />
        <Button type="submit" disabled={submitting} className="w-full">
          {submitting ? 'Creating account…' : 'Register'}
        </Button>
        <p className="text-sm text-slate-400">
          Already have an account?{' '}
          <Link to="/login" className="font-medium text-indigo-400 hover:underline">
            Log in
          </Link>
        </p>
      </form>
    </div>
  );
}
