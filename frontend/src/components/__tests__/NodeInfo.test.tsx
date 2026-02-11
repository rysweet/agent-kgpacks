/**
 * Tests for NodeInfo component
 *
 * Tests node detail display, article data fetching, and Wikipedia links.
 * Following TDD methodology - these tests will fail until implementation is complete.
 */

import { describe, it, expect, beforeEach, vi } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { NodeInfo } from '../Sidebar/NodeInfo';

// Mock API client
vi.mock('../../services/api', () => ({
  apiClient: {
    get: vi.fn(),
  },
}));

describe('NodeInfo', () => {
  const mockNode = {
    id: 'Machine_Learning',
    title: 'Machine Learning',
    category: 'Computer Science',
    word_count: 5234,
    depth: 0,
    links_count: 42,
  };

  const mockArticleData = {
    title: 'Machine Learning',
    category: 'Computer Science',
    word_count: 5234,
    sections: [
      {
        title: 'Overview',
        content: 'Machine learning is the study of...',
        word_count: 342,
        level: 2,
      },
      {
        title: 'History',
        content: 'The term machine learning was coined...',
        word_count: 456,
        level: 2,
      },
    ],
    links: ['Deep Learning', 'Neural Networks', 'Artificial Intelligence'],
    backlinks: ['Artificial Intelligence', 'Data Science'],
    categories: ['Computer Science', 'Artificial Intelligence', 'Machine Learning'],
    wikipedia_url: 'https://en.wikipedia.org/wiki/Machine_Learning',
    last_updated: '2026-02-10T12:00:00Z',
  };

  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('shows nothing when no node selected', () => {
    const { container } = render(<NodeInfo selectedNode={null} />);

    expect(container).toBeEmptyDOMElement();
  });

  it('displays node metadata', () => {
    render(<NodeInfo selectedNode={mockNode} />);

    expect(screen.getByText('Machine Learning')).toBeInTheDocument();
    expect(screen.getByText('Computer Science')).toBeInTheDocument();
    expect(screen.getByText(/5234/)).toBeInTheDocument(); // word count
    expect(screen.getByText(/42/)).toBeInTheDocument(); // links count
  });

  it('fetches article data when node selected', async () => {
    const { apiClient } = await import('../../services/api');

    (apiClient.get as any).mockResolvedValue({
      data: mockArticleData,
    });

    render(<NodeInfo selectedNode={mockNode} />);

    await waitFor(() => {
      expect(apiClient.get).toHaveBeenCalledWith(
        `/api/v1/articles/${encodeURIComponent('Machine Learning')}`
      );
    });
  });

  it('displays article sections', async () => {
    const { apiClient } = await import('../../services/api');

    (apiClient.get as any).mockResolvedValue({
      data: mockArticleData,
    });

    render(<NodeInfo selectedNode={mockNode} />);

    await waitFor(() => {
      expect(screen.getByText('Overview')).toBeInTheDocument();
      expect(screen.getByText('History')).toBeInTheDocument();
    });
  });

  it('displays section content', async () => {
    const { apiClient } = await import('../../services/api');

    (apiClient.get as any).mockResolvedValue({
      data: mockArticleData,
    });

    render(<NodeInfo selectedNode={mockNode} />);

    await waitFor(() => {
      expect(screen.getByText(/Machine learning is the study of/)).toBeInTheDocument();
    });
  });

  it('displays Wikipedia link', async () => {
    const { apiClient } = await import('../../services/api');

    (apiClient.get as any).mockResolvedValue({
      data: mockArticleData,
    });

    render(<NodeInfo selectedNode={mockNode} />);

    await waitFor(() => {
      const link = screen.getByRole('link', { name: /wikipedia|view article/i });
      expect(link).toHaveAttribute('href', mockArticleData.wikipedia_url);
      expect(link).toHaveAttribute('target', '_blank');
      expect(link).toHaveAttribute('rel', 'noopener noreferrer');
    });
  });

  it('opens Wikipedia link in new tab', async () => {
    const { apiClient } = await import('../../services/api');

    (apiClient.get as any).mockResolvedValue({
      data: mockArticleData,
    });

    render(<NodeInfo selectedNode={mockNode} />);

    await waitFor(() => {
      const link = screen.getByRole('link', { name: /wikipedia|view article/i });
      expect(link).toHaveAttribute('target', '_blank');
    });
  });

  it('shows loading state while fetching', async () => {
    const { apiClient } = await import('../../services/api');

    // Mock slow API response
    (apiClient.get as any).mockImplementation(
      () => new Promise((resolve) => setTimeout(resolve, 1000))
    );

    render(<NodeInfo selectedNode={mockNode} />);

    // Should show loading indicator
    expect(screen.getByRole('status')).toBeInTheDocument();
  });

  it('shows error message on fetch failure', async () => {
    const { apiClient } = await import('../../services/api');

    (apiClient.get as any).mockRejectedValue(new Error('Network error'));

    render(<NodeInfo selectedNode={mockNode} />);

    await waitFor(() => {
      expect(screen.getByText(/error|failed/i)).toBeInTheDocument();
    });
  });

  it('displays linked articles', async () => {
    const { apiClient } = await import('../../services/api');

    (apiClient.get as any).mockResolvedValue({
      data: mockArticleData,
    });

    render(<NodeInfo selectedNode={mockNode} />);

    await waitFor(() => {
      expect(screen.getByText('Deep Learning')).toBeInTheDocument();
      expect(screen.getByText('Neural Networks')).toBeInTheDocument();
      expect(screen.getByText('Artificial Intelligence')).toBeInTheDocument();
    });
  });

  it('displays backlinks', async () => {
    const { apiClient } = await import('../../services/api');

    (apiClient.get as any).mockResolvedValue({
      data: mockArticleData,
    });

    render(<NodeInfo selectedNode={mockNode} />);

    await waitFor(() => {
      expect(screen.getByText('Data Science')).toBeInTheDocument();
    });
  });

  it('refetches data when selected node changes', async () => {
    const { apiClient } = await import('../../services/api');

    (apiClient.get as any).mockResolvedValue({
      data: mockArticleData,
    });

    const { rerender } = render(<NodeInfo selectedNode={mockNode} />);

    await waitFor(() => {
      expect(apiClient.get).toHaveBeenCalledTimes(1);
    });

    const newNode = {
      ...mockNode,
      id: 'Deep_Learning',
      title: 'Deep Learning',
    };

    rerender(<NodeInfo selectedNode={newNode} />);

    await waitFor(() => {
      expect(apiClient.get).toHaveBeenCalledTimes(2);
    });
  });

  it('clears data when node deselected', () => {
    const { rerender } = render(<NodeInfo selectedNode={mockNode} />);

    expect(screen.getByText('Machine Learning')).toBeInTheDocument();

    rerender(<NodeInfo selectedNode={null} />);

    expect(screen.queryByText('Machine Learning')).not.toBeInTheDocument();
  });

  it('displays article categories', async () => {
    const { apiClient } = await import('../../services/api');

    (apiClient.get as any).mockResolvedValue({
      data: mockArticleData,
    });

    render(<NodeInfo selectedNode={mockNode} />);

    await waitFor(() => {
      expect(screen.getByText('Artificial Intelligence')).toBeInTheDocument();
    });
  });

  it('formats last updated date', async () => {
    const { apiClient } = await import('../../services/api');

    (apiClient.get as any).mockResolvedValue({
      data: mockArticleData,
    });

    render(<NodeInfo selectedNode={mockNode} />);

    await waitFor(() => {
      // Should display formatted date
      expect(screen.getByText(/2026|feb|february/i)).toBeInTheDocument();
    });
  });

  it('handles article with no sections', async () => {
    const { apiClient } = await import('../../services/api');

    const dataNoSections = {
      ...mockArticleData,
      sections: [],
    };

    (apiClient.get as any).mockResolvedValue({
      data: dataNoSections,
    });

    render(<NodeInfo selectedNode={mockNode} />);

    await waitFor(() => {
      expect(screen.getByText('Machine Learning')).toBeInTheDocument();
    });

    // Should handle gracefully
    expect(screen.queryByText('Overview')).not.toBeInTheDocument();
  });

  it('handles article with no links', async () => {
    const { apiClient } = await import('../../services/api');

    const dataNoLinks = {
      ...mockArticleData,
      links: [],
      backlinks: [],
    };

    (apiClient.get as any).mockResolvedValue({
      data: dataNoLinks,
    });

    render(<NodeInfo selectedNode={mockNode} />);

    await waitFor(() => {
      expect(screen.getByText('Machine Learning')).toBeInTheDocument();
    });

    // Should handle gracefully
    expect(screen.queryByText('Deep Learning')).not.toBeInTheDocument();
  });
});
