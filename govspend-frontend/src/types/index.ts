/**
 * GovSpend Nexus AI - Complete TypeScript Type Definitions
 */

// ==========================================
// Authentication & User Management
// ==========================================

export enum UserRole {
  SUPER_ADMIN = 'super_admin',
  ADMIN = 'admin',
  AUDITOR_LEVEL_3 = 'auditor_level_3',
  AUDITOR_LEVEL_2 = 'auditor_level_2',
  AUDITOR_LEVEL_1 = 'auditor_level_1',
  OFFICER = 'officer',
  COMPLIANCE_OFFICER = 'compliance_officer',
  DATA_ANALYST = 'data_analyst',
  REVIEWER = 'reviewer',
  APPROVER = 'approver',
  READ_ONLY = 'read_only',
}

export interface User {
  user_id: string;
  username: string;
  email: string;
  full_name: string;
  roles: UserRole[];
  jurisdictions: string[];
  permissions?: string[];
  mfa_enabled?: boolean;
}

export interface UserRoleUpdate {
  user_id: string;
  roles: string[];
  jurisdictions: string[];
}

// ==========================================
// Case Models
// ==========================================

export type CaseTier = 'HIGH' | 'BORDERLINE' | 'LOW';

export type CaseStatus =
  | 'NEW'
  | 'UNDER_REVIEW'
  | 'APPROVED'
  | 'REJECTED'
  | 'ESCALATED'
  | 'CLOSED';

export interface Signal {
  detector_type: string;
  signal_value: number;
  confidence: number;
  evidence_ids?: string[];
  metadata?: Record<string, any>;
}

export interface Case {
  case_id: string;
  transaction_id: string;
  risk_score: number;
  tier: CaseTier;
  status: CaseStatus;
  department: string;
  vendor_token: string;
  amount: number;
  transaction_date: string;
  top_signals: Signal[];
  signal_count: number;
  created_at: string;
  updated_at: string;
}

export interface CaseActionRecord {
  action_id: string;
  action: string;
  user_id: string;
  action_time: string;
  notes?: string;
  reason?: string;
}

export interface CaseDetail {
  case_id: string;
  transaction_id: string;
  risk_score: number;
  tier: CaseTier;
  status: CaseStatus;
  confidence_factor: number;
  weights_version: string;
  transaction: {
    amount: number;
    currency?: string;
    unit_price?: number;
    quantity?: number;
    category?: string;
    description?: string;
    region?: string;
    submitted_at?: string;
    invoice_doc_hash?: string;
    source?: string;
    [key: string]: any;
  };
  vendor: {
    vendor_token: string;
    category?: string;
    risk_level?: string;
    registration_date?: string;
    masked_name?: string;
    [key: string]: any;
  };
  department: {
    department_id?: string;
    department_name: string;
    jurisdiction?: string;
    budget_code?: string;
    [key: string]: any;
  };
  signals: Signal[];
  signals_summary?: Record<string, any>;
  evidence_ids: string[];
  evidence_summary?: Record<string, any>;
  jurisdiction_id?: string;
  assigned_to?: string;
  created_at: string;
  updated_at: string;
  actions: CaseActionRecord[];
}

export interface CaseDetailResponse {
  case: CaseDetail;
  evidence: EvidenceItem[];
  actions: CaseActionRecord[];
}

export interface CaseFilters {
  tiers?: string[];
  statuses?: string[];
  department?: string;
  vendor_token?: string;
  minScore?: number;
  maxScore?: number;
  dateFrom?: string | null;
  dateTo?: string | null;
  search?: string;
}

export interface CaseListResponse {
  cases: Case[];
  total: number;
  limit: number;
  offset: number;
}

export interface CaseActionRequest {
  notes?: string;
  reason?: string;
}

// ==========================================
// Evidence Models
// ==========================================

export interface EvidenceItem {
  evidence_id: string;
  evidence_type: string;
  description: string;
  data: Record<string, any>;
  confidence: number;
  source: string;
  created_at: string;
}

export interface EvidenceDetail extends EvidenceItem {
  case_id: string;
  transaction_id: string;
  metadata?: Record<string, any>;
  verified?: boolean;
  hash?: string;
}

// ==========================================
// AI Explanation Models
// ==========================================

export interface ExplanationPoint {
  point_number: number;
  detector_name: string;
  sentence: string;
  confidence: number;
  evidence_ids: string[];
  policy_references: string[];
  citations?: Array<{
    sentence_index: number;
    evidence_id?: string;
    policy_clause_id?: string;
    quote?: string;
  }>;
}

export interface CaseExplanation {
  case_id: string;
  transaction_id: string;
  explanations: ExplanationPoint[];
  summary: string;
  overall_confidence: number;
  grounding_score: number;
  evidence_count: number;
  policy_count: number;
  generated_at: string;
  version: string;
}

