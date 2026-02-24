import { useEffect, useState, useRef } from 'react';
import { useNavigate } from 'react-router-dom';
import { Terminal, LogIn, Shield, ArrowLeft, KeyRound, Lock } from 'lucide-react';
import { signIn, confirmSignIn, fetchAuthSession } from 'aws-amplify/auth';
import { useAuth } from '../hooks/useAuth';
import { config } from '../config';
import { localDevLogin, setSession } from '../lib/auth';
import type { LocalDevUser } from '../types';

type LoginStep = 'credentials' | 'mfa' | 'newPassword';

export function LoginPage() {
  const { user, refreshUser } = useAuth();
  const navigate = useNavigate();

  const [step, setStep] = useState<LoginStep>('credentials');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [totpCode, setTotpCode] = useState('');
  const [newPassword, setNewPassword] = useState('');
  const [confirmPw, setConfirmPw] = useState('');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);
  const [devUsers, setDevUsers] = useState<LocalDevUser[]>([]);

  // Track whether a sign-in is already in progress (Amplify state)
  const signInActive = useRef(false);

  useEffect(() => {
    if (user) navigate('/', { replace: true });
  }, [user, navigate]);

  useEffect(() => {
    if (config.localDev) {
      fetch('/rbac/users.json')
        .then((r) => r.json())
        .then((data) => setDevUsers(data.users.filter((u: LocalDevUser) => u.active)));
    }
  }, []);

  async function storeSessionAndRedirect() {
    const session = await fetchAuthSession();
    const idToken = session.tokens?.idToken?.toString() || '';
    const accessToken = session.tokens?.accessToken?.toString() || '';
    setSession({
      access_token: accessToken,
      id_token: idToken,
      expires_at: Date.now() + 3600 * 1000,
    });
    await refreshUser();
    navigate('/', { replace: true });
  }

  async function handleCredentials(e: React.FormEvent) {
    e.preventDefault();
    setError('');
    setLoading(true);

    try {
      const result = await signIn({ username: email, password });
      signInActive.current = true;

      switch (result.nextStep.signInStep) {
        case 'DONE':
          await storeSessionAndRedirect();
          return;
        case 'CONFIRM_SIGN_IN_WITH_TOTP_CODE':
          setStep('mfa');
          break;
        case 'CONFIRM_SIGN_IN_WITH_NEW_PASSWORD_REQUIRED':
          setStep('newPassword');
          break;
        default:
          setError(`Unsupported challenge: ${result.nextStep.signInStep}`);
      }
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.name : '';
      if (msg === 'NotAuthorizedException' || msg === 'UserNotFoundException') {
        setError('Incorrect email or password.');
      } else if (msg === 'UserAlreadyAuthenticatedException') {
        // Already signed in from a previous attempt - go ahead
        await storeSessionAndRedirect();
        return;
      } else {
        setError('Sign in failed. Please try again.');
      }
    } finally {
      setLoading(false);
    }
  }

  async function handleMfa(e: React.FormEvent) {
    e.preventDefault();
    setError('');
    setLoading(true);

    try {
      const result = await confirmSignIn({ challengeResponse: totpCode });
      if (result.nextStep.signInStep === 'DONE') {
        await storeSessionAndRedirect();
      } else {
        setError(`Unexpected step: ${result.nextStep.signInStep}`);
      }
    } catch {
      setError('Invalid code. Please try again.');
    } finally {
      setLoading(false);
    }
  }

  async function handleNewPassword(e: React.FormEvent) {
    e.preventDefault();
    setError('');

    if (newPassword !== confirmPw) {
      setError('Passwords do not match.');
      return;
    }
    if (newPassword.length < 12) {
      setError('Password must be at least 12 characters.');
      return;
    }

    setLoading(true);

    try {
      const result = await confirmSignIn({ challengeResponse: newPassword });
      switch (result.nextStep.signInStep) {
        case 'DONE':
          await storeSessionAndRedirect();
          return;
        case 'CONFIRM_SIGN_IN_WITH_TOTP_CODE':
          setStep('mfa');
          break;
        default:
          setError(`Unexpected step: ${result.nextStep.signInStep}`);
      }
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'Failed to set password.';
      setError(msg);
    } finally {
      setLoading(false);
    }
  }

  function resetToCredentials() {
    signInActive.current = false;
    setStep('credentials');
    setTotpCode('');
    setNewPassword('');
    setConfirmPw('');
    setError('');
  }

  // ── Render ──

  if (config.localDev) {
    return (
      <div className="cb_login">
        <div className="cb_login__box">
          <div className="cb_login__logo"><Terminal /></div>
          <h1 className="cb_login__title">CommandBridge</h1>
          <p className="cb_login__subtitle">
            Scottish Government Digital Identity<br />Internal Operations Portal
          </p>
          <p className="cb_login__dev-label">Local dev mode - select a user</p>
          <div className="cb_login__user-list">
            {devUsers.map((u) => (
              <button key={u.id} className="cb_login__user-btn" onClick={() => localDevLogin(u)}>
                <strong>{u.name}</strong>
                <span>{u.role} - {u.team}</span>
              </button>
            ))}
          </div>
        </div>
        <div className="cb_login__footer">
          <Shield /> Scottish Government - Digital Directorate
        </div>
      </div>
    );
  }

  return (
    <div className="cb_login">
      <div className="cb_login__box">
        <div className="cb_login__logo"><Terminal /></div>
        <h1 className="cb_login__title">CommandBridge</h1>
        <p className="cb_login__subtitle">
          Scottish Government Digital Identity<br />Internal Operations Portal
        </p>

        {error && <div className="cb_login__error">{error}</div>}

        {step === 'credentials' && (
          <form className="cb_login__form" onSubmit={handleCredentials}>
            <div className="cb_login__field">
              <label className="cb_label">Email</label>
              <input
                type="email"
                className="cb_input"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                placeholder="you@gov.scot"
                autoComplete="username"
                required
              />
            </div>
            <div className="cb_login__field">
              <label className="cb_label">Password</label>
              <input
                type="password"
                className="cb_input"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                placeholder="Enter your password"
                autoComplete="current-password"
                required
              />
            </div>
            <button type="submit" className="cb_button" disabled={loading}>
              <LogIn /> {loading ? 'Signing in...' : 'Sign In'}
            </button>
          </form>
        )}

        {step === 'mfa' && (
          <form className="cb_login__form" onSubmit={handleMfa}>
            <p className="cb_login__mfa-info">
              <KeyRound /> Enter the 6-digit code from your authenticator app.
            </p>
            <div className="cb_login__field">
              <label className="cb_label">Verification Code</label>
              <input
                type="text"
                className="cb_input"
                inputMode="numeric"
                autoComplete="one-time-code"
                maxLength={6}
                pattern="[0-9]*"
                value={totpCode}
                onChange={(e) => setTotpCode(e.target.value.replace(/\D/g, ''))}
                placeholder="000000"
                required
              />
            </div>
            <button type="submit" className="cb_button" disabled={loading}>
              <Shield /> {loading ? 'Verifying...' : 'Verify'}
            </button>
            <button type="button" className="cb_login__back" onClick={resetToCredentials}>
              <ArrowLeft /> Back to sign in
            </button>
          </form>
        )}

        {step === 'newPassword' && (
          <form className="cb_login__form" onSubmit={handleNewPassword}>
            <p className="cb_login__mfa-info">
              <Lock /> Your temporary password has expired. Set a new password.
            </p>
            <div className="cb_login__field">
              <label className="cb_label">New Password</label>
              <input
                type="password"
                className="cb_input"
                value={newPassword}
                onChange={(e) => setNewPassword(e.target.value)}
                placeholder="Enter new password"
                autoComplete="new-password"
                required
              />
            </div>
            <div className="cb_login__field">
              <label className="cb_label">Confirm Password</label>
              <input
                type="password"
                className="cb_input"
                value={confirmPw}
                onChange={(e) => setConfirmPw(e.target.value)}
                placeholder="Confirm new password"
                autoComplete="new-password"
                required
              />
            </div>
            <p className="cb_login__hint">
              Min 12 characters. Must include uppercase, lowercase, number, and symbol.
            </p>
            <button type="submit" className="cb_button" disabled={loading}>
              <Lock /> {loading ? 'Setting password...' : 'Set Password'}
            </button>
            <button type="button" className="cb_login__back" onClick={resetToCredentials}>
              <ArrowLeft /> Back to sign in
            </button>
          </form>
        )}
      </div>
      <div className="cb_login__footer">
        <Shield /> Scottish Government - Digital Directorate
      </div>
    </div>
  );
}
