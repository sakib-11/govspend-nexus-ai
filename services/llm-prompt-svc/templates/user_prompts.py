"""User prompts — templates that get interpolated with case data."""

from __future__ import annotations

from typing import Any, Dict

USER_PROMPTS: Dict[str, str] = {
    "default": """\
I need you to analyze the following procurement case and provide a detailed \
explanation of the detected fraud signals.

CASE INFORMATION:
- Case ID: {case_id}
- Transaction ID: {transaction_id}
- Risk Score: {risk_score}
- Risk Tier: {risk_tier}

SIGNALS DETECTED:
{signals}

EVIDENCE BUNDLE:
{evidence_bundle}

RELEVANT POLICIES:
{retrieved_policies}

Please provide:
1. A summary of the overall risk assessment
2. Detailed explanations for each significant signal
3. Citations linking explanations to evidence and policies
4. A confidence score for your analysis

Requirements:
- Every explanation point must include evidence citations
- Reference policies where applicable
- Be specific and actionable
- If uncertain, acknowledge it
- Focus on fraud indicators and patterns""",

    "detailed": """\
Perform a comprehensive analysis of the following procurement case.

CASE DETAILS:
- Case ID: {case_id}
- Transaction ID: {transaction_id}
- Risk Score: {risk_score}
- Risk Tier: {risk_tier}
{department_line}
{amount_line}
{vendor_line}
{date_line}

DETECTED SIGNALS:
{signals}

AVAILABLE EVIDENCE:
{evidence_bundle}

RELEVANT POLICIES:
{retrieved_policies}

CONTEXT:
{context}

Please provide a detailed analysis with:
1. Executive Summary
2. Signal Analysis (each signal with explanation)
3. Evidence-Based Findings
4. Policy Compliance Assessment
5. Risk Mitigation Recommendations

For each explanation point:
- Include the signal value and confidence
- Reference specific evidence
- Cite relevant policies
- Explain the fraud indicator
- Provide context for the finding""",

    "case_focused": """\
Analyze this procurement fraud case and provide explanations for each \
detected signal.

CASE: {case_id}
RISK SCORE: {risk_score} ({risk_tier})

DETECTED SIGNALS:
{signals}

EVIDENCE:
{evidence_bundle}

POLICIES:
{retrieved_policies}

INSTRUCTIONS:
For each signal, provide:
1. A clear explanation of what the signal indicates
2. The evidence supporting this finding
3. Relevant policy references
4. The confidence level

Summary requirements:
1. Overall risk assessment
2. Key findings
3. Recommendations
4. Confidence level""",

    "minimal": """\
Summarize the key risk factors for case {case_id}.

Risk Score: {risk_score} ({risk_tier})

Signals: {signals}
Evidence: {evidence_bundle}""",
}


def get_user_prompt(style: str = "default") -> str:
    """Return the raw user prompt template for *style*."""
    return USER_PROMPTS.get(style, USER_PROMPTS["default"])


def list_styles() -> list[str]:
    """Return available user prompt style names."""
    return list(USER_PROMPTS.keys())
