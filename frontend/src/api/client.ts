import { useCallback, useEffect, useState } from 'react';

export class ApiError extends Error {
  status: number;
  errors: Record<string, string>;
  constructor(status: number, message: string, errors: Record<string, string> = {}) {
    super(message);
    this.status = status;
    this.errors = errors;
  }
}

async function request<T>(method: string, path: string, body?: unknown): Promise<T> {
  let res: Response;
  try {
    res = await fetch(`/api${path}`, {
      method,
      headers: {
        'ngrok-skip-browser-warning': 'true',
        ...(body !== undefined ? { 'Content-Type': 'application/json' } : {}),
      },
      body: body !== undefined ? JSON.stringify(body) : undefined,
    });
  } catch {
    throw new ApiError(0, 'Cannot reach the API. Is the backend running on port 8000?');
  }
  if (res.status === 204) return undefined as T;
  const data = await res.json().catch(() => null);
  if (!res.ok) {
    const detail = data?.detail;
    const errors = detail && typeof detail === 'object' && detail.errors ? detail.errors : {};
    const message = typeof detail === 'string' ? detail : 'Something went wrong. Please check the form and try again.';
    throw new ApiError(res.status, message, errors);
  }
  return data as T;
}

/** Multipart upload with real progress, which fetch cannot report. */
function upload<T>(path: string, form: FormData, onProgress?: (percent: number) => void): Promise<T> {
  return new Promise((resolve, reject) => {
    const xhr = new XMLHttpRequest();
    xhr.open('POST', `/api${path}`);
    xhr.setRequestHeader('ngrok-skip-browser-warning', 'true');
    if (onProgress) {
      xhr.upload.onprogress = (e) => {
        if (e.lengthComputable) onProgress(Math.round((e.loaded / e.total) * 100));
      };
    }
    xhr.onload = () => {
      let data: unknown = null;
      try { data = JSON.parse(xhr.responseText); } catch { /* non-JSON error body */ }
      if (xhr.status >= 200 && xhr.status < 300) return resolve(data as T);
      const detail = (data as { detail?: unknown } | null)?.detail;
      const errors = detail && typeof detail === 'object' && 'errors' in detail
        ? (detail as { errors: Record<string, string> }).errors : {};
      const message = typeof detail === 'string' ? detail
        : (detail && typeof detail === 'object' && 'message' in detail
          ? String((detail as { message: unknown }).message)
          : 'The upload failed. Please check the file and try again.');
      reject(new ApiError(xhr.status, message, errors));
    };
    xhr.onerror = () => reject(new ApiError(0, 'Cannot reach the API. Is the backend running on port 8000?'));
    xhr.send(form);
  });
}

export const api = {
  get: <T,>(path: string) => request<T>('GET', path),
  post: <T,>(path: string, body?: unknown) => request<T>('POST', path, body ?? {}),
  put: <T,>(path: string, body: unknown) => request<T>('PUT', path, body),
  patch: <T,>(path: string, body: unknown) => request<T>('PATCH', path, body),
  del: (path: string) => request<void>('DELETE', path),
  upload,
};

export function useApi<T>(path: string | null) {
  const [data, setData] = useState<T | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(path !== null);
  const [tick, setTick] = useState(0);

  useEffect(() => {
    if (path === null) return;
    let cancelled = false;
    setLoading(true);
    api.get<T>(path)
      .then((d) => { if (!cancelled) { setData(d); setError(null); } })
      .catch((e: Error) => { if (!cancelled) setError(e.message); })
      .finally(() => { if (!cancelled) setLoading(false); });
    return () => { cancelled = true; };
  }, [path, tick]);

  const reload = useCallback(() => setTick((t) => t + 1), []);
  return { data, error, loading, reload, setData };
}
