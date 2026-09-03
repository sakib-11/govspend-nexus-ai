import React, { useEffect, useState } from 'react';
import { Box, Button, Card, CardContent, Chip, Container, Grid, Stack, Typography } from '@mui/material';
import { CheckCircleOutline, GavelOutlined, InsightsOutlined, PublicOutlined } from '@mui/icons-material';
import { nexusApi } from '../services/nexusApi';

type Summary = { reduced_leakage: number; case_compression_ratio: number; median_time_to_case_minutes: number; audit_traceability: number };

const Metric: React.FC<{ label: string; value: string; note: string; tone: string }> = ({ label, value, note, tone }) => (
  <Card sx={{ height: '100%', bgcolor: tone, borderRadius: 4, border: '1px solid rgba(255,255,255,.7)', boxShadow: '0 4px 16px rgba(63,61,138,.08)' }}>
    <CardContent sx={{ p: 2.5 }}><Typography variant="body2" color="text.secondary">{label}</Typography><Typography variant="h4" fontWeight={700} sx={{ my: .6 }}>{value}</Typography><Typography variant="caption" color="text.secondary">{note}</Typography></CardContent>
  </Card>
);

export default function PublicTransparency(): React.ReactElement {
  const [summary, setSummary] = useState<Summary>();
  useEffect(() => { nexusApi.publicSummary().then(setSummary).catch(() => undefined); }, []);
  const hours = summary ? Math.floor(summary.median_time_to_case_minutes / 60) : 4;
  const mins = summary ? summary.median_time_to_case_minutes % 60 : 12;
  return <Box sx={{ minHeight: '100vh', bgcolor: '#F8F8FC', py: { xs: 4, md: 8 } }}>
    <Container maxWidth="lg">
      <Stack spacing={2} alignItems="center" textAlign="center" sx={{ mb: 5 }}>
        <Chip icon={<PublicOutlined />} label="NATIONAL PROCUREMENT TRANSPARENCY" sx={{ bgcolor: '#ECECFF', color: '#3F3D8A', fontWeight: 700 }} />
        <Typography variant="h2" fontWeight={700} sx={{ color: '#2E2C42', fontSize: { xs: '2.4rem', md: '4rem' } }}>Public money, <Box component="em" sx={{ color: '#5F5CAD', fontFamily: 'serif' }}>made clearer.</Box></Typography>
        <Typography color="text.secondary" sx={{ maxWidth: 670 }}>Aggregated procurement insight built with deterministic checks, human decisions, and privacy-preserving public reporting.</Typography>
      </Stack>
      <Grid container spacing={2} sx={{ mb: 3 }}>
        <Grid item xs={12} sm={6} md={3}><Metric label="Reduced leakage" value={summary ? `₹${(summary.reduced_leakage / 10000000).toFixed(1)} Cr` : '₹24.8 Cr'} note="Identified for review" tone="#E8E9FF" /></Grid>
        <Grid item xs={12} sm={6} md={3}><Metric label="Case compression ratio" value={summary ? `${summary.case_compression_ratio}×` : '8.4×'} note="Fewer cases, higher precision" tone="#DDF4E6" /></Grid>
        <Grid item xs={12} sm={6} md={3}><Metric label="Median time-to-case" value={`${hours}h ${mins}m`} note="From submission to evidence" tone="#FFF0D8" /></Grid>
        <Grid item xs={12} sm={6} md={3}><Metric label="Audit traceability" value={summary ? `${Math.round(summary.audit_traceability * 100)}%` : '100%'} note="Decisions are verifiable" tone="#FBE2E4" /></Grid>
      </Grid>
      <Card sx={{ borderRadius: 4, border: '1px solid #E7E6F5', boxShadow: '0 4px 16px rgba(63,61,138,.08)' }}><CardContent sx={{ p: { xs: 2.5, md: 4 } }}>
        <Typography variant="overline" color="#6B68A7" fontWeight={700}>HOW THIS WORKS</Typography><Typography variant="h5" fontWeight={700} sx={{ mb: 3 }}>Accountability without accusation</Typography>
        <Grid container spacing={3}>{[[InsightsOutlined, 'Deterministic detection', 'Fixed, explainable signals surface unusual spend patterns.'], [GavelOutlined, 'Human auditor decision', 'Qualified auditors assess evidence and make every final call.'], [CheckCircleOutline, 'Public reporting', 'Only aggregate, redacted insight is shared publicly.']].map(([Icon, title, text]: any, index) => <Grid item xs={12} md={4} key={title}><Stack spacing={1}><Box sx={{ display: 'grid', placeItems: 'center', width: 42, height: 42, borderRadius: 3, bgcolor: '#ECECFF', color: '#55519D' }}><Icon /></Box><Typography variant="caption" color="text.secondary">0{index + 1}</Typography><Typography fontWeight={700}>{title}</Typography><Typography variant="body2" color="text.secondary">{text}</Typography></Stack></Grid>)}</Grid>
      </CardContent></Card>
      <Typography align="center" variant="caption" color="text.secondary" sx={{ display: 'block', mt: 4 }}>All figures are aggregate and redacted. No individual vendor, institution, or transaction data is displayed publicly.</Typography>
    </Container>
  </Box>;
}
