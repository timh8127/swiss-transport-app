// API client for Swiss Transport backend

import type { Location, TripSearchResult, TripPlanRequest, Disruption } from '../types';

const API_BASE = import.meta.env.VITE_API_URL || '';

async function fetchApi<T>(endpoint: string, options?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE}${endpoint}`, {
    ...options,
    headers: {
      'Content-Type': 'application/json',
      ...options?.headers,
    },
  });

  if (!response.ok) {
    throw new Error(`API error: ${response.status} ${response.statusText}`);
  }

  return response.json();
}

export async function searchLocations(query: string, limit = 10): Promise<Location[]> {
  const params = new URLSearchParams({ query, limit: limit.toString() });
  return fetchApi<Location[]>(`/api/locations?${params}`);
}

export async function planTrip(request: TripPlanRequest): Promise<TripSearchResult> {
  return fetchApi<TripSearchResult>('/api/trips', {
    method: 'POST',
    body: JSON.stringify({
      ...request,
      include_predictions: request.include_predictions ?? true,
    }),
  });
}

export async function getDisruptions(limit = 50): Promise<Disruption[]> {
  return fetchApi<Disruption[]>(`/api/disruptions?limit=${limit}`);
}

export async function getApiInfo(): Promise<Record<string, unknown>> {
  return fetchApi<Record<string, unknown>>('/api/info');
}

// SSE connection for real-time updates
export function subscribeToUpdates(onMessage: (event: MessageEvent) => void): EventSource {
  const eventSource = new EventSource(`${API_BASE}/api/events`);

  eventSource.onmessage = onMessage;

  eventSource.onerror = (error) => {
    console.error('SSE connection error:', error);
  };

  return eventSource;
}
