/**
 * Tests for SearchBar component
 *
 * Tests search input, debouncing, mode toggle, and autocomplete.
 * Following TDD methodology - these tests will fail until implementation is complete.
 */

import { describe, it, expect, beforeEach, vi } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { SearchBar } from '../Search/SearchBar';

describe('SearchBar', () => {
  const mockOnSearch = vi.fn();
  const mockOnModeChange = vi.fn();

  beforeEach(() => {
    mockOnSearch.mockClear();
    mockOnModeChange.mockClear();
  });

  it('renders search input', () => {
    render(<SearchBar onSearch={mockOnSearch} />);

    const input = screen.getByPlaceholderText(/search/i);
    expect(input).toBeInTheDocument();
  });

  it('renders mode toggle button', () => {
    render(<SearchBar onSearch={mockOnSearch} onModeChange={mockOnModeChange} />);

    const modeButton = screen.getByRole('button', { name: /mode|semantic|text/i });
    expect(modeButton).toBeInTheDocument();
  });

  it('fires search after debounce delay', async () => {
    vi.useFakeTimers();

    render(<SearchBar onSearch={mockOnSearch} debounceMs={300} />);

    const input = screen.getByPlaceholderText(/search/i);

    // Type search query
    await userEvent.type(input, 'Machine Learning');

    // Should not search immediately
    expect(mockOnSearch).not.toHaveBeenCalled();

    // Fast-forward time past debounce delay
    vi.advanceTimersByTime(300);

    // Should search after debounce
    await waitFor(() => {
      expect(mockOnSearch).toHaveBeenCalledWith('Machine Learning');
    });

    vi.useRealTimers();
  });

  it('cancels pending search on new input', async () => {
    vi.useFakeTimers();

    render(<SearchBar onSearch={mockOnSearch} debounceMs={300} />);

    const input = screen.getByPlaceholderText(/search/i);

    // Type first query
    await userEvent.type(input, 'Machine');
    vi.advanceTimersByTime(100);

    // Type more before debounce completes
    await userEvent.type(input, ' Learning');

    // Fast-forward past original debounce
    vi.advanceTimersByTime(300);

    // Should only search once with final query
    expect(mockOnSearch).toHaveBeenCalledTimes(1);
    expect(mockOnSearch).toHaveBeenCalledWith('Machine Learning');

    vi.useRealTimers();
  });

  it('toggles between text and semantic mode', async () => {
    render(<SearchBar onSearch={mockOnSearch} onModeChange={mockOnModeChange} />);

    const modeButton = screen.getByRole('button', { name: /mode|semantic|text/i });

    // Click to toggle mode
    await userEvent.click(modeButton);

    expect(mockOnModeChange).toHaveBeenCalledTimes(1);

    // Click again to toggle back
    await userEvent.click(modeButton);

    expect(mockOnModeChange).toHaveBeenCalledTimes(2);
  });

  it('displays mode indicator', () => {
    const { rerender } = render(<SearchBar onSearch={mockOnSearch} mode="text" />);

    expect(screen.getByText(/text/i)).toBeInTheDocument();

    rerender(<SearchBar onSearch={mockOnSearch} mode="semantic" />);

    expect(screen.getByText(/semantic/i)).toBeInTheDocument();
  });

  it('shows autocomplete dropdown when typing', async () => {
    const mockSuggestions = [
      { title: 'Machine Learning', category: 'Computer Science' },
      { title: 'Mathematics', category: 'Mathematics' },
    ];

    render(<SearchBar onSearch={mockOnSearch} suggestions={mockSuggestions} />);

    const input = screen.getByPlaceholderText(/search/i);

    // Type to trigger suggestions
    await userEvent.type(input, 'Ma');

    // Suggestions should appear
    await waitFor(() => {
      expect(screen.getByText('Machine Learning')).toBeInTheDocument();
      expect(screen.getByText('Mathematics')).toBeInTheDocument();
    });
  });

  it('hides autocomplete when no suggestions', () => {
    render(<SearchBar onSearch={mockOnSearch} suggestions={[]} />);

    // Dropdown should not be visible
    expect(screen.queryByRole('listbox')).not.toBeInTheDocument();
  });

  it('selects suggestion on click', async () => {
    const mockSuggestions = [
      { title: 'Machine Learning', category: 'Computer Science' },
    ];

    render(<SearchBar onSearch={mockOnSearch} suggestions={mockSuggestions} />);

    const suggestion = screen.getByText('Machine Learning');

    // Click suggestion
    await userEvent.click(suggestion);

    // Should trigger search with selected title
    expect(mockOnSearch).toHaveBeenCalledWith('Machine Learning');
  });

  it('navigates suggestions with keyboard', async () => {
    const mockSuggestions = [
      { title: 'Machine Learning', category: 'Computer Science' },
      { title: 'Mathematics', category: 'Mathematics' },
    ];

    render(<SearchBar onSearch={mockOnSearch} suggestions={mockSuggestions} />);

    const input = screen.getByPlaceholderText(/search/i);

    // Focus input
    input.focus();

    // Press down arrow
    fireEvent.keyDown(input, { key: 'ArrowDown' });

    // First suggestion should be highlighted
    // (implementation detail - test structure)
    expect(input).toHaveFocus();

    // Press Enter to select
    fireEvent.keyDown(input, { key: 'Enter' });

    // Should trigger search
    expect(mockOnSearch).toHaveBeenCalled();
  });

  it('clears input when clear button clicked', async () => {
    render(<SearchBar onSearch={mockOnSearch} />);

    const input = screen.getByPlaceholderText(/search/i) as HTMLInputElement;

    // Type query
    await userEvent.type(input, 'Machine Learning');

    expect(input.value).toBe('Machine Learning');

    // Click clear button
    const clearButton = screen.getByRole('button', { name: /clear/i });
    await userEvent.click(clearButton);

    // Input should be empty
    expect(input.value).toBe('');
  });

  it('submits search on Enter key', async () => {
    render(<SearchBar onSearch={mockOnSearch} />);

    const input = screen.getByPlaceholderText(/search/i);

    // Type query
    await userEvent.type(input, 'Machine Learning');

    // Press Enter
    fireEvent.keyDown(input, { key: 'Enter' });

    expect(mockOnSearch).toHaveBeenCalledWith('Machine Learning');
  });

  it('does not search with empty query', async () => {
    render(<SearchBar onSearch={mockOnSearch} />);

    const input = screen.getByPlaceholderText(/search/i);

    // Press Enter without typing
    fireEvent.keyDown(input, { key: 'Enter' });

    expect(mockOnSearch).not.toHaveBeenCalled();
  });

  it('shows loading indicator during search', () => {
    render(<SearchBar onSearch={mockOnSearch} isLoading={true} />);

    const loadingIndicator = screen.getByRole('status');
    expect(loadingIndicator).toBeInTheDocument();
  });

  it('disables input during loading', () => {
    render(<SearchBar onSearch={mockOnSearch} isLoading={true} />);

    const input = screen.getByPlaceholderText(/search/i);
    expect(input).toBeDisabled();
  });

  it('focuses input on mount', () => {
    render(<SearchBar onSearch={mockOnSearch} autoFocus={true} />);

    const input = screen.getByPlaceholderText(/search/i);
    expect(input).toHaveFocus();
  });

  it('displays error message', () => {
    const errorMessage = 'Search failed';

    render(<SearchBar onSearch={mockOnSearch} error={errorMessage} />);

    expect(screen.getByText(errorMessage)).toBeInTheDocument();
  });

  it('clears error on new input', async () => {
    const errorMessage = 'Search failed';

    const { rerender } = render(<SearchBar onSearch={mockOnSearch} error={errorMessage} />);

    expect(screen.getByText(errorMessage)).toBeInTheDocument();

    const input = screen.getByPlaceholderText(/search/i);

    // Type new query
    await userEvent.type(input, 'New query');

    // Error should be cleared (via parent component)
    rerender(<SearchBar onSearch={mockOnSearch} error={null} />);

    expect(screen.queryByText(errorMessage)).not.toBeInTheDocument();
  });
});
