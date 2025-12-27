// Disruption panel component

import { AlertTriangle, AlertCircle, Info, Wifi, WifiOff } from 'lucide-react';
import type { Disruption } from '../types';
import { useDisruptionUpdates } from '../hooks';
import { format } from 'date-fns';

const SEVERITY_STYLES = {
  severe: {
    bg: 'bg-red-50',
    border: 'border-red-200',
    icon: AlertTriangle,
    iconColor: 'text-red-600',
    text: 'text-red-800',
  },
  warning: {
    bg: 'bg-amber-50',
    border: 'border-amber-200',
    icon: AlertCircle,
    iconColor: 'text-amber-600',
    text: 'text-amber-800',
  },
  info: {
    bg: 'bg-blue-50',
    border: 'border-blue-200',
    icon: Info,
    iconColor: 'text-blue-600',
    text: 'text-blue-800',
  },
};

function DisruptionItem({ disruption }: { disruption: Disruption }) {
  const style = SEVERITY_STYLES[disruption.severity];
  const Icon = style.icon;

  return (
    <div className={`p-3 rounded-lg border ${style.bg} ${style.border}`}>
      <div className="flex items-start gap-2">
        <Icon className={`w-5 h-5 flex-shrink-0 ${style.iconColor}`} />
        <div className="flex-1 min-w-0">
          <div className={`font-medium ${style.text}`}>{disruption.title}</div>
          {disruption.affected_lines.length > 0 && (
            <div className="mt-1 text-sm text-gray-600">
              Lines: {disruption.affected_lines.slice(0, 5).join(', ')}
              {disruption.affected_lines.length > 5 && ` +${disruption.affected_lines.length - 5} more`}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

export function DisruptionPanel() {
  const { disruptions, connected, lastUpdate, availability } = useDisruptionUpdates();

  return (
    <div className="bg-white rounded-xl shadow-sm p-4">
      <div className="flex items-center justify-between mb-4">
        <h2 className="text-lg font-semibold text-gray-900">Live Disruptions</h2>
        <div className="flex items-center gap-2 text-sm">
          {connected ? (
            <>
              <Wifi className="w-4 h-4 text-green-500" />
              <span className="text-green-600">Live</span>
            </>
          ) : (
            <>
              <WifiOff className="w-4 h-4 text-gray-400" />
              <span className="text-gray-500">Connecting...</span>
            </>
          )}
        </div>
      </div>

      {lastUpdate && (
        <div className="text-xs text-gray-400 mb-3">
          Updated {format(lastUpdate, 'HH:mm:ss')}
        </div>
      )}

      {/* Show warning if SIRI-SX data is unavailable */}
      {!availability.siri_sx && (
        <div className="mb-3 p-2 bg-amber-50 border border-amber-200 rounded-lg">
          <div className="flex items-center gap-2 text-amber-800 text-sm">
            <AlertCircle className="w-4 h-4" />
            <span>Live disruption data unavailable</span>
          </div>
        </div>
      )}

      <div className="space-y-2 max-h-96 overflow-y-auto">
        {disruptions.length === 0 ? (
          <div className="text-center py-8 text-gray-500">
            <Info className="w-8 h-8 mx-auto mb-2 text-gray-300" />
            No active disruptions
          </div>
        ) : (
          disruptions.map((d) => (
            <DisruptionItem key={d.id} disruption={d} />
          ))
        )}
      </div>

      <div className="mt-4 text-xs text-gray-400">
        Data refreshed every 30 seconds via SIRI-SX
      </div>
    </div>
  );
}
