/**
 * SearchBar Component
 *
 * Search input with debouncing, mode toggle, and autocomplete.
 */

import React, { useState, useEffect, useCallback, useRef } from 'react';

interface SearchBarProps {
  onSearch: (query: string) => void;
  onModeChange?: (mode: 'text' | 'semantic') => void;
  mode?: 'text' | 'semantic';
  suggestions?: Array<{ title: string; category: string }>;
  debounceMs?: number;
  autoFocus?: boolean;
  isLoading?: boolean;
  error?: string | null;
}

export const SearchBar: React.FC<SearchBarProps> = ({
  onSearch,
  onModeChange,
  mode = 'text',
  suggestions = [],
  debounceMs = 300,
  autoFocus = false,
  isLoading = false,
  error = null,
}) => {
  const [query, setQuery] = useState('');
  const [showSuggestions, setShowSuggestions] = useState(false);
  const [selectedIndex, setSelectedIndex] = useState(-1);
  const inputRef = useRef<HTMLInputElement>(null);
  const timeoutRef = useRef<NodeJS.Timeout | null>(null);

  // Auto-focus on mount
  useEffect(() => {
    if (autoFocus && inputRef.current) {
      inputRef.current.focus();
    }
  }, [autoFocus]);

  // Debounced search
  const handleInputChange = useCallback(
    (value: string) => {
      setQuery(value);

      // Cancel pending search
      if (timeoutRef.current) {
        clearTimeout(timeoutRef.current);
      }

      // Schedule new search
      if (value.length >= 2) {
        timeoutRef.current = setTimeout(() => {
          onSearch(value);
        }, debounceMs);
      }

      // Show suggestions when typing
      setShowSuggestions(value.length >= 2 && suggestions.length > 0);
    },
    [onSearch, debounceMs, suggestions.length]
  );

  // Clear input
  const handleClear = useCallback(() => {
    setQuery('');
    setShowSuggestions(false);
    if (timeoutRef.current) {
      clearTimeout(timeoutRef.current);
    }
  }, []);

  // Submit search immediately
  const handleSubmit = useCallback(
    (e: React.FormEvent) => {
      e.preventDefault();
      if (query.trim()) {
        if (timeoutRef.current) {
          clearTimeout(timeoutRef.current);
        }
        onSearch(query);
        setShowSuggestions(false);
      }
    },
    [query, onSearch]
  );

  // Handle keyboard navigation
  const handleKeyDown = useCallback(
    (e: React.KeyboardEvent) => {
      if (e.key === 'ArrowDown') {
        e.preventDefault();
        setSelectedIndex((prev) =>
          prev < suggestions.length - 1 ? prev + 1 : prev
        );
      } else if (e.key === 'ArrowUp') {
        e.preventDefault();
        setSelectedIndex((prev) => (prev > 0 ? prev - 1 : -1));
      } else if (e.key === 'Enter' && selectedIndex >= 0) {
        e.preventDefault();
        const selected = suggestions[selectedIndex];
        setQuery(selected.title);
        onSearch(selected.title);
        setShowSuggestions(false);
      } else if (e.key === 'Escape') {
        setShowSuggestions(false);
      }
    },
    [suggestions, selectedIndex, onSearch]
  );

  // Select suggestion
  const handleSelectSuggestion = useCallback(
    (suggestion: { title: string; category: string }) => {
      setQuery(suggestion.title);
      onSearch(suggestion.title);
      setShowSuggestions(false);
    },
    [onSearch]
  );

  // Toggle mode
  const handleModeToggle = useCallback(() => {
    if (onModeChange) {
      onModeChange(mode === 'text' ? 'semantic' : 'text');
    }
  }, [mode, onModeChange]);

  // Show suggestions when suggestions prop changes
  useEffect(() => {
    setShowSuggestions(suggestions.length > 0);
  }, [suggestions]);

  return (
    <div className="relative w-full">
      <form onSubmit={handleSubmit} className="flex gap-2">
        <div className="relative flex-1">
          <input
            ref={inputRef}
            type="text"
            value={query}
            onChange={(e) => handleInputChange(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder="Search articles..."
            disabled={isLoading}
            className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 disabled:bg-gray-100 disabled:cursor-not-allowed"
          />

          {isLoading && (
            <div
              role="status"
              className="absolute right-3 top-1/2 transform -translate-y-1/2"
            >
              <div className="animate-spin h-5 w-5 border-2 border-blue-500 border-t-transparent rounded-full" />
            </div>
          )}

          {query && !isLoading && (
            <button
              type="button"
              onClick={handleClear}
              aria-label="Clear"
              className="absolute right-3 top-1/2 transform -translate-y-1/2 text-gray-400 hover:text-gray-600"
            >
              ×
            </button>
          )}
        </div>

        {onModeChange ? (
          <button
            type="button"
            onClick={handleModeToggle}
            aria-label={`Mode: ${mode}`}
            className="px-4 py-2 border border-gray-300 rounded-lg bg-white hover:bg-gray-50"
          >
            <span className="capitalize">{mode}</span>
          </button>
        ) : mode ? (
          <div className="px-4 py-2 text-sm text-gray-600">
            <span className="capitalize">{mode}</span>
          </div>
        ) : null}
      </form>

      {/* Autocomplete dropdown */}
      {showSuggestions && suggestions.length > 0 && (
        <ul
          role="listbox"
          className="absolute z-10 w-full mt-1 bg-white border border-gray-300 rounded-lg shadow-lg max-h-64 overflow-y-auto"
        >
          {suggestions.map((suggestion, index) => (
            <li
              key={suggestion.title}
              role="option"
              aria-selected={index === selectedIndex}
              onClick={() => handleSelectSuggestion(suggestion)}
              className={`px-4 py-2 cursor-pointer ${
                index === selectedIndex ? 'bg-blue-100' : 'hover:bg-gray-100'
              }`}
            >
              <div className="font-medium">{suggestion.title}</div>
              <div className="text-sm text-gray-500">{suggestion.category}</div>
            </li>
          ))}
        </ul>
      )}

      {/* Error message */}
      {error && (
        <div className="mt-2 text-sm text-red-600" role="alert">
          {error}
        </div>
      )}
    </div>
  );
};
