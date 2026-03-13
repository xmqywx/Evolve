const BASE_URL = import.meta.env.VITE_API_URL || '';

function getToken(): string | null {
  return localStorage.getItem('token');
}

function authHeaders(): Record<string, string> {
  const token = getToken();
  return token ? { Authorization: `Bearer ${token}` } : {};
}

export async function apiFetch<T>(path: string, options?: RequestInit): Promise<T> {
  const resp = await fetch(`${BASE_URL}${path}`, {
    ...options,
    headers: {
      'Content-Type': 'application/json',
      ...authHeaders(),
      ...options?.headers,
    },
  });
  if (resp.status === 401) {
    localStorage.removeItem('token');
    window.location.href = '/login';
    throw new Error('Unauthorized');
  }
  if (!resp.ok) {
    throw new Error(`API error: ${resp.status}`);
  }
  return resp.json();
}

export async function login(secret: string): Promise<string> {
  const data = await apiFetch<{ token: string }>('/api/login', {
    method: 'POST',
    body: JSON.stringify({ secret }),
  });
  localStorage.setItem('token', data.token);
  return data.token;
}

export function logout(): void {
  localStorage.removeItem('token');
  window.location.href = '/login';
}

export function isLoggedIn(): boolean {
  return !!getToken();
}

export function createWsUrl(path: string): string {
  const token = getToken() || '';
  const proto = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
  const host = BASE_URL ? new URL(BASE_URL).host : window.location.host;
  return `${proto}//${host}${path}?token=${encodeURIComponent(token)}`;
}
