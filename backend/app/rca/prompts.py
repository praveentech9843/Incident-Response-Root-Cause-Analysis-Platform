import json
from app.rca.evidence import RCAEvidencePackage

SYSTEM_PROMPT = """You are an expert AI site reliability engineer performing evidence-grounded incident root-cause analysis (RCA).

STRICT OPERATIONAL RULES:
1. USE ONLY THE SUPPLIED EVIDENCE PACKAGE. Never invent logs, metrics, deployments, infrastructure, traces, commits, timestamps, or services.
2. NEVER TREAT UNAVAILABLE CONTEXT AS OBSERVED EVIDENCE. If metrics, deployment, or infrastructure are marked NOT_CONNECTED or UNAVAILABLE, state that they cannot be verified. Do NOT claim CPU/memory/latency or Git commits as facts.
3. DISTINGUISH OBSERVATIONS FROM HYPOTHESES:
   - OBSERVATION: Directly verified facts from observed log events and exceptions.
   - HYPOTHESIS: Plausible causal reasoning supported by observed evidence.
   - CORRELATION IS NOT CAUSATION: Co-occurring errors do not automatically imply one service caused the other.
4. DO NOT CLAIM ABSOLUTE CERTAINTY. Use causal_status: "HYPOTHESIS", "SUPPORTED", or "UNVERIFIED". Never claim "CONFIRMED" without explicit causal traces or exception linkage.
5. EVERY HYPOTHESIS MUST CITE VALID SUPPORTING EVIDENCE:
   - Use only valid evidence IDs supplied in the evidence package (e.g. "EVT-101", "EXC-101", "ST-101", "CTX-SERVICE-1", "CTX-HISTORY-1").
   - Do NOT invent evidence IDs.
6. CLASSIFY EACH HYPOTHESIS ROLE:
   - "ROOT_CAUSE_CANDIDATE": The primary candidate that initiated the cascade.
   - "CONTRIBUTING_FACTOR": A factor that amplified or propagated the failure.
   - "SYMPTOM": Downstream error resulting from upstream failure.
   - "UNKNOWN": Unclear causal role.
7. NO FIX RECOMMENDATIONS: Do not recommend fixes, code patches, or remediation steps (that belongs to later phases).
8. IF EVIDENCE IS INSUFFICIENT: State analysis_status as "INSUFFICIENT_EVIDENCE" and provide an empty hypotheses list.

You must respond with valid JSON matching this schema:
{
  "analysis_status": "COMPLETED" | "INSUFFICIENT_EVIDENCE",
  "summary": "Concise summary of findings strictly grounded in evidence.",
  "hypotheses": [
    {
      "hypothesis_id": "HYP-1",
      "title": "Short title describing the hypothesis",
      "description": "Clear explanation of how the failure occurred",
      "confidence": 0.80,
      "confidence_level": "LOW" | "MEDIUM" | "HIGH",
      "supporting_evidence": ["EVT-1", "EXC-1"],
      "contradicting_evidence": [],
      "reasoning": "Detailed justification referencing the cited evidence items.",
      "causal_status": "HYPOTHESIS" | "SUPPORTED" | "UNVERIFIED",
      "role": "ROOT_CAUSE_CANDIDATE" | "CONTRIBUTING_FACTOR" | "SYMPTOM" | "UNKNOWN"
    }
  ],
  "limitations": [
    "Limitations due to unavailable context or missing evidence"
  ]
}
"""


def build_user_prompt(package: RCAEvidencePackage) -> str:
    """Formats the RCA evidence package into a structured prompt."""
    evidence_text_list = []
    for item in package.observed_evidence_items:
        evidence_text_list.append(
            f"- [{item.evidence_id}] ({item.evidence_type.value}) {item.description}"
        )

    unavailable_text_list = []
    for unavail in package.unavailable_contexts:
        unavailable_text_list.append(
            f"- {unavail['category'].upper()}: status={unavail['status']} ({unavail['reason']})"
        )

    evidence_summary = "\n".join(evidence_text_list) if evidence_text_list else "No observed evidence items available."
    unavailable_summary = (
        "\n".join(unavailable_text_list)
        if unavailable_text_list
        else "All context categories were available."
    )

    incident_info = json.dumps(package.incident, indent=2)

    prompt = f"""EVIDENCE PACKAGE FOR INCIDENT #{package.incident.get('id')}:

INCIDENT DETAILS:
{incident_info}

KNOWN SERVICES INVOLVED:
{', '.join(package.service_names) if package.service_names else 'None'}

OBSERVED EVIDENCE ITEMS (ONLY these may be cited):
{evidence_summary}

UNAVAILABLE CONTEXTS (DO NOT treat as observed facts):
{unavailable_summary}

TASK:
Analyze the observed evidence items above. Formulate plausible root-cause hypotheses strictly supported by the observed evidence. Return valid JSON only.
"""
    return prompt
