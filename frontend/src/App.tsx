// Main Application Component

import { useState } from 'react';
import { Train, ArrowRightLeft, Search, Loader2, Calendar, Info } from 'lucide-react';
import { LocationInput, TripCard, DisruptionPanel } from './components';
import { planTrip } from './api/client';
import type { Location, TripSearchResult } from './types';

function App() {
  const [origin, setOrigin] = useState<Location | null>(null);
  const [destination, setDestination] = useState<Location | null>(null);
  const [departureTime, setDepartureTime] = useState<string>('');
  const [searchResult, setSearchResult] = useState<TripSearchResult | null>(null);
  const [selectedTripId, setSelectedTripId] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [showInfo, setShowInfo] = useState(false);

  const handleSwapLocations = () => {
    const temp = origin;
    setOrigin(destination);
    setDestination(temp);
  };

  const handleSearch = async () => {
    if (!origin || !destination) {
      setError('Please select both origin and destination');
      return;
    }

    setLoading(true);
    setError(null);
    setSearchResult(null);
    setSelectedTripId(null);

    try {
      const result = await planTrip({
        origin_id: origin.id,
        origin_name: origin.name,
        destination_id: destination.id,
        destination_name: destination.name,
        departure_time: departureTime || undefined,
        num_results: 5,
        include_predictions: true,
      });

      setSearchResult(result);
      if (result.trips.length > 0) {
        setSelectedTripId(result.trips[0].trip_id);
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Search failed');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen bg-gray-50">
      {/* Header */}
      <header className="bg-sbb-red text-white shadow-lg">
        <div className="max-w-7xl mx-auto px-4 py-4">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-3">
              <Train className="w-8 h-8" />
              <div>
                <h1 className="text-xl font-bold">Swiss Transport Planner</h1>
                <p className="text-sm text-red-100">Real-time updates & delay predictions</p>
              </div>
            </div>
            <button
              onClick={() => setShowInfo(!showInfo)}
              className="p-2 hover:bg-red-700 rounded-lg transition"
            >
              <Info className="w-5 h-5" />
            </button>
          </div>
        </div>
      </header>

      {/* Info Panel */}
      {showInfo && (
        <div className="bg-white border-b border-gray-200 shadow-sm">
          <div className="max-w-7xl mx-auto px-4 py-4">
            <h3 className="font-semibold text-gray-900 mb-2">About This App</h3>
            <div className="grid md:grid-cols-2 gap-4 text-sm text-gray-600">
              <div>
                <h4 className="font-medium text-gray-800">Data Sources</h4>
                <ul className="mt-1 space-y-1">
                  <li>• Route planning: OJP (timetable-only)</li>
                  <li>• Disruptions: SIRI-SX (30s refresh)</li>
                  <li>• Delays: GTFS-RT Trip Updates</li>
                  <li>• Traffic: DATEX II & OCIT-C</li>
                </ul>
              </div>
              <div>
                <h4 className="font-medium text-gray-800">Delay Prediction</h4>
                <ul className="mt-1 space-y-1">
                  <li>• Uses road traffic data for bus/tram</li>
                  <li>• 15-minute prediction horizon</li>
                  <li>• Peak hours: 5:45-7:00, 16:30-18:00</li>
                  <li>• Confidence score based on data quality</li>
                </ul>
              </div>
            </div>
          </div>
        </div>
      )}

      <main className="max-w-7xl mx-auto px-4 py-6">
        <div className="grid lg:grid-cols-3 gap-6">
          {/* Search Panel */}
          <div className="lg:col-span-2">
            <div className="bg-white rounded-xl shadow-sm p-6">
              <h2 className="text-lg font-semibold text-gray-900 mb-4">Plan Your Journey</h2>

              <div className="space-y-4">
                {/* Origin/Destination inputs */}
                <div className="grid md:grid-cols-[1fr,auto,1fr] gap-4 items-end">
                  <LocationInput
                    label="From"
                    placeholder="Enter origin station..."
                    value={origin}
                    onChange={setOrigin}
                  />

                  <button
                    onClick={handleSwapLocations}
                    className="p-3 border border-gray-300 rounded-lg hover:bg-gray-50 transition self-end"
                    title="Swap locations"
                  >
                    <ArrowRightLeft className="w-5 h-5 text-gray-600" />
                  </button>

                  <LocationInput
                    label="To"
                    placeholder="Enter destination station..."
                    value={destination}
                    onChange={setDestination}
                  />
                </div>

                {/* Date/Time picker */}
                <div className="flex items-end gap-4">
                  <div className="flex-1">
                    <label className="block text-sm font-medium text-gray-700 mb-1">
                      Departure Time (optional)
                    </label>
                    <div className="relative">
                      <Calendar className="absolute left-3 top-1/2 -translate-y-1/2 w-5 h-5 text-gray-400" />
                      <input
                        type="datetime-local"
                        value={departureTime}
                        onChange={(e) => setDepartureTime(e.target.value)}
                        className="w-full pl-10 pr-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-sbb-red focus:border-transparent outline-none transition"
                      />
                    </div>
                  </div>

                  <button
                    onClick={handleSearch}
                    disabled={loading || !origin || !destination}
                    className="px-6 py-3 bg-sbb-red text-white font-semibold rounded-lg hover:bg-sbb-red-dark disabled:bg-gray-300 disabled:cursor-not-allowed transition flex items-center gap-2"
                  >
                    {loading ? (
                      <>
                        <Loader2 className="w-5 h-5 animate-spin" />
                        Searching...
                      </>
                    ) : (
                      <>
                        <Search className="w-5 h-5" />
                        Search
                      </>
                    )}
                  </button>
                </div>

                {/* Error message */}
                {error && (
                  <div className="p-4 bg-red-50 text-red-800 rounded-lg">
                    {error}
                  </div>
                )}
              </div>
            </div>

            {/* Search Results */}
            {searchResult && (
              <div className="mt-6 space-y-4">
                <h3 className="text-lg font-semibold text-gray-900">
                  {searchResult.trips.length} Connection{searchResult.trips.length !== 1 ? 's' : ''} Found
                </h3>

                {searchResult.trips.length === 0 ? (
                  <div className="bg-white rounded-xl shadow-sm p-8 text-center text-gray-500">
                    No connections found for this route. Try different times or stations.
                  </div>
                ) : (
                  <div className="space-y-4">
                    {searchResult.trips.map((trip) => (
                      <TripCard
                        key={trip.trip_id}
                        trip={trip}
                        isSelected={selectedTripId === trip.trip_id}
                        onSelect={() => setSelectedTripId(trip.trip_id)}
                      />
                    ))}
                  </div>
                )}
              </div>
            )}
          </div>

          {/* Disruption Panel */}
          <div className="lg:col-span-1">
            <DisruptionPanel />
          </div>
        </div>
      </main>

      {/* Footer */}
      <footer className="bg-gray-800 text-gray-400 py-6 mt-12">
        <div className="max-w-7xl mx-auto px-4 text-center text-sm">
          <p>Data provided by Swiss Open Transport Data (OTD)</p>
          <p className="mt-1">
            OJP • GTFS-RT • SIRI-SX • DATEX II • OCIT-C
          </p>
        </div>
      </footer>
    </div>
  );
}

export default App;
