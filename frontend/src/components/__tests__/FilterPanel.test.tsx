/**
 * Tests for FilterPanel component
 *
 * Tests category filtering, depth slider, and filter application.
 * Following TDD methodology - these tests will fail until implementation is complete.
 */

import { describe, it, expect, beforeEach, vi } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { FilterPanel } from '../Sidebar/FilterPanel';

describe('FilterPanel', () => {
  const mockCategories = ['Computer Science', 'Physics', 'Mathematics', 'Biology'];

  const mockOnFilterChange = vi.fn();

  beforeEach(() => {
    mockOnFilterChange.mockClear();
  });

  it('renders filter panel', () => {
    render(<FilterPanel categories={mockCategories} onFilterChange={mockOnFilterChange} />);

    expect(screen.getByText(/filter/i)).toBeInTheDocument();
  });

  it('displays category checkboxes', () => {
    render(<FilterPanel categories={mockCategories} onFilterChange={mockOnFilterChange} />);

    mockCategories.forEach((category) => {
      expect(screen.getByLabelText(category)).toBeInTheDocument();
    });
  });

  it('selects category on checkbox click', async () => {
    render(<FilterPanel categories={mockCategories} onFilterChange={mockOnFilterChange} />);

    const checkbox = screen.getByLabelText('Computer Science');

    await userEvent.click(checkbox);

    expect(mockOnFilterChange).toHaveBeenCalledWith(
      expect.objectContaining({
        selectedCategories: ['Computer Science'],
      })
    );
  });

  it('deselects category on second click', async () => {
    render(
      <FilterPanel
        categories={mockCategories}
        onFilterChange={mockOnFilterChange}
        selectedCategories={['Computer Science']}
      />
    );

    const checkbox = screen.getByLabelText('Computer Science');

    await userEvent.click(checkbox);

    expect(mockOnFilterChange).toHaveBeenCalledWith(
      expect.objectContaining({
        selectedCategories: [],
      })
    );
  });

  it('supports multiple category selection', async () => {
    render(<FilterPanel categories={mockCategories} onFilterChange={mockOnFilterChange} />);

    const checkbox1 = screen.getByLabelText('Computer Science');
    const checkbox2 = screen.getByLabelText('Physics');

    await userEvent.click(checkbox1);
    await userEvent.click(checkbox2);

    expect(mockOnFilterChange).toHaveBeenLastCalledWith(
      expect.objectContaining({
        selectedCategories: expect.arrayContaining(['Computer Science', 'Physics']),
      })
    );
  });

  it('displays depth slider', () => {
    render(<FilterPanel categories={mockCategories} onFilterChange={mockOnFilterChange} />);

    const slider = screen.getByRole('slider', { name: /depth/i });
    expect(slider).toBeInTheDocument();
  });

  it('updates depth on slider change', async () => {
    render(<FilterPanel categories={mockCategories} onFilterChange={mockOnFilterChange} />);

    const slider = screen.getByRole('slider', { name: /depth/i });

    fireEvent.change(slider, { target: { value: '2' } });

    expect(mockOnFilterChange).toHaveBeenCalledWith(
      expect.objectContaining({
        depth: 2,
      })
    );
  });

  it('validates depth range (1-3)', () => {
    render(<FilterPanel categories={mockCategories} onFilterChange={mockOnFilterChange} />);

    const slider = screen.getByRole('slider', { name: /depth/i }) as HTMLInputElement;

    expect(slider).toHaveAttribute('min', '1');
    expect(slider).toHaveAttribute('max', '3');
  });

  it('displays current depth value', () => {
    render(
      <FilterPanel
        categories={mockCategories}
        onFilterChange={mockOnFilterChange}
        depth={2}
      />
    );

    expect(screen.getByText('2')).toBeInTheDocument();
  });

  it('applies filters on button click', async () => {
    render(<FilterPanel categories={mockCategories} onFilterChange={mockOnFilterChange} />);

    const applyButton = screen.getByRole('button', { name: /apply/i });

    await userEvent.click(applyButton);

    expect(mockOnFilterChange).toHaveBeenCalled();
  });

  it('resets filters on reset button click', async () => {
    render(
      <FilterPanel
        categories={mockCategories}
        onFilterChange={mockOnFilterChange}
        selectedCategories={['Computer Science']}
        depth={2}
      />
    );

    const resetButton = screen.getByRole('button', { name: /reset|clear/i });

    await userEvent.click(resetButton);

    expect(mockOnFilterChange).toHaveBeenCalledWith({
      selectedCategories: [],
      depth: 2, // or default value
    });
  });

  it('shows selected category count', () => {
    render(
      <FilterPanel
        categories={mockCategories}
        onFilterChange={mockOnFilterChange}
        selectedCategories={['Computer Science', 'Physics']}
      />
    );

    expect(screen.getByText(/2.*selected/i)).toBeInTheDocument();
  });

  it('displays "Select All" checkbox', () => {
    render(<FilterPanel categories={mockCategories} onFilterChange={mockOnFilterChange} />);

    const selectAllCheckbox = screen.getByLabelText(/select all/i);
    expect(selectAllCheckbox).toBeInTheDocument();
  });

  it('selects all categories on "Select All" click', async () => {
    render(<FilterPanel categories={mockCategories} onFilterChange={mockOnFilterChange} />);

    const selectAllCheckbox = screen.getByLabelText(/select all/i);

    await userEvent.click(selectAllCheckbox);

    expect(mockOnFilterChange).toHaveBeenCalledWith(
      expect.objectContaining({
        selectedCategories: mockCategories,
      })
    );
  });

  it('deselects all categories when "Select All" clicked with all selected', async () => {
    render(
      <FilterPanel
        categories={mockCategories}
        onFilterChange={mockOnFilterChange}
        selectedCategories={mockCategories}
      />
    );

    const selectAllCheckbox = screen.getByLabelText(/select all/i);

    await userEvent.click(selectAllCheckbox);

    expect(mockOnFilterChange).toHaveBeenCalledWith(
      expect.objectContaining({
        selectedCategories: [],
      })
    );
  });

  it('shows indeterminate state for "Select All" when some selected', () => {
    render(
      <FilterPanel
        categories={mockCategories}
        onFilterChange={mockOnFilterChange}
        selectedCategories={['Computer Science']}
      />
    );

    const selectAllCheckbox = screen.getByLabelText(/select all/i) as HTMLInputElement;

    // Should be in indeterminate state
    expect(selectAllCheckbox.indeterminate).toBe(true);
  });

  it('collapses/expands category section', async () => {
    render(<FilterPanel categories={mockCategories} onFilterChange={mockOnFilterChange} />);

    const expandButton = screen.getByRole('button', { name: /categories|expand|collapse/i });

    await userEvent.click(expandButton);

    // Categories should be hidden
    const checkbox = screen.queryByLabelText('Computer Science');
    expect(checkbox).not.toBeVisible();
  });

  it('displays category with article count', () => {
    const categoriesWithCounts = [
      { name: 'Computer Science', count: 1234 },
      { name: 'Physics', count: 892 },
    ];

    render(
      <FilterPanel
        categories={categoriesWithCounts}
        onFilterChange={mockOnFilterChange}
      />
    );

    expect(screen.getByText(/1234/)).toBeInTheDocument();
    expect(screen.getByText(/892/)).toBeInTheDocument();
  });

  it('disables apply button when no changes', () => {
    render(<FilterPanel categories={mockCategories} onFilterChange={mockOnFilterChange} />);

    const applyButton = screen.getByRole('button', { name: /apply/i });

    expect(applyButton).toBeDisabled();
  });

  it('enables apply button when filters changed', async () => {
    render(<FilterPanel categories={mockCategories} onFilterChange={mockOnFilterChange} />);

    const checkbox = screen.getByLabelText('Computer Science');

    await userEvent.click(checkbox);

    const applyButton = screen.getByRole('button', { name: /apply/i });

    expect(applyButton).toBeEnabled();
  });

  it('triggers refetch when filters applied', async () => {
    const mockOnApply = vi.fn();

    render(
      <FilterPanel
        categories={mockCategories}
        onFilterChange={mockOnFilterChange}
        onApply={mockOnApply}
      />
    );

    const checkbox = screen.getByLabelText('Computer Science');
    await userEvent.click(checkbox);

    const applyButton = screen.getByRole('button', { name: /apply/i });
    await userEvent.click(applyButton);

    expect(mockOnApply).toHaveBeenCalled();
  });
});
