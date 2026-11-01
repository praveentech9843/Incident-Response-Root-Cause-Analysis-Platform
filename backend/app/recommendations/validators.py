import re
from typing import List, Set, Tuple
from app.recommendations.evidence import RecommendationInput
from app.recommendations.schemas import (
    RecommendationConfidenceLevel,
    RecommendationItem,
    RecommendationResult,
    RecommendationStatus,
    RecommendationType,
    RiskLevel,
)

# Forbidden execution patterns (destructive commands, CLI commands, scripts)
EXECUTION_COMMAND_PATTERNS = [
    r"\bkubectl\b",
    r"\bsystemctl\b",
    r"\bservice\s+\w+\s+(?:restart|stop|start)\b",
    r"\bdocker\s+(?:run|stop|restart|rm|kill)\b",
    r"\brm\s+-rf\b",
    r"\bsudo\b",
    r"\bkill\s+-9\b",
    r"\bgit\s+(?:push|commit|checkout|reset)\b",
    r"\bALTER\s+TABLE\b",
    r"\bDROP\s+TABLE\b",
    r"\bDELETE\s+FROM\b",
    r"\breboot\b",
    r"\bshutdown\b",
    r"\bchmod\s+[0-7]{3,4}\b",
]

# Patterns detecting invented configuration values (e.g. "change timeout to 30s", "set memory limit to 4GB")
INVENTED_CONFIG_PATTERNS = [
    r"\b(?:change|set|increase|decrease|update)\s+.*?\btimeout\s+(?:to|=)\s*\d+\s*(?:s|ms|sec|seconds)?\b",
    r"\btimeout\s+of\s+\d+\s*(?:s|ms|sec|seconds)\b",
    r"\b(?:set|limit)\s+.*?\b(?:cpu|memory|ram)\s+(?:to|=)\s*\d+\s*(?:m|g|gb|mb|cores?)\b",
    r"\b(?:set|scale)\s+.*?\breplicas?\s+(?:to|=)\s*\d+\b",
    r"\b(?:set|change)\s+.*?\bpool\s+size\s+(?:to|=)\s*\d+\b",
    r"\b(?:set|change)\s+.*?\bretry\s+count\s+(?:to|=)\s*\d+\b",
]

# Patterns detecting invented numerical impact claims (e.g. "reduce errors by 87%")
NUMERICAL_IMPACT_PATTERNS = [
    r"\b(?:reduce|decrease|cut)\s+.*?\bby\s+\d+%",
    r"\b\d+%\s+(?:reduction|improvement|decrease|drop|fix)\b",
    r"\bguarantee\s+100%",
    r"\b\d+%",
]


