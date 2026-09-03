import React from 'react';
import {
  Box,
  Card,
  CardContent,
  Typography,
  Chip,
  Button,
  Divider,
  Paper,
  Tooltip,
} from '@mui/material';
import {
  Psychology as AIIcon,
  ContentCopy as CopyIcon,
  VerifiedUser as GroundedIcon,
  Gavel as PolicyIcon,
} from '@mui/icons-material';
import { CaseExplanation } from '../../../types';
import { toast } from 'react-hot-toast';

interface ExplanationPanelProps {
  explanation: CaseExplanation;
}

export const ExplanationPanel: React.FC<ExplanationPanelProps> = ({ explanation }) => {
  const handleCopy = () => {
    const text = `Case Rationale Summary:\n${explanation.summary}\n\nKey Findings:\n${explanation.explanations
      .map((e) => `${e.point_number}. [${e.detector_name}] ${e.sentence}`)
      .join('\n')}`;
    navigator.clipboard.writeText(text);
    toast.success('Explanation summary copied to clipboard');
  };

  return (
    <Card sx={{ mb: 3 }}>
      <CardContent>
        {/* Header */}
        <Box display="flex" justifyContent="space-between" alignItems="center" mb={2}>
          <Box display="flex" alignItems="center" gap={1}>
            <AIIcon color="primary" sx={{ fontSize: 28 }} />
            <Box>
              <Typography variant="h6" fontWeight={700}>
                AI RAG Explanation & Legal Grounding
              </Typography>
              <Typography variant="caption" color="text.secondary">
                Model: RAG Validator Pipeline (Ver {explanation.version})
              </Typography>
            </Box>
          </Box>
          <Box display="flex" alignItems="center" gap={1}>
            <Tooltip title="Percentage of statements mathematically verified against evidence tokens">
              <Chip
                icon={<GroundedIcon />}
                label={`${(explanation.grounding_score * 100).toFixed(1)}% Grounded`}
                color="success"
                sx={{ fontWeight: 700 }}
              />
            </Tooltip>
            <Button
              size="small"
              variant="outlined"
              startIcon={<CopyIcon />}
              onClick={handleCopy}
            >
              Copy Rationale
            </Button>
          </Box>
        </Box>

        {/* Synthesis Summary */}
        <Paper sx={{ p: 2, bgcolor: 'action.hover', borderRadius: 2, mb: 3 }}>
          <Typography variant="subtitle2" color="primary.main" fontWeight={700} gutterBottom>
            EXECUTIVE AUDIT SUMMARY:
          </Typography>
          <Typography variant="body2" sx={{ lineHeight: 1.6 }}>
            {explanation.summary}
          </Typography>
        </Paper>

        <Divider sx={{ my: 2 }} />

        {/* Detailed Points */}
        <Typography variant="subtitle1" fontWeight={700} gutterBottom>
          Structured Findings & Grounded Citations
        </Typography>

        <Box display="flex" flexDirection="column" gap={2} mt={2}>
          {explanation.explanations?.map((point) => (
            <Box
              key={point.point_number}
              sx={{
                p: 2,
                borderRadius: 2,
                border: '1px solid',
                borderColor: 'divider',
                bgcolor: 'background.paper',
              }}
            >
              <Box display="flex" justifyContent="space-between" alignItems="center" mb={1}>
                <Box display="flex" alignItems="center" gap={1}>
                  <Chip
                    label={`#${point.point_number}`}
                    size="small"
                    color="primary"
                    sx={{ fontWeight: 700 }}
                  />
                  <Typography variant="subtitle2" fontWeight={700}>
                    {point.detector_name}
                  </Typography>
                </Box>
                <Chip
                  label={`${(point.confidence * 100).toFixed(0)}% Confidence`}
                  size="small"
                  color={point.confidence > 0.85 ? 'error' : 'warning'}
                />
              </Box>

              <Typography variant="body2" sx={{ my: 1, lineHeight: 1.6 }}>
                {point.sentence}
              </Typography>

              {/* Linked Citations and Policy References */}
              <Box display="flex" flexWrap="wrap" gap={1} mt={1.5} alignItems="center">
                {point.evidence_ids?.map((evId) => (
                  <Chip
                    key={evId}
                    label={`Evidence Ref: ${evId.toUpperCase()}`}
                    size="small"
                    variant="outlined"
                    color="primary"
                  />
                ))}

                {point.policy_references?.map((pol, pIdx) => (
                  <Chip
                    key={pIdx}
                    icon={<PolicyIcon fontSize="small" />}
                    label={pol}
                    size="small"
                    color="secondary"
                    variant="outlined"
                  />
                ))}
              </Box>

              {/* Legal Quote Citation if available */}
              {point.citations?.map((cit, cIdx) => cit.quote && (
                <Paper
                  key={cIdx}
                  sx={{
                    p: 1.5,
                    mt: 1.5,
                    borderLeft: 3,
                    borderColor: 'secondary.main',
                    bgcolor: 'action.hover',
                  }}
                >
                  <Typography variant="caption" color="text.secondary" display="block">
                    Statutory Rule Quote ({cit.policy_clause_id}):
                  </Typography>
                  <Typography variant="caption" fontStyle="italic">
                    "{cit.quote}"
                  </Typography>
                </Paper>
              ))}
            </Box>
          ))}
        </Box>
      </CardContent>
    </Card>
  );
};

export default ExplanationPanel;
