// Location search input component

import { useState, useRef, useEffect } from 'react';
import { MapPin, X, Loader2 } from 'lucide-react';
import type { Location } from '../types';
import { useLocationSearch } from '../hooks';

interface LocationInputProps {
  label: string;
  placeholder: string;
  value: Location | null;
  onChange: (location: Location | null) => void;
}

export function LocationInput({ label, placeholder, value, onChange }: LocationInputProps) {
  const { setQuery, results, loading, clearResults } = useLocationSearch();
  const [isOpen, setIsOpen] = useState(false);
  const [inputValue, setInputValue] = useState('');
  const containerRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (value) {
      setInputValue(value.name);
    }
  }, [value]);

  useEffect(() => {
    function handleClickOutside(event: MouseEvent) {
      if (containerRef.current && !containerRef.current.contains(event.target as Node)) {
        setIsOpen(false);
      }
    }
    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

  const handleInputChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const val = e.target.value;
    setInputValue(val);
    setQuery(val);
    setIsOpen(true);
    if (!val) {
      onChange(null);
    }
  };

  const handleSelect = (location: Location) => {
    onChange(location);
    setInputValue(location.name);
    setIsOpen(false);
    clearResults();
  };

  const handleClear = () => {
    setInputValue('');
    setQuery('');
    onChange(null);
    clearResults();
  };

  return (
    <div ref={containerRef} className="relative">
      <label className="block text-sm font-medium text-gray-700 mb-1">{label}</label>
      <div className="relative">
        <MapPin className="absolute left-3 top-1/2 -translate-y-1/2 w-5 h-5 text-gray-400" />
        <input
          type="text"
          value={inputValue}
          onChange={handleInputChange}
          onFocus={() => setIsOpen(true)}
          placeholder={placeholder}
          className="w-full pl-10 pr-10 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-sbb-red focus:border-transparent outline-none transition"
        />
        {loading && (
          <Loader2 className="absolute right-10 top-1/2 -translate-y-1/2 w-5 h-5 text-gray-400 animate-spin" />
        )}
        {inputValue && (
          <button
            onClick={handleClear}
            className="absolute right-3 top-1/2 -translate-y-1/2 p-1 hover:bg-gray-100 rounded-full"
          >
            <X className="w-4 h-4 text-gray-400" />
          </button>
        )}
      </div>

      {isOpen && results.length > 0 && (
        <div className="absolute z-50 w-full mt-1 bg-white border border-gray-200 rounded-lg shadow-lg max-h-60 overflow-y-auto">
          {results.map((location) => (
            <button
              key={location.id}
              onClick={() => handleSelect(location)}
              className="w-full px-4 py-3 text-left hover:bg-gray-50 flex items-start gap-3 border-b border-gray-100 last:border-0"
            >
              <MapPin className="w-5 h-5 text-sbb-red flex-shrink-0 mt-0.5" />
              <div>
                <div className="font-medium text-gray-900">{location.name}</div>
                {location.locality && (
                  <div className="text-sm text-gray-500">{location.locality}</div>
                )}
              </div>
            </button>
          ))}
        </div>
      )}
    </div>
  );
}
