/** API contracts for the new three-portal UI.  Calls only return data allowed
 * by the current server-side role and jurisdiction; the client never filters
 * data for access control. */
const baseUrl = import.meta.env.VITE_API_URL || 'http://localhost:8015';

export type PortalIdentity = {
  role: 'auditor' | 'institution';
  subject: string;
  jurisdictions: string[];
  institutionId?: string;
};

async function request<T>(path: string, identity?: PortalIdentity, init: RequestInit = {}): Promise<T> {
  const headers = new Headers(init.headers);
  headers.set('Content-Type', 'application/json');
  if (identity) {
    // Development adapter only. Production deployments receive identity from OIDC.
    headers.set('X-GovSpend-Role', identity.role);
    headers.set('X-GovSpend-Subject', identity.subject);
    headers.set('X-GovSpend-Jurisdictions', identity.jurisdictions.join(','));
    if (identity.institutionId) headers.set('X-GovSpend-Institution', identity.institutionId);
  }
  const response = await fetch(`${baseUrl}/api/v1${path}`, { ...init, headers });
  if (!response.ok) throw new Error(`API request failed (${response.status})`);
  return response.json() as Promise<T>;
}

export const nexusApi = {
  publicSummary: () => request('/public/metrics/summary'),
  publicFunnel: () => request('/public/funnel'),
  cases: (identity: PortalIdentity) => request('/cases', identity),
  caseDetail: (caseId: string, identity: PortalIdentity) => request(`/cases/${caseId}`, identity),
  decide: (caseId: string, action: 'approve' | 'reject' | 'escalate', comment: string, identity: PortalIdentity) => request(`/cases/${caseId}/decision`, identity, { method: 'POST', body: JSON.stringify({ action, comment }) }),
  submitInvoice: (institutionId: string, invoice: unknown, identity: PortalIdentity) => request(`/institutions/${institutionId}/invoices`, identity, { method: 'POST', body: JSON.stringify(invoice) }),
};