// ==========================================
// Vendor Graph Models
// ==========================================

export interface GraphNode {
  id: string;
  type: 'vendor' | 'official' | 'department' | 'transaction' | 'shell_company';
  label: string;
  size?: number;
  color?: string;
  data?: Record<string, any>;
  metadata?: Record<string, any>;
}

export interface GraphEdge {
  id: string;
  source: string;
  target: string;
  type: 'supplies' | 'employs' | 'owns' | 'contracted' | 'approved_by' | 'shared_address';
  label: string;
  weight?: number;
  data?: Record<string, any>;
}

export interface VendorGraph {
  nodes: GraphNode[];
  edges: GraphEdge[];
  metadata?: Record<string, any>;
  timestamp: string;
}

export interface VendorAnalysis {
  vendor_token: string;
  degree_centrality: number;
  clustering_coefficient: number;
  shell_risk_index: number;
  connected_officials_count: number;
  historical_contracts_value: number;
  flagged_anomalies: string[];
}

// ==========================================
// Unmask Models
// ==========================================

export enum UnmaskStatus {
  PENDING = 'pending',
  APPROVED = 'approved',
  REJECTED = 'rejected',
  UNMASKED = 'unmasked',
  VIEWED = 'viewed',
  EXPIRED = 'expired',
}

export enum UnmaskEntityType {
  VENDOR = 'vendor',
  OFFICIAL = 'official',
  TRANSACTION = 'transaction',
  INVOICE = 'invoice',
}

export interface UnmaskRequestCreate {
  case_id: string;
  entity_type: UnmaskEntityType | string;
  entity_token: string;
  reason: string;
  jurisdiction_id: string;
}

export interface UnmaskResponse {
  request_id: string;
  case_id: string;
  entity_type: string;
  entity_token: string;
  status: UnmaskStatus;
  requested_by: string;
  requested_at: string;
  approved_by?: string | null;
  approved_at?: string | null;
  unmasked_data?: Record<string, any> | null;
}

export interface UnmaskApproval {
  decision: 'approve' | 'reject';
  reason?: string;
}

// ==========================================
// Admin & Policy Models
// ==========================================

export interface PolicyWeight {
  version: string;
  weights: Record<string, number>;
  is_active: boolean;
  created_at: string;
  created_by: string;
  description?: string;
}

export interface PolicyWeightCreate {
  weights: Record<string, number>;
  description?: string;
  activate?: boolean;
}

export interface AuditLogEntry {
  entry_id: string;
  timestamp: string;
  user_id: string;
  action: string;
  resource_type: string;
  resource_id?: string | null;
  details: Record<string, any>;
  hash_chain: {
    sequence: number;
    hash: string;
    previous_hash?: string;
  };
}

export interface AdminMetrics {
  totalCases: number;
  highRisk: number;
  borderline: number;
  lowRisk: number;
  totalAuditedAmount: number;
  potentialSavings: number;
  avgInferenceLatencyMs: number;
  tierDistribution: Array<{ name: string; value: number; color?: string }>;
  casesOverTime: Array<{ date: string; high: number; borderline: number; low: number }>;
  detectorDistribution: Array<{ detector: string; count: number; avgScore: number }>;
}

// ==========================================
// Officer Dashboard Models
// ==========================================

export interface ComplianceMetric {
  name: string;
  value: number; // 0-100%
  description: string;
  target: number;
  status: 'good' | 'fair' | 'poor';
}

export interface OfficerAlert {
  id: string;
  caseId: string;
  message: string;
  severity: 'HIGH' | 'MEDIUM' | 'LOW';
  timestamp: string;
  department: string;
}

export interface DepartmentCaseCount {
  department: string;
  high: number;
  borderline: number;
  low: number;
  totalSpend: number;
}

export interface OfficerMetrics {
  pendingReviews: number;
  totalCases: number;
  complianceRate: number;
  avgResolutionTime: number; // in hours
  totalSpendManaged: number;
  casesByDepartment: DepartmentCaseCount[];
  complianceMetrics: ComplianceMetric[];
  recentAlerts: OfficerAlert[];
}

export interface OfficerReport {
  id: string;
  title: string;
  generated_at: string;
  period: string;
  summary: string;
  total_spend: number;
  flagged_spend: number;
  compliance_score: number;
  status: 'published' | 'draft';
  file_url?: string;
}

// ==========================================
// Common State & UI
// ==========================================

export interface Pagination {
  page: number;
  limit: number;
  total: number;
}

export interface AppNotification {
  id: string;
  title: string;
  message: string;
  type: 'info' | 'warning' | 'error' | 'success';
  timestamp: string;
  read: boolean;
  link?: string;
}
