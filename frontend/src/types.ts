// Type definitions for Swiss Transport App

export type TransportMode = 'rail' | 'bus' | 'tram' | 'metro' | 'funicular' | 'ferry' | 'cableway' | 'walk' | 'unknown';

export interface Location {
  id: string;
  name: string;
  type: 'stop' | 'address' | 'poi' | 'coordinate';
  latitude?: number;
  longitude?: number;
  locality?: string;
}

export interface StopPoint {
  id: string;
  name: string;
  platform?: string;
  scheduled_time: string;
  estimated_time?: string;
  delay_minutes: number;
  latitude?: number;
  longitude?: number;
}

export interface DelayPrediction {
  predicted_delay_minutes: number;
  confidence_score: number;
  factors: string[];
  is_peak_hour: boolean;
  prediction_time: string;
}

export interface TripLeg {
  leg_id: string;
  mode: TransportMode;
  line_name?: string;
  line_number?: string;
  destination_text?: string;
  operator?: string;
  origin: StopPoint;
  destination: StopPoint;
  intermediate_stops: StopPoint[];
  duration_minutes: number;
  has_realtime: boolean;
  delay_prediction?: DelayPrediction;
}

export interface Disruption {
  id: string;
  title: string;
  description: string;
  severity: 'info' | 'warning' | 'severe';
  affected_lines: string[];
  affected_stops: string[];
  start_time?: string;
  end_time?: string;
  is_active: boolean;
}

export interface Trip {
  trip_id: string;
  legs: TripLeg[];
  departure_time: string;
  arrival_time: string;
  duration_minutes: number;
  num_transfers: number;
  has_disruptions: boolean;
  disruptions: Disruption[];
}

export interface TripSearchResult {
  trips: Trip[];
  search_time: string;
}

export interface TripPlanRequest {
  origin_id: string;
  origin_name: string;
  destination_id: string;
  destination_name: string;
  departure_time?: string;
  num_results?: number;
  include_predictions?: boolean;
}
