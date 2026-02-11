/**
 * GraphCanvas Component
 *
 * D3.js force-directed graph visualization with zoom, pan, and interaction.
 */

import React, { useEffect, useRef } from 'react';
import * as d3 from 'd3';
import type { GraphNode, GraphEdge } from '../../types/graph';

interface GraphCanvasProps {
  nodes: GraphNode[];
  edges: GraphEdge[];
  onNodeClick?: (nodeId: string) => void;
  selectedNodeId?: string | null;
}

// Category color scale
const categoryColors = d3.scaleOrdinal(d3.schemeCategory10);

export const GraphCanvas: React.FC<GraphCanvasProps> = ({
  nodes,
  edges,
  onNodeClick,
  selectedNodeId,
}) => {
  const svgRef = useRef<SVGSVGElement>(null);
  const simulationRef = useRef<d3.Simulation<GraphNode, GraphEdge> | null>(null);

  useEffect(() => {
    if (!svgRef.current || nodes.length === 0) return;

    const svg = d3.select(svgRef.current);
    const width = svgRef.current.clientWidth;
    const height = svgRef.current.clientHeight;

    // Clear previous content
    svg.selectAll('*').remove();

    // Create container for zoom
    const g = svg.append('g').attr('class', 'graph-layer');

    // Create force simulation
    const simulation = d3
      .forceSimulation(nodes)
      .force(
        'link',
        d3
          .forceLink<GraphNode, GraphEdge>(edges)
          .id((d) => d.id)
          .distance(100)
      )
      .force('charge', d3.forceManyBody().strength(-300))
      .force('center', d3.forceCenter(width / 2, height / 2))
      .force(
        'collision',
        d3.forceCollide<GraphNode>().radius((d) => 10 + d.links_count * 0.5)
      );

    simulationRef.current = simulation;

    // Draw edges
    const edgeElements = g
      .selectAll<SVGLineElement, GraphEdge>('.edge')
      .data(edges)
      .join('line')
      .attr('class', 'edge')
      .attr('stroke', '#999')
      .attr('stroke-opacity', 0.6)
      .attr('stroke-width', (d) => Math.sqrt(d.weight) * 2);

    // Draw nodes
    const nodeElements = g
      .selectAll<SVGCircleElement, GraphNode>('.node')
      .data(nodes)
      .join('circle')
      .attr('class', 'node')
      .attr('r', (d) => 5 + d.links_count * 0.5)
      .attr('fill', (d) => categoryColors(d.category))
      .attr('stroke', '#fff')
      .attr('stroke-width', 1.5)
      .style('cursor', 'pointer')
      .on('click', (_event, d) => {
        if (onNodeClick) {
          onNodeClick(d.id);
        }
      });

    // Update node appearance based on selection
    if (selectedNodeId) {
      nodeElements
        .attr('stroke', (d) => (d.id === selectedNodeId ? '#000' : '#fff'))
        .attr('stroke-width', (d) => (d.id === selectedNodeId ? 3 : 1.5));
    }

    // Update positions on simulation tick
    simulation.on('tick', () => {
      edgeElements
        .attr('x1', (d) => (d.source as GraphNode).x!)
        .attr('y1', (d) => (d.source as GraphNode).y!)
        .attr('x2', (d) => (d.target as GraphNode).x!)
        .attr('y2', (d) => (d.target as GraphNode).y!);

      nodeElements.attr('cx', (d) => d.x!).attr('cy', (d) => d.y!);
    });

    // Zoom behavior
    const zoom = d3
      .zoom<SVGSVGElement, unknown>()
      .scaleExtent([0.1, 10])
      .on('zoom', (event) => {
        g.attr('transform', event.transform);
      });

    svg.call(zoom);

    // Handle window resize
    const handleResize = () => {
      const newWidth = svgRef.current?.clientWidth || width;
      const newHeight = svgRef.current?.clientHeight || height;
      simulation.force('center', d3.forceCenter(newWidth / 2, newHeight / 2));
      simulation.alpha(0.3).restart();
    };

    window.addEventListener('resize', handleResize);

    return () => {
      simulation.stop();
      window.removeEventListener('resize', handleResize);
    };
  }, [nodes, edges, onNodeClick, selectedNodeId]);

  return (
    <svg
      ref={svgRef}
      className="w-full h-full"
      style={{ background: '#f9fafb' }}
    />
  );
};
