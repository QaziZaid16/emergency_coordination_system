export type ApiOptions = Omit<RequestInit, 'headers'> & { token?: string | null; headers?: HeadersInit };

export class ApiError extends Error {
  constructor(message: string, readonly status: number) { super(message); this.name = 'ApiError'; }
}

export async function request<T>(origin: string, path: string, options: ApiOptions = {}): Promise<T> {
  const { token, headers: supplied, ...init } = options;
  let response: Response;
  try {
    response = await fetch(`${origin}/api/v1${path}`, {
      ...init,
      redirect: 'error',
      headers: { ...(init.body ? { 'Content-Type': 'application/json' } : {}), ...(token ? { Authorization: `Bearer ${token}` } : {}), ...Object.fromEntries(new Headers(supplied).entries()) },
    });
  } catch {
    throw new ApiError('Could not reach the coordination service. Check the API origin and connection.', 0);
  }
  if (response.status === 204) return null as T;
  const body = await response.json().catch(() => ({} as { detail?: unknown }));
  if (!response.ok) {
    if (typeof body.detail === 'string') throw new ApiError(body.detail, response.status);
    if (Array.isArray(body.detail)) throw new ApiError(body.detail.map((e: any) => `${(e.loc || []).filter((x: string) => x !== 'body').join('.')}: ${e.msg || 'Invalid value'}`).join('; '), response.status);
    throw new ApiError(`Request failed (${response.status})`, response.status);
  }
  return body as T;
}
