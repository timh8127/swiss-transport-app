// Trip result display component

import { format } from 'date-fns';
import {
  Train, Bus, Tram, Ship, Cable, Footprints,
  ChevronDown, ChevronUp, AlertTriangle, Clock,
  TrendingUp, Gauge
} from 'lucide-react';
import type { Trip, TripLeg, TransportMode } from '../types';
import { useState } from 'react';

const MODE_ICONS: Record<TransportMode, typeof Train> = {
  rail: Train,
  bus: Bus,
  tram: Tram,
  metro: Train,
  funicular: Cable,
  ferry: Ship,
  cableway: Cable,
  walk: Footprints,
  unknown: Train,
};

const MODE_COLORS: Record<TransportMode, string> = {
  rail: 'bg-red-600',
  bus: 'bg-blue-600',
  tram: 'bg-green-600',
  metro: 'bg-purple-600',
  funicular: 'bg-orange-600',
  ferry: 'bg-cyan-600',
  cableway: 'bg-amber-600',
  walk: 'bg-gray-500',
  unknown: 'bg-gray-400',
};

function formatTime(dateStr: string): string {
  return format(new Date(dateStr), 'HH:mm');
}

function DelayBadge({ minutes, type }: { minutes: number; type: 'actual' | 'predicted' }) {
  if (minutes === 0) return null;

  const bgColor = type === 'predicted' ? 'bg-amber-100 text-amber-800' : 'bg-red-100 text-red-800';

  return (
    <span className={`text-xs px-2 py-0.5 rounded-full ${bgColor}`}>
      {type === 'predicted' ? '~' : ''}+{minutes} min
    </span>
  );
}

function LegDetail({ leg, index }: { leg: TripLeg; index: number }) {
  const Icon = MODE_ICONS[leg.mode];
  const colorClass = MODE_COLORS[leg.mode];
  const [showStops, setShowStops] = useState(false);

  return (
    <div className="relative pl-8">
      {/* Mode icon */}
      <div className={`absolute left-0 top-0 w-6 h-6 rounded-full ${colorClass} flex items-center justify-center`}>
        <Icon className="w-4 h-4 text-white" />
      </div>

      {/* Vertical line */}
      <div className={`absolute left-[11px] top-6 bottom-0 w-0.5 ${colorClass}`} />

      <div className="pb-6">
        {/* Origin */}
        <div className="flex items-start justify-between">
          <div>
            <div className="font-semibold text-gray-900">{leg.origin.name}</div>
            {leg.origin.platform && (
              <div className="text-sm text-gray-600">
                {leg.mode === 'bus' || leg.mode === 'tram' ? 'Stop' : 'Track'} {leg.origin.platform}
              </div>
            )}
          </div>
          <div className="text-right">
            <div className="font-mono text-lg">{formatTime(leg.origin.scheduled_time)}</div>
            {leg.origin.delay_minutes > 0 && (
              <DelayBadge minutes={leg.origin.delay_minutes} type="actual" />
            )}
          </div>
        </div>

        {/* Line info */}
        {leg.mode !== 'walk' && (
          <div className="mt-2 flex items-center gap-2 text-sm text-gray-600">
            <span className={`px-2 py-0.5 rounded text-white text-xs font-bold ${colorClass}`}>
              {leg.line_name || leg.mode.toUpperCase()}
            </span>
            {leg.destination_text && (
              <span>→ {leg.destination_text}</span>
            )}
            <span className="text-gray-400">({leg.duration_minutes} min)</span>
          </div>
        )}

        {leg.mode === 'walk' && (
          <div className="mt-2 text-sm text-gray-500">
            Walk ({leg.duration_minutes} min)
          </div>
        )}

        {/* Delay Prediction */}
        {leg.delay_prediction && (
          <div className="mt-3 p-3 bg-amber-50 rounded-lg border border-amber-200">
            <div className="flex items-center gap-2 text-amber-800">
              <TrendingUp className="w-4 h-4" />
              <span className="font-medium">Predicted Delay</span>
            </div>
            <div className="mt-2 flex items-center gap-4">
              <span className="text-2xl font-bold text-amber-700">
                +{leg.delay_prediction.predicted_delay_minutes} min
              </span>
              <div className="flex items-center gap-1 text-sm text-amber-600">
                <Gauge className="w-4 h-4" />
                <span>{Math.round(leg.delay_prediction.confidence_score * 100)}% confidence</span>
              </div>
            </div>
            {leg.delay_prediction.factors.length > 0 && (
              <div className="mt-2 text-xs text-amber-700">
                Factors: {leg.delay_prediction.factors.join(', ')}
              </div>
            )}
            {leg.delay_prediction.is_peak_hour && (
              <div className="mt-1 text-xs text-amber-600 flex items-center gap-1">
                <Clock className="w-3 h-3" />
                Peak hour traffic
              </div>
            )}
          </div>
        )}

        {/* Intermediate stops */}
        {leg.intermediate_stops.length > 0 && (
          <button
            onClick={() => setShowStops(!showStops)}
            className="mt-2 text-sm text-gray-500 hover:text-gray-700 flex items-center gap-1"
          >
            {showStops ? <ChevronUp className="w-4 h-4" /> : <ChevronDown className="w-4 h-4" />}
            {leg.intermediate_stops.length} intermediate stop{leg.intermediate_stops.length > 1 ? 's' : ''}
          </button>
        )}

        {showStops && (
          <div className="mt-2 pl-4 border-l-2 border-gray-200 space-y-2">
            {leg.intermediate_stops.map((stop, i) => (
              <div key={i} className="text-sm flex justify-between">
                <span className="text-gray-600">{stop.name}</span>
                <span className="font-mono text-gray-500">{formatTime(stop.scheduled_time)}</span>
              </div>
            ))}
          </div>
        )}

        {/* Destination */}
        <div className="mt-4 flex items-start justify-between">
          <div>
            <div className="font-semibold text-gray-900">{leg.destination.name}</div>
            {leg.destination.platform && (
              <div className="text-sm text-gray-600">
                {leg.mode === 'bus' || leg.mode === 'tram' ? 'Stop' : 'Track'} {leg.destination.platform}
              </div>
            )}
          </div>
          <div className="text-right">
            <div className="font-mono text-lg">{formatTime(leg.destination.scheduled_time)}</div>
            {leg.destination.delay_minutes > 0 && (
              <DelayBadge minutes={leg.destination.delay_minutes} type="actual" />
            )}
          </div>
        </div>
      </div>
    </div>
  );
}

