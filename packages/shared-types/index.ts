/**
 * Shared TypeScript types for GovSpend Nexus AI
 * Used by frontend and Node.js services
 */

// ============ Enums ============

export enum SignalType {
  PRICE_DEVIATION = 'price_deviation',
  DUPLICATE_FUZZY = 'duplicate_fuzzy',
  VENDOR_GRAPH_RISK = 'vendor_graph_risk',
  TIMING_ANOMALY = 'timing_anomaly',
  CONTRACT_SPLITTING = 'contract_splitting',
  APPROVAL_VELOCITY = 'approval_velocity',
}

export enum CaseStatus {
  OPEN = 'open',
  IN_REVIEW = 'in_review',
  APPROVED = 'approved',
  REJECTED = 'rejected',
  ESCALATED = 'escalated',
}

export enum RiskTier {
  HIGH = 'high',
  BORDERLINE = 'borderline',
  LOW = 'low',
}

export enum UnmaskStatus {
  PENDING = 'pending',
  APPROVED = 'approved',
  REJECTED = 'rejected',
  EXPIRED = 'expired',
}

export enum ActionType {
  APPROVE = 'approve',
  REJECT = 'reject',
  RECALIBRATE = 'recalibrate',
  UNMASK = 'unmask',
  ESCALATE = 'escalate',
  ASSIGN = 'assign',
}

export enum SourceType {
  CPPP = 'CPPP',
  GEM = 'GeM',
  ERP = 'ERP',
  MANUAL = 'Manual',
}

// ============ Core Types ============

export interface Signal {
  type: SignalType;
  value: number; // 0-1
  confidence: number; // 0-1
  evidence_ref: string[];
  metadata?: Record<string, any>;
}

export interface CanonicalTransaction {
  id: string;
  invoice_doc_hash: string;
  vendor_token: string;
  department_id: string;
  amount: number;
  unit_price: number;
  quantity: number;
  category: string;
  region: string;
  submitted_at: string;
  approved_at?: string;
  approver_token?: string;
  source: SourceType;
  metadata?: Record<string, any>;
}

export interface RiskScore {
  id: string;
  transaction_id: string;
  score: number; // 0-1
  tier: RiskTier;
  confidence_factor: number; // 0-1
  policy_weight_version: string;
  evidence_bundle_id: string;
  created_at: string;
}

export interface EvidenceBundle {
  id: string;
  risk_score_id: string;
  signals: Signal[];
  transaction: CanonicalTransaction;
  vendor_token: string;
  department_id: string;
  benchmarks: Record<string, any>;
  retrieved_policy_chunks?: Array<{
    chunk_id: string;
    content: string;
    source: string;
    relevance_score: number;
  }>;
  created_at: string;
}

export interface Case {
  id: string;
  risk_score_id: string;
  status: CaseStatus;
  assigned_auditor_id?: string;
  jurisdiction_scope: string;
  priority: number; // 1-5
  created_at: string;
  updated_at: string;
  resolved_at?: string;
  resolution_notes?: string;
}

export interface UnmaskRequest {
  id: string;
  case_id: string;
  requester_id: string;
  approver_id?: string;
  entity_type: 'vendor' | 'official' | 'department' | 'transaction';
  entity_token: string;
  reason: string;
  status: UnmaskStatus;
  jurisdiction_scope: string;
  created_at: string;
  approved_at?: string;
  viewed_at?: string;
}

export interface Explanation {
  case_id: string;
  rationale: string;
  citations: Array<{
    sentence_index: number;
    evidence_id?: string;
    policy_clause_id?: string;
    quote?: string;
  }>;
  grounding_rate: number; // 0-1
  model_used: string;
  tokens_used: number;
  created_at: string;
}

export interface Action {
  id: string;
  case_id: string;
  auditor_id: string;
  action: ActionType;
  rationale?: string;
  metadata?: Record<string, any>;
  created_at: string;
}

// ============ MCP Tool Types ============

export interface MCPTool {
  name: string;
  permission_tag: string;
  input_schema: Record<string, any>;
  output_schema: Record<string, any>;
  side_effects: string[];
  rate_limit: number;
  timeout: number;
}

// ============ Request/Response Types ============

export interface CaseListResponse {
  cases: Array<{
    id: string;
    risk_score_id: string;
    status: CaseStatus;
    jurisdiction_scope: string;
    priority: number;
    created_at: string;
    score: number;
    tier: RiskTier;
    top_signals: Signal[];
  }>;
  total: number;
  page: number;
  page_size: number;
}

export interface CaseDetailResponse {
  case: Case;
  risk_score: RiskScore;
  evidence_bundle: EvidenceBundle;
  explanation?: Explanation;
}

export interface IngestRequest {
  file_content: string;
  department_id: string;
  region: string;
  source: SourceType;
}

export interface IngestResponse {
  transaction_id: string;
  status: string;
  vendor_token: string;
  message: string;
  warnings?: string[];
}

export interface UnmaskRequestData {
  case_id: string;
  entity_type: 'vendor' | 'official' | 'department' | 'transaction';
  entity_token: string;
  reason: string;
}

export interface UnmaskResponse {
  request_id: string;
  status: UnmaskStatus;
  message: string;
}

// ============ Validation Helpers ============

export function isSignalActive(signal: Signal, threshold: number = 0.15): boolean {
  return signal.value > threshold;
}

export function getTierColor(tier: RiskTier): string {
  switch (tier) {
    case RiskTier.HIGH:
      return 'red';
    case RiskTier.BORDERLINE:
      return 'orange';
    case RiskTier.LOW:
      return 'green';
    default:
      return 'gray';
  }
}

export function formatCurrency(amount: number): string {
  return new Intl.NumberFormat('en-IN', {
    style: 'currency',
    currency: 'INR',
    minimumFractionDigits: 0,
    maximumFractionDigits: 0,
  }).format(amount);
}

export function formatDate(dateString: string): string {
  return new Date(dateString).toLocaleDateString('en-IN', {
    year: 'numeric',
    month: 'short',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  });
}
