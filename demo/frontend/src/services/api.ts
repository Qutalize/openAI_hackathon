export async function api<T>(path: string, init: RequestInit = {}): Promise<T> {
  const response = await fetch(path, {
    ...init,
    credentials: 'same-origin',
    headers: {
      'Content-Type': 'application/json',
      ...init.headers,
    },
  });
  if (!response.ok) {
    const body = await response.json().catch(() => ({}));
    const message =
      typeof body.detail === 'string' ? body.detail : '入力内容またはサーバー接続を確認してください';
    throw Object.assign(new Error(message), { status: response.status });
  }
  return response.status === 204 ? (undefined as T) : response.json();
}

export function wsURL(path: string) {
  return `${location.protocol === 'https:' ? 'wss:' : 'ws:'}//${location.host}${path}`;
}
