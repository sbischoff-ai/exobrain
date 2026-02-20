/** Thin adapter over fetch for backend API calls. */
export async function apiClient<T>(input: string, init?: RequestInit): Promise<T> {
  const response = await fetch(input, init);
  if (!response.ok) {
    throw new Error(`API request failed: ${response.status} ${input}`);
  }
  return (await response.json()) as T;
}

export async function apiClientAllowUnauthorized<T>(input: string): Promise<T | null> {
  const response = await fetch(input);
  if (response.status === 401) {
    return null;
  }
  if (!response.ok) {
    throw new Error(`API request failed: ${response.status} ${input}`);
  }
  return (await response.json()) as T;
}
