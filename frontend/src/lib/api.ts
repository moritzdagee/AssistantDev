/**
 * API-Wrapper — einheitliche Schnittstelle fuer Backend-Calls.
 *
 * Zwei Pfade:
 *  1. pywebview.api.*  — JS-zu-Python-Bridge im nativen Dashboard-Fenster
 *  2. fetch()          — HTTP-Routen am web_server.py auf :8080
 *
 * Die Endpunkt-Pfade bleiben 1:1 identisch zur bestehenden Implementierung
 * in src/web_server.py — siehe frontend/README.md fuer die vollstaendige
 * Endpunkt-Matrix.
 */

type Json = unknown;

export class ApiError extends Error {
  status: number;
  body: Json;
  constructor(message: string, status: number, body: Json) {
    super(message);
    this.status = status;
    this.body = body;
  }
}

async function parseResponse(res: Response): Promise<Json> {
  const text = await res.text();
  try {
    return text ? JSON.parse(text) : null;
  } catch {
    return text;
  }
}

async function request<T = Json>(
  method: 'GET' | 'POST' | 'PUT' | 'DELETE',
  path: string,
  body?: Json,
  init?: RequestInit,
): Promise<T> {
  const headers: Record<string, string> = {
    Accept: 'application/json',
    ...(init?.headers as Record<string, string> | undefined),
  };
  if (body !== undefined && !(body instanceof FormData)) {
    headers['Content-Type'] = 'application/json';
  }
  const res = await fetch(path, {
    method,
    headers,
    body:
      body === undefined
        ? undefined
        : body instanceof FormData
          ? body
          : JSON.stringify(body),
    ...init,
  });
  const parsed = await parseResponse(res);
  if (!res.ok) {
    throw new ApiError(`${method} ${path} → ${res.status}`, res.status, parsed);
  }
  return parsed as T;
}

export const api = {
  get: <T = Json>(path: string, init?: RequestInit) =>
    request<T>('GET', path, undefined, init),
  post: <T = Json>(path: string, body?: Json, init?: RequestInit) =>
    request<T>('POST', path, body, init),
  put: <T = Json>(path: string, body?: Json, init?: RequestInit) =>
    request<T>('PUT', path, body, init),
  del: <T = Json>(path: string, init?: RequestInit) =>
    request<T>('DELETE', path, undefined, init),
};

/**
 * pywebview-Bridge. Liefert null, wenn das Frontend im regulaeren Browser laeuft
 * (Vite dev-Server) oder die Bridge noch nicht initialisiert ist.
 */
export function pywebviewApi(): NonNullable<Window['pywebview']>['api'] | null {
  return window.pywebview?.api ?? null;
}

export function isPywebview(): boolean {
  return typeof window !== 'undefined' && !!window.pywebview;
}
