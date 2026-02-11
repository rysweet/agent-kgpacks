/**
 * GraphCanvas Component
 *
 * D3.js force-directed graph visualization with zoom, pan, and interaction.
 * Simulation lifecycle is decoupled from selection state to avoid rebuilds
 * on every click. D3 operates on deep-cloned data to prevent mutation of
 * React/Zustand store state.
 */

import React, { useCallback, useEffect, useRef } from 'react';
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
  const simulationRef = useRef<d3.Simulation<GraphNode, GraphEdge> | null>(
    null
  );
  // Keep a stable reference to the latest onNodeClick so the simulation
  // effect closure always invokes the current callback without needing
  // onNodeClick in its dependency array.
  const onNodeClickRef = useRef(onNodeClick);
  onNodeClickRef.current = onNodeClick;

  // Drag behavior factory -- returned handlers mutate the simulation via
  // simulationRef so they stay valid across re-renders.
  const makeDrag = useCallback(() => {
    function dragStarted(
      event: d3.D3DragEvent<SVGCircleElement, GraphNode, GraphNode>,
      d: GraphNode
    ) {
      if (!event.active) simulationRef.current?.alphaTarget(0.3).restart();
      d.fx = d.x;
      d.fy = d.y;
    }

    function dragged(
      event: d3.D3DragEvent<SVGCircleElement, GraphNode, GraphNode>,
      d: GraphNode
    ) {
      d.fx = event.x;
      d.fy = event.y;
    }

    function dragEnded(
      event: d3.D3DragEvent<SVGCircleElement, GraphNode, GraphNode>,
      d: GraphNode
    ) {
      if (!event.active) simulationRef.current?.alphaTarget(0);
      d.fx = null;
      d.fy = null;
    }

    return d3
      .drag<SVGCircleElement, GraphNode>()
      .on('start', dragStarted)
      .on('drag', dragged)
      .on('end', dragEnded);
  }, []);

  // --- Simulation effect: only rebuilds when the graph data changes ---
  useEffect(() => {
    if (!svgRef.current || nodes.length === 0) return;

    // Deep-clone data so D3 mutations (x, y, vx, vy) never touch store state
    const simNodes: GraphNode[] = structuredClone(nodes);
    const simEdges: GraphEdge[] = structuredClone(edges);

    const svg = d3.select(svgRef.current);
    const width = svgRef.current.clientWidth;
    const height = svgRef.current.clientHeight;

    // Clear previous content
    svg.selectAll('*').remove();

    // Create container for zoom
    const g = svg.append('g').attr('class', 'graph-layer');

    // Create force simulation on cloned data
    const simulation = d3
      .forceSimulation(simNodes)
      .force(
        'link',
        d3
          .forceLink<GraphNode, GraphEdge>(simEdges)
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
      .data(simEdges)
      .join('line')
      .attr('class', 'edge')
      .attr('stroke', '#999')
      .attr('stroke-opacity', 0.6)
      .attr('stroke-width', (d) => Math.sqrt(d.weight) * 2);

    // Draw nodes
    const nodeElements = g
      .selectAll<SVGCircleElement, GraphNode>('.node')
      .data(simNodes, (d) => d.id)
      .join('circle')
      .attr('class', 'node')
      .attr('r', (d) => 5 + d.links_count * 0.5)
      .attr('fill', (d) => categoryColors(d.category))
      .attr('stroke', '#fff')
      .attr('stroke-width', 1.5)
      .style('cursor', 'pointer')
      .on('click', (_event, d) => {
        onNodeClickRef.current?.(d.id);
      })
      .call(makeDrag());

    // Draw labels
    const labelElements = g
      .selectAll<SVGTextElement, GraphNode>('.node-label')
      .data(simNodes, (d) => d.id)
      .join('text')
      .attr('class', 'node-label')
      .text((d) => d.title)
      .attr('font-size', 10)
      .attr('dx', (d) => 8 + d.links_count * 0.5)
      .attr('dy', 3)
      .attr('fill', '#333')
      .attr('pointer-events', 'none');

    // Update positions on simulation tick
    simulation.on('tick', () => {
      edgeElements
        .attr('x1', (d) => (d.source as GraphNode).x!)
        .attr('y1', (d) => (d.source as GraphNode).y!)
        .attr('x2', (d) => (d.target as GraphNode).x!)
        .attr('y2', (d) => (d.target as GraphNode).y!);

      nodeElements.attr('cx', (d) => d.x!).attr('cy', (d) => d.y!);

      labelElements.attr('x', (d) => d.x!).attr('y', (d) => d.y!);
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
  }, [nodes, edges, makeDrag]);

  // --- Selection effect: updates visual highlight without rebuilding ---
  useEffect(() => {
    if (!svgRef.current) return;

    const svg = d3.select(svgRef.current);

    svg
      .selectAll<SVGCircleElement, GraphNode>('.node')
      .attr('stroke', (d) => (d.id === selectedNodeId ? '#000' : '#fff'))
      .attr('stroke-width', (d) => (d.id === selectedNodeId ? 3 : 1.5));
  }, [selectedNodeId]);

  return (
    <svg
      ref={svgRef}
      className="w-full h-full"
      style={{ background: '#f9fafb' }}
    />
  );
};
