// Custom hooks for Swiss Transport App

import { useState, useEffect, useCallback, useRef } from 'react';
import type { Location, Disruption } from '../types';
import { searchLocations, subscribeToUpdates } from '../api/client';

// Debounced location search hook
export function useLocationSearch() {
  const [query, setQuery] = useState('');
  const [results, setResults] = useState<Location[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const debounceRef = useRef<ReturnType<typeof setTimeout>>();

  const search = useCallback(async (searchQuery: string) => {
    if (searchQuery.length < 2) {
      setResults([]);
      return;
    }

    setLoading(true);
    setError(null);

    try {
      const locations = await searchLocations(searchQuery);
      setResults(locations);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Search failed');
      setResults([]);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    if (debounceRef.current) {
      clearTimeout(debounceRef.current);
    }

    debounceRef.current = setTimeout(() => {
      search(query);
    }, 300);

    return () => {
      if (debounceRef.current) {
        clearTimeout(debounceRef.current);
      }
    };
  }, [query, search]);

  return { query, setQuery, results, loading, error, clearResults: () => setResults([]) };
}

// Data availability status
interface DataAvailability {
  gtfs_rt: boolean;
  siri_sx: boolean;
  traffic_situations: boolean;
  traffic_lights: boolean;
}

// Real-time disruption updates hook with heartbeat handling
export function useDisruptionUpdates() {
  const [disruptions, setDisruptions] = useState<Disruption[]>([]);
  const [connected, setConnected] = useState(false);
  const [lastUpdate, setLastUpdate] = useState<Date | null>(null);
  const [availability, setAvailability] = useState<DataAvailability>({
    gtfs_rt: true,
    siri_sx: true,
    traffic_situations: true,
    traffic_lights: true,
  });
  const eventSourceRef = useRef<EventSource | null>(null);

  useEffect(() => {
    const handleMessage = (event: MessageEvent) => {
      try {
        const data = JSON.parse(event.data);

        // Handle heartbeat events (keep-alive)
        if (data.type === 'heartbeat') {
          // Heartbeat received, connection is alive
          return;
        }

        // Handle disruption updates
        if (data.disruptions) {
          setDisruptions(data.disruptions);
          setLastUpdate(new Date());
        }

        // Handle availability status updates
        if (data.available !== undefined) {
          setAvailability(prev => ({
            ...prev,
            siri_sx: data.available,
          }));
        }
      } catch (err) {
        console.error('Error parsing SSE message:', err);
      }
    };

    eventSourceRef.current = subscribeToUpdates(handleMessage);

    eventSourceRef.current.onopen = () => {
      setConnected(true);
    };

    eventSourceRef.current.onerror = () => {
      setConnected(false);
    };

    return () => {
      if (eventSourceRef.current) {
        eventSourceRef.current.close();
      }
    };
  }, []);

  return { disruptions, connected, lastUpdate, availability };
}
