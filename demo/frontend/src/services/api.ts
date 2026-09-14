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

export async function uploadRecognitionVideo(
  roomId: string,
  kind: 'lipread',
  segmentId: string,
  csrfToken: string,
  video: Blob,
) {
  const query = new URLSearchParams({ kind, segment_id: segmentId });
  const response = await fetch(
    `/api/rooms/${encodeURIComponent(roomId)}/recognition/video?${query.toString()}`,
    {
      method: 'POST',
      credentials: 'same-origin',
      headers: {
        'Content-Type': video.type || 'video/webm',
        'X-CSRF-Token': csrfToken,
      },
      body: video,
    },
  );
  if (!response.ok) {
    const body = await response.json().catch(() => ({}));
    throw new Error(typeof body.detail === 'string' ? body.detail : '撮影動画を送信できませんでした');
  }
}

export function wsURL(path: string) {
  return `${location.protocol === 'https:' ? 'wss:' : 'ws:'}//${location.host}${path}`;
}