interface TripCardProps {
  trip: Trip;
  isSelected: boolean;
  onSelect: () => void;
}

export function TripCard({ trip, isSelected, onSelect }: TripCardProps) {
  return (
    <div
      onClick={onSelect}
      className={`bg-white rounded-xl shadow-sm border-2 transition cursor-pointer ${
        isSelected ? 'border-sbb-red' : 'border-transparent hover:border-gray-200'
      }`}
    >
      {/* Header */}
      <div className="p-4 border-b border-gray-100">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-4">
            <div>
              <span className="text-2xl font-bold">{formatTime(trip.departure_time)}</span>
              <span className="mx-2 text-gray-400">→</span>
              <span className="text-2xl font-bold">{formatTime(trip.arrival_time)}</span>
            </div>
            <div className="text-sm text-gray-500">
              {trip.duration_minutes} min · {trip.num_transfers} transfer{trip.num_transfers !== 1 ? 's' : ''}
            </div>
          </div>

          {/* Mode icons */}
          <div className="flex items-center gap-1">
            {trip.legs.filter(l => l.mode !== 'walk').map((leg, i) => {
              const Icon = MODE_ICONS[leg.mode];
              return (
                <div
                  key={i}
                  className={`w-8 h-8 rounded-full ${MODE_COLORS[leg.mode]} flex items-center justify-center`}
                >
                  <Icon className="w-4 h-4 text-white" />
                </div>
              );
            })}
          </div>
        </div>

        {/* Disruption warning */}
        {trip.has_disruptions && (
          <div className="mt-3 p-2 bg-red-50 rounded-lg flex items-start gap-2 text-red-800">
            <AlertTriangle className="w-5 h-5 flex-shrink-0" />
            <div className="text-sm">
              <div className="font-medium">Disruptions on this route</div>
              {trip.disruptions[0] && (
                <div className="text-red-600">{trip.disruptions[0].title}</div>
              )}
            </div>
          </div>
        )}
      </div>

      {/* Leg details (shown when selected) */}
      {isSelected && (
        <div className="p-4">
          {trip.legs.map((leg, index) => (
            <LegDetail key={leg.leg_id} leg={leg} index={index} />
          ))}
        </div>
      )}
    </div>
  );
}
