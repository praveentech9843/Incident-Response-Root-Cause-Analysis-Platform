from typing import List, Set
from app.models.incident import Incident


class InvalidEvidenceReferenceError(ValueError):
    """Raised when an action, note, or verification references non-existent evidence."""
    pass


class EvidenceReferenceValidator:
    """
    Validates evidence references for an incident against the ground truth of
    correlated log events, exceptions, stack traces, context items, RCA analyses,
    and Phase 6 recommendations.
    Strictly prevents hallucinated or invented evidence references.
    """

    @classmethod
    def get_valid_evidence_tokens(cls, incident: Incident) -> Set[str]:
        valid_tokens: Set[str] = set()

        # 1. Parsed log events, exceptions, and stack traces
        for ie in incident.incident_events:
            valid_tokens.add(f"EVT-{ie.event_index}")
            valid_tokens.add(f"EVT-{ie.id}")
            pe = ie.parsed_log
            if pe:
                valid_tokens.add(f"EVT-{pe.event_index}")
                valid_tokens.add(f"EVT-{pe.id}")
                if pe.exception_type:
                    valid_tokens.add(f"EXC-{pe.event_index}")
                    valid_tokens.add(f"EXC-{pe.id}")
                    valid_tokens.add(f"EXC-{ie.event_index}")
                if pe.stack_trace:
                    valid_tokens.add(f"ST-{pe.event_index}")
                    valid_tokens.add(f"ST-{pe.id}")
                    valid_tokens.add(f"ST-{ie.event_index}")


        # 2. Context enrichment items
        for ctx in incident.contexts:
            valid_tokens.add(f"CTX-{ctx.id}")
            if ctx.context_category:
                valid_tokens.add(f"CTX-{ctx.context_category.lower()}")
                valid_tokens.add(f"CTX-{ctx.context_category.upper()}")

        # 3. Phase 5 RCA Analyses & Snapshots
        for rca in incident.rca_analyses:
            if rca.analysis_id:
                valid_tokens.add(rca.analysis_id)
            snapshot = rca.evidence_snapshot or {}
            for ev in snapshot.get("events", []):
                if isinstance(ev, dict) and "evidence_id" in ev:
                    valid_tokens.add(ev["evidence_id"])
            for exc in snapshot.get("exceptions", []):
                if isinstance(exc, dict) and "evidence_id" in exc:
                    valid_tokens.add(exc["evidence_id"])
            for st in snapshot.get("stack_traces", []):
                if isinstance(st, dict) and "evidence_id" in st:
                    valid_tokens.add(st["evidence_id"])
            for ctx_key in snapshot.get("contexts", {}).keys():
                valid_tokens.add(f"CTX-{ctx_key.lower()}")
                valid_tokens.add(f"CTX-{ctx_key.upper()}")

            for hyp in rca.hypotheses or []:
                if isinstance(hyp, dict):
                    if "hypothesis_id" in hyp:
                        valid_tokens.add(hyp["hypothesis_id"])
                    for se in hyp.get("supporting_evidence", []):
                        valid_tokens.add(str(se))

        # 4. Phase 6 Recommendations
        for rec in incident.recommendations:
            if rec.recommendation_id:
                valid_tokens.add(rec.recommendation_id)
            for se in rec.supporting_evidence or []:
                valid_tokens.add(str(se))

        return valid_tokens

    @classmethod
    def validate_references(cls, incident: Incident, references: List[str]) -> None:
        """
        Validates that all tokens in references exist in the incident's valid evidence set.
        Raises InvalidEvidenceReferenceError if any token is invalid.
        """
        if not references:
            return

        valid_tokens = cls.get_valid_evidence_tokens(incident)

        for ref in references:
            ref_clean = ref.strip()
            if not ref_clean:
                raise InvalidEvidenceReferenceError("Evidence reference token cannot be empty")
            if ref_clean not in valid_tokens:
                raise InvalidEvidenceReferenceError(
                    f"Invalid evidence reference: '{ref_clean}' does not exist in incident evidence."
                )
