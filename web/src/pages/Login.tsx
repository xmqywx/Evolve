import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Lock } from 'lucide-react';
import { login, isLoggedIn } from '../utils/api';

export default function LoginPage() {
  const navigate = useNavigate();
  const [secret, setSecret] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  if (isLoggedIn()) {
    navigate('/', { replace: true });
    return null;
  }

  const handleLogin = async () => {
    if (!secret.trim()) return;
    setLoading(true);
    setError('');
    try {
      await login(secret);
      navigate('/', { replace: true });
    } catch {
      setError('认证失败');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="flex items-center justify-center min-h-screen bg-[var(--surface)]">
      <div className="w-full max-w-sm p-8 border border-[var(--border)] rounded-xl bg-[var(--surface-alt)]">
        <div className="text-center mb-8">
          <h1 className="text-2xl font-bold text-[var(--accent)]">MyAgent</h1>
          <p className="text-sm text-[var(--text-muted)] mt-1">AI 控制面板</p>
        </div>

        <div className="relative mb-4">
          <Lock size={16} className="absolute left-3 top-1/2 -translate-y-1/2 text-[var(--text-muted)]" />
          <input
            type="password"
            placeholder="输入密钥"
            value={secret}
            onChange={(e) => setSecret(e.target.value)}
            onKeyDown={(e) => e.key === 'Enter' && handleLogin()}
            className="w-full pl-10 pr-4 py-2.5 rounded-lg border border-[var(--border)]
                       bg-[var(--surface)] text-[var(--text)]
                       placeholder:text-[var(--text-muted)]
                       focus:outline-none focus:ring-2 focus:ring-[var(--accent)] focus:border-transparent
                       transition-colors"
          />
        </div>

        {error && (
          <p className="text-sm text-red-400 mb-4">{error}</p>
        )}

        <button
          onClick={handleLogin}
          disabled={loading || !secret.trim()}
          className="w-full py-2.5 rounded-lg font-medium text-white
                     bg-[var(--accent)] hover:bg-[var(--accent-hover)]
                     disabled:opacity-50 disabled:cursor-not-allowed
                     transition-colors"
        >
          {loading ? '登录中...' : '登录'}
        </button>
      </div>
    </div>
  );
}
