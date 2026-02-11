/**
 * FilterPanel Component
 *
 * Category filtering, depth slider, and filter application.
 */

import React, { useState, useEffect, useRef } from 'react';

interface FilterPanelProps {
  categories: string[] | Array<{ name: string; count: number }>;
  selectedCategories?: string[];
  depth?: number;
  onFilterChange: (filters: {
    selectedCategories?: string[];
    depth?: number;
  }) => void;
  onApply?: () => void;
}

export const FilterPanel: React.FC<FilterPanelProps> = ({
  categories,
  selectedCategories = [],
  depth = 2,
  onFilterChange,
  onApply,
}) => {
  const [localSelectedCategories, setLocalSelectedCategories] =
    useState<string[]>(selectedCategories);
  const [localDepth, setLocalDepth] = useState(depth);
  const [isExpanded, setIsExpanded] = useState(true);
  const [hasChanges, setHasChanges] = useState(false);
  const selectAllCheckboxRef = useRef<HTMLInputElement>(null);

  // Convert categories to uniform format
  const categoryList = categories.map((cat) =>
    typeof cat === 'string' ? cat : cat.name
  );

  const categoriesWithCounts = categories.map((cat) =>
    typeof cat === 'string' ? { name: cat, count: undefined } : cat
  );

  // Update indeterminate state for "Select All" checkbox
  useEffect(() => {
    if (selectAllCheckboxRef.current) {
      const allSelected = localSelectedCategories.length === categoryList.length;
      const noneSelected = localSelectedCategories.length === 0;

      selectAllCheckboxRef.current.indeterminate = !allSelected && !noneSelected;
    }
  }, [localSelectedCategories, categoryList.length]);

  // Check for changes
  useEffect(() => {
    const categoriesChanged =
      JSON.stringify([...localSelectedCategories].sort()) !==
      JSON.stringify([...selectedCategories].sort());
    const depthChanged = localDepth !== depth;

    setHasChanges(categoriesChanged || depthChanged);
  }, [localSelectedCategories, localDepth, selectedCategories, depth]);

  const handleCategoryToggle = (category: string) => {
    const newSelected = localSelectedCategories.includes(category)
      ? localSelectedCategories.filter((c) => c !== category)
      : [...localSelectedCategories, category];

    setLocalSelectedCategories(newSelected);
    onFilterChange({
      selectedCategories: newSelected,
      depth: localDepth,
    });
  };

  const handleSelectAll = () => {
    const newSelected =
      localSelectedCategories.length === categoryList.length ? [] : categoryList;

    setLocalSelectedCategories(newSelected);
    onFilterChange({
      selectedCategories: newSelected,
      depth: localDepth,
    });
  };

  const handleDepthChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const newDepth = Number(e.target.value);
    setLocalDepth(newDepth);
    onFilterChange({
      selectedCategories: localSelectedCategories,
      depth: newDepth,
    });
  };

  const handleReset = () => {
    setLocalSelectedCategories([]);
    setLocalDepth(2);
    onFilterChange({
      selectedCategories: [],
      depth: 2,
    });
  };

  const handleApply = () => {
    if (onApply) {
      onApply();
    }
  };

  return (
    <div className="p-4 bg-white border-t border-gray-200">
      <div className="flex items-center justify-between mb-4">
        <h3 className="font-semibold">Filters</h3>
        <button
          type="button"
          onClick={() => setIsExpanded(!isExpanded)}
          aria-label={isExpanded ? 'Collapse' : 'Expand'}
          className="text-gray-500 hover:text-gray-700"
        >
          {isExpanded ? '−' : '+'}
        </button>
      </div>

      {isExpanded && (
        <div className="space-y-6">
          {/* Categories */}
          <div>
            <div className="flex items-center justify-between mb-2">
              <label className="font-medium text-sm">Categories</label>
              {localSelectedCategories.length > 0 && (
                <span className="text-xs text-gray-500">
                  {localSelectedCategories.length} selected
                </span>
              )}
            </div>

            {/* Select All */}
            <div className="mb-2">
              <label className="flex items-center space-x-2 cursor-pointer">
                <input
                  ref={selectAllCheckboxRef}
                  type="checkbox"
                  checked={localSelectedCategories.length === categoryList.length}
                  onChange={handleSelectAll}
                  className="w-4 h-4 rounded border-gray-300 text-blue-600 focus:ring-blue-500"
                />
                <span className="text-sm font-medium">Select All</span>
              </label>
            </div>

            {/* Category list */}
            <div className="space-y-2 max-h-64 overflow-y-auto">
              {categoriesWithCounts.map(({ name, count }) => (
                <label
                  key={name}
                  className="flex items-center space-x-2 cursor-pointer"
                >
                  <input
                    type="checkbox"
                    checked={localSelectedCategories.includes(name)}
                    onChange={() => handleCategoryToggle(name)}
                    className="w-4 h-4 rounded border-gray-300 text-blue-600 focus:ring-blue-500"
                  />
                  <span className="text-sm flex-1">{name}</span>
                  {count !== undefined && (
                    <span className="text-xs text-gray-500">{count}</span>
                  )}
                </label>
              ))}
            </div>
          </div>

          {/* Depth slider */}
          <div>
            <div className="flex items-center justify-between mb-2">
              <label htmlFor="depth-slider" className="font-medium text-sm">
                Depth
              </label>
              <span className="text-sm text-gray-600" data-testid="depth-value">{localDepth}</span>
            </div>

            <input
              id="depth-slider"
              type="range"
              min="1"
              max="3"
              value={localDepth}
              onChange={handleDepthChange}
              aria-label="Depth"
              className="w-full h-2 bg-gray-200 rounded-lg appearance-none cursor-pointer"
            />

            <div className="flex justify-between text-xs text-gray-500 mt-1">
              <span>1</span>
              <span>2</span>
              <span>3</span>
            </div>
          </div>

          {/* Action buttons */}
          <div className="flex gap-2">
            <button
              type="button"
              onClick={handleApply}
              disabled={!hasChanges}
              aria-label="Apply filters"
              className="flex-1 px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:bg-gray-300 disabled:cursor-not-allowed transition-colors"
            >
              Apply
            </button>

            <button
              type="button"
              onClick={handleReset}
              aria-label="Reset filters"
              className="px-4 py-2 border border-gray-300 rounded-lg hover:bg-gray-50 transition-colors"
            >
              Reset
            </button>
          </div>
        </div>
      )}
    </div>
  );
};