class RecommendationValidator:
    """
    Strict safety, grounding, and anti-hallucination validation layer for recommendations.
    Enforces evidence traceability, rejects execution commands, catches invented config values,
    and guarantees the Investigation-First principle.
    """

    @classmethod
    def validate_and_refine(
        cls,
        raw_result: RecommendationResult,
        rec_input: RecommendationInput,
    ) -> RecommendationResult:
        valid_evidence_ids = rec_input.get_observed_evidence_ids()
        known_services = rec_input.get_known_services()
        unavailable_categories = {
            u.get("category")
            for u in rec_input.unavailable_contexts
            if isinstance(u, dict) and u.get("category")
        }

        refined_recommendations: List[RecommendationItem] = []
        limitations: List[str] = list(raw_result.limitations)

        # 1. Inspect underlying RCA status
        is_insufficient = rec_input.is_insufficient_evidence()
        if is_insufficient:
            limitations.append(
                "Underlying RCA has INSUFFICIENT_EVIDENCE. Fix recommendations are prohibited; "
                "prioritizing investigation and telemetry collection."
            )

        for rec in raw_result.recommendations:
            validation_errors: List[str] = []

            # 2. Execution Command Check (Strict Safety Guard)
            if cls._contains_execution_command(rec):
                limitations.append(
                    f"Rejected recommendation '{rec.title}' because it contained forbidden execution instructions or CLI commands."
                )
                continue

            # 3. Evidence Reference Validation
            valid_supporting: List[str] = []
            for ev_id in rec.supporting_evidence:
                if ev_id in valid_evidence_ids:
                    valid_supporting.append(ev_id)
                else:
                    validation_errors.append(
                        f"Nonexistent evidence reference '{ev_id}' removed from recommendation '{rec.title}'."
                    )

            if not valid_supporting and valid_evidence_ids:
                # If provider hallucinated all evidence IDs, reject or fallback to first valid observed item
                limitations.append(
                    f"Recommendation '{rec.title}' cited no valid evidence IDs. Downgraded to review."
                )
                valid_supporting = [list(valid_evidence_ids)[0]]

            # 4. Service Grounding Check
            cls._check_service_references(rec, known_services, validation_errors)

            # 5. Unavailable Context Grounding Check
            cls._check_unavailable_context(rec, unavailable_categories, validation_errors)

            # 6. Invented Configuration Check
            cleaned_title, cleaned_desc, config_found = cls._sanitize_invented_config(
                rec.title, rec.description
            )
            if config_found:
                validation_errors.append(
                    f"Unsupported specific configuration values detected in '{rec.title}' and replaced with conceptual guidance."
                )

            # 7. Invented Numerical Impact Check
            cleaned_impact, impact_found = cls._sanitize_numerical_impact(rec.expected_impact)
            if impact_found:
                validation_errors.append(
                    f"Invented numerical impact percentages detected and replaced with evidence-grounded non-numerical impact."
                )

            # 8. Type and Investigation-First Enforcement
            adjusted_type, adjusted_risk, type_notes = cls._enforce_investigation_first(
                rec=rec,
                rec_input=rec_input,
                is_insufficient=is_insufficient,
            )
            validation_errors.extend(type_notes)

            # 9. Verification Steps Enforcement for FIX
            verification_steps = list(rec.verification_steps)
            if adjusted_type == RecommendationType.FIX and not verification_steps:
                verification_steps = [
                    "Verify current service configuration matches expected baseline.",
                    "Monitor error rates and latency across the incident window post-adjustment.",
                    "Confirm no regression or cascading failures in upstream and downstream dependencies.",
                ]
                validation_errors.append(
                    f"Added mandatory verification steps to FIX recommendation '{rec.title}'."
                )

            # 10. Status and Execution Prevention (Status cannot be EXECUTED)
            status = rec.status
            if str(status).upper() == "EXECUTED":
                status = RecommendationStatus.REVIEW_REQUIRED
                validation_errors.append("Status 'EXECUTED' is forbidden in Phase 6; reverted to REVIEW_REQUIRED.")
            elif adjusted_type == RecommendationType.FIX and status == RecommendationStatus.PROPOSED:
                status = RecommendationStatus.REVIEW_REQUIRED

            # 11. Bounded Confidence
            bounded_confidence, confidence_level = cls._bound_confidence(
                rec.confidence, valid_supporting, is_insufficient
            )

            # Assemble refined recommendation
            refined_rec = RecommendationItem(
                recommendation_id=rec.recommendation_id,
                type=adjusted_type,
                title=cleaned_title,
                description=cleaned_desc,
                rationale=rec.rationale,
                supporting_evidence=valid_supporting,
                confidence=bounded_confidence,
                confidence_level=confidence_level,
                risk_level=adjusted_risk,
                expected_impact=cleaned_impact,
                prerequisites=rec.prerequisites,
                verification_steps=verification_steps,
                status=status,
            )
            refined_recommendations.append(refined_rec)
            limitations.extend(validation_errors)

        return RecommendationResult(
            status=raw_result.status,
            analysis_id=raw_result.analysis_id,
            summary=raw_result.summary,
            recommendations=refined_recommendations,
            limitations=list(dict.fromkeys(limitations)),  # deduplicate
            provider=raw_result.provider,
            model=raw_result.model,
        )

    @classmethod
    def _contains_execution_command(cls, rec: RecommendationItem) -> bool:
        full_text = f"{rec.title} {rec.description} {rec.rationale} {' '.join(rec.verification_steps)}"
        for pattern in EXECUTION_COMMAND_PATTERNS:
            if re.search(pattern, full_text, re.IGNORECASE):
                return True
        return False

    @classmethod
    def _check_service_references(
        cls, rec: RecommendationItem, known_services: Set[str], errors: List[str]
    ) -> None:
        if not known_services:
            return
        # If words that look like Microservices are referenced, check against known set
        full_text = f"{rec.title} {rec.description}"
        potential_services = re.findall(r"\b[A-Z][a-zA-Z0-9]+(?:Service|Gateway|Cluster|Worker|App|API|DB)\b", full_text)
        for svc in potential_services:
            if svc not in known_services and svc not in {"Microservice", "DatabaseService", "ThirdPartyService"}:
                errors.append(f"Service '{svc}' mentioned in recommendation was not present in incident data.")

    @classmethod
    def _check_unavailable_context(
        cls, rec: RecommendationItem, unavailable_categories: Set[str], errors: List[str]
    ) -> None:
        full_text = f"{rec.title} {rec.description} {rec.rationale}".lower()
        if "metrics" in unavailable_categories:
            if re.search(r"\b(?:cpu|memory|disk|saturation|utilization)\b.*(?:\d+%|spike|saturation)", full_text):
                errors.append("Metrics context was NOT_CONNECTED; metric assertions cannot be cited as confirmed facts.")
        if "deployment" in unavailable_categories:
            if re.search(r"\b(?:commit|deploy|release|build)\b.*(?:regression|caused|introduced)", full_text):
                errors.append("Deployment context was INTEGRATION_REQUIRED; deployment claims cannot be treated as verified.")

    @classmethod
    def _sanitize_invented_config(cls, title: str, description: str) -> Tuple[str, str, bool]:
        found = False
        new_title = title
        new_desc = description
        for pattern in INVENTED_CONFIG_PATTERNS:
            if re.search(pattern, new_title, re.IGNORECASE):
                found = True
                new_title = re.sub(pattern, "review timeout and connection configuration", new_title, flags=re.IGNORECASE)
            if re.search(pattern, new_desc, re.IGNORECASE):
                found = True
                new_desc = re.sub(pattern, "review operational configuration against standard baselines", new_desc, flags=re.IGNORECASE)
        return new_title, new_desc, found

    @classmethod
    def _sanitize_numerical_impact(cls, expected_impact: str) -> Tuple[str, bool]:
        found = False
        new_impact = expected_impact
        for pattern in NUMERICAL_IMPACT_PATTERNS:
            if re.search(pattern, new_impact, re.IGNORECASE):
                found = True
                new_impact = re.sub(
                    pattern,
                    "reduce potential incident recurrence if verified by testing",
                    new_impact,
                    flags=re.IGNORECASE,
                )
        return new_impact, found

    @classmethod
    def _enforce_investigation_first(
        cls,
        rec: RecommendationItem,
        rec_input: RecommendationInput,
        is_insufficient: bool,
    ) -> Tuple[RecommendationType, RiskLevel, List[str]]:
        notes: List[str] = []
        rec_type = rec.type
        risk = rec.risk_level

        # If insufficient evidence, FIX is strictly prohibited
        if is_insufficient and rec_type == RecommendationType.FIX:
            notes.append(
                f"Downgraded FIX recommendation '{rec.title}' to DIAGNOSTIC_VERIFICATION due to INSUFFICIENT_EVIDENCE in RCA."
            )
            return RecommendationType.DIAGNOSTIC_VERIFICATION, RiskLevel.LOW, notes

        # Inspect RCA hypotheses strength
        all_hypotheses_unverified = True
        for hyp in rec_input.hypotheses:
            causal = hyp.get("causal_status")
            if causal in ("SUPPORTED", "CONFIRMED"):
                all_hypotheses_unverified = False
                break

        # If all hypotheses are HYPOTHESIS or UNVERIFIED, downgrade FIX to DIAGNOSTIC_VERIFICATION
        if all_hypotheses_unverified and rec_type == RecommendationType.FIX:
            notes.append(
                f"RCA hypotheses are unconfirmed hypotheses; downgraded FIX recommendation '{rec.title}' to DIAGNOSTIC_VERIFICATION."
            )
            rec_type = RecommendationType.DIAGNOSTIC_VERIFICATION
            risk = RiskLevel.LOW

        # Ensure sensible risk mappings
        if rec_type in (RecommendationType.INVESTIGATION, RecommendationType.DIAGNOSTIC_VERIFICATION):
            if risk not in (RiskLevel.LOW, RiskLevel.MEDIUM):
                risk = RiskLevel.LOW
        elif rec_type == RecommendationType.FIX:
            if risk == RiskLevel.LOW:
                risk = RiskLevel.MEDIUM

        return rec_type, risk, notes

    @classmethod
    def _bound_confidence(
        cls,
        raw_confidence: float,
        supporting_evidence: List[str],
        is_insufficient: bool,
    ) -> Tuple[float, RecommendationConfidenceLevel]:
        if is_insufficient or len(supporting_evidence) == 0:
            return 0.3, RecommendationConfidenceLevel.LOW

        # Cap based on supporting evidence count
        if len(supporting_evidence) == 1:
            confidence = min(raw_confidence, 0.65)
            level = RecommendationConfidenceLevel.LOW if confidence < 0.5 else RecommendationConfidenceLevel.MEDIUM
            return round(confidence, 2), level
        elif len(supporting_evidence) == 2:
            confidence = min(raw_confidence, 0.80)
            level = RecommendationConfidenceLevel.MEDIUM
            return round(confidence, 2), level
        else:
            confidence = min(raw_confidence, 0.95)
            level = RecommendationConfidenceLevel.HIGH if confidence >= 0.8 else RecommendationConfidenceLevel.MEDIUM
            return round(confidence, 2), level
