import React, { useState } from 'react';
import {
  Box,
  Typography,
  Paper,
  Chip,
  Grid,
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  Button,
} from '@mui/material';
import { useQuery } from '@tanstack/react-query';
import { Hub as HubIcon, Warning as AlertIcon } from '@mui/icons-material';
import { graphService } from '../../../services/api';
import { GraphNode } from '../../../types';
import LoadingSpinner from '../../common/Loading/LoadingSpinner';

interface VendorGraphProps {
  vendorToken: string;
}

export const VendorGraph: React.FC<VendorGraphProps> = ({ vendorToken }) => {
  const [selectedNode, setSelectedNode] = useState<GraphNode | null>(null);

  const { data: graphData, isLoading } = useQuery({
    queryKey: ['vendor-graph', vendorToken],
    queryFn: () => graphService.getVendorGraph(vendorToken),
  });

  const { data: analysis } = useQuery({
    queryKey: ['vendor-analysis', vendorToken],
    queryFn: () => graphService.analyseVendor(vendorToken),
  });

  if (isLoading || !graphData) {
    return <LoadingSpinner message="Reconstructing vendor corporate relationship graph..." />;
  }

  // Define static coordinates for interactive visual representation
  const nodePositions: Record<string, { x: number; y: number }> = {
    'VK-83921': { x: 300, y: 160 },
    'SHELL-01': { x: 140, y: 80 },
    'SHELL-02': { x: 140, y: 240 },
    'OFFICIAL-01': { x: 460, y: 240 },
    'DEPT-DOT': { x: 460, y: 80 },
    'TX-99412': { x: 300, y: 40 },
    'TX-99413': { x: 300, y: 280 },
  };

  return (
    <Box>
      {/* Analysis Badges */}
      {analysis && (
        <Grid container spacing={2} mb={2}>
          <Grid item xs={12} sm={4}>
            <Paper sx={{ p: 1.5, textAlign: 'center', bgcolor: 'action.hover' }}>
              <Typography variant="caption" color="text.secondary">Shell Company Risk Index</Typography>
              <Typography variant="h6" fontWeight={700} color="error.main">
                {(analysis.shell_risk_index * 100).toFixed(0)}% (Critical)
              </Typography>
            </Paper>
          </Grid>
          <Grid item xs={12} sm={4}>
            <Paper sx={{ p: 1.5, textAlign: 'center', bgcolor: 'action.hover' }}>
              <Typography variant="caption" color="text.secondary">Connected Public Officials</Typography>
              <Typography variant="h6" fontWeight={700} color="warning.main">
                {analysis.connected_officials_count} Identified
              </Typography>
            </Paper>
          </Grid>
          <Grid item xs={12} sm={4}>
            <Paper sx={{ p: 1.5, textAlign: 'center', bgcolor: 'action.hover' }}>
              <Typography variant="caption" color="text.secondary">Network Clustering Coeff</Typography>
              <Typography variant="h6" fontWeight={700} color="info.main">
                {analysis.clustering_coefficient.toFixed(2)}
              </Typography>
            </Paper>
          </Grid>
        </Grid>
      )}

      {/* SVG Network Graph Canvas */}
      <Box
        sx={{
          width: '100%',
          height: 380,
          border: '1px solid',
          borderColor: 'divider',
          borderRadius: 2,
          bgcolor: (theme) => (theme.palette.mode === 'dark' ? '#0F172A' : '#F8FAFC'),
          position: 'relative',
          overflow: 'hidden',
        }}
      >
        <svg width="100%" height="100%" viewBox="0 0 600 320">
          <defs>
            <marker
              id="arrow"
              viewBox="0 0 10 10"
              refX="22"
              refY="5"
              markerWidth="6"
              markerHeight="6"
              orient="auto-start-reverse"
            >
              <path d="M 0 0 L 10 5 L 0 10 z" fill="#94A3B8" />
            </marker>
          </defs>

          {/* Render Edges */}
          {graphData.edges.map((edge) => {
            const src = nodePositions[edge.source] || { x: 300, y: 160 };
            const tgt = nodePositions[edge.target] || { x: 300, y: 160 };
            const midX = (src.x + tgt.x) / 2;
            const midY = (src.y + tgt.y) / 2;

            return (
              <g key={edge.id}>
                <line
                  x1={src.x}
                  y1={src.y}
                  x2={tgt.x}
                  y2={tgt.y}
                  stroke="#94A3B8"
                  strokeWidth={edge.weight || 2}
                  strokeDasharray={edge.type === 'shared_address' ? '4 4' : 'none'}
                  markerEnd="url(#arrow)"
                />
                <text
                  x={midX}
                  y={midY - 4}
                  fill="#64748B"
                  fontSize="9"
                  textAnchor="middle"
                  fontWeight="600"
                >
                  {edge.label}
                </text>
              </g>
            );
          })}

          {/* Render Nodes */}
          {graphData.nodes.map((node) => {
            const pos = nodePositions[node.id] || { x: 300, y: 160 };
            const isSelected = selectedNode?.id === node.id;

            return (
              <g
                key={node.id}
                transform={`translate(${pos.x}, ${pos.y})`}
                onClick={() => setSelectedNode(node)}
                style={{ cursor: 'pointer' }}
              >
                <circle
                  r={node.size || 14}
                  fill={node.color || '#0284C7'}
                  stroke={isSelected ? '#FFFFFF' : '#0F172A'}
                  strokeWidth={isSelected ? 3 : 1.5}
                />
                <text
                  y={22}
                  fill="#334155"
                  fontSize="10"
                  fontWeight="700"
                  textAnchor="middle"
                >
                  {node.label}
                </text>
              </g>
            );
          })}
        </svg>

        {/* Legend */}
        <Box
          sx={{
            position: 'absolute',
            bottom: 12,
            left: 12,
            display: 'flex',
            gap: 1,
            bgcolor: 'background.paper',
            p: 1,
            borderRadius: 1,
            border: '1px solid',
            borderColor: 'divider',
          }}
        >
          <Chip label="Vendor" size="small" sx={{ bgcolor: '#DC2626', color: '#fff', fontSize: '0.65rem' }} />
          <Chip label="Shell Entity" size="small" sx={{ bgcolor: '#F59E0B', color: '#fff', fontSize: '0.65rem' }} />
          <Chip label="Official" size="small" sx={{ bgcolor: '#8B5CF6', color: '#fff', fontSize: '0.65rem' }} />
          <Chip label="Department" size="small" sx={{ bgcolor: '#0284C7', color: '#fff', fontSize: '0.65rem' }} />
        </Box>
      </Box>

      {/* Node Details Dialog */}
      <Dialog
        open={Boolean(selectedNode)}
        onClose={() => setSelectedNode(null)}
        maxWidth="xs"
        fullWidth
      >
        <DialogTitle>
          <Box display="flex" alignItems="center" gap={1}>
            <HubIcon color="primary" />
            <Typography variant="h6">{selectedNode?.label}</Typography>
          </Box>
        </DialogTitle>
        <DialogContent dividers>
          {selectedNode && (
            <Box display="flex" flexDirection="column" gap={1.5}>
              <Typography variant="caption" color="text.secondary">Entity Identifier</Typography>
              <Typography variant="body2" fontFamily="monospace" fontWeight={700}>
                {selectedNode.id}
              </Typography>
              <Typography variant="caption" color="text.secondary">Entity Class</Typography>
              <Chip label={selectedNode.type.toUpperCase()} size="small" color="primary" sx={{ width: 'fit-content' }} />
              <Typography variant="caption" color="text.secondary">Connected Relationships</Typography>
              <Typography variant="body2">
                Flagged in cross-agency corporate registry linkages and public procurement databases.
              </Typography>
            </Box>
          )}
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setSelectedNode(null)}>Close</Button>
        </DialogActions>
      </Dialog>
    </Box>
  );
};

export default VendorGraph;
