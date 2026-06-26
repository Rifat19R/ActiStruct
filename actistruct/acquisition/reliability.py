from __future__ import annotations

from collections.abc import Iterable

DEFAULT_BETA = 2.0
DEFAULT_GAMMA = 1.0
DEFAULT_FAILURE_RISK_THRESHOLD = 0.10


def failure_aware_minimization_score(
    predicted_value: float,
    uncertainty: float,
    failure_risk: float,
    exploration_weight: float = 1.0,
    failure_penalty: float = 1.0,
) -> float:
    """Lower-is-better score for energy minimization candidates.

    This mirrors lower-confidence-bound acquisition, then penalizes candidates
    likely to fail before consuming DFT time.
    """

    risk = _bounded_risk(failure_risk)
    return predicted_value - exploration_weight * uncertainty + failure_penalty * risk


def lcb_minimization_score(
    predicted_value: float,
    uncertainty: float,
    beta: float = DEFAULT_BETA,
) -> float:
    """Lower-confidence-bound score for minimization."""

    return predicted_value - beta * uncertainty


def failure_aware_maximization_score(
    predicted_value: float,
    uncertainty: float,
    failure_risk: float,
    exploration_weight: float = 1.0,
    failure_penalty: float = 1.0,
) -> float:
    """Higher-is-better score for property maximization candidates."""

    risk = _bounded_risk(failure_risk)
    return predicted_value + exploration_weight * uncertainty - failure_penalty * risk


def rank_candidates(
    candidates: Iterable[dict[str, object]],
    objective: str = "minimize",
    exploration_weight: float | None = None,
    failure_penalty: float | None = None,
    beta: float = DEFAULT_BETA,
    gamma: float = DEFAULT_GAMMA,
    failure_risk_threshold: float = DEFAULT_FAILURE_RISK_THRESHOLD,
) -> list[dict[str, object]]:
    """Rank candidate dictionaries with failure-aware acquisition scores.

    Required keys:
    - `predicted_value`
    - `uncertainty`

    Optional keys:
    - `failure_risk`

    For minimization, the score is:
    `predicted_value - beta * uncertainty + gamma * failure_risk`.
    If `failure_risk` is absent, the original LCB score is used.
    """

    if objective not in {"minimize", "maximize"}:
        raise ValueError("objective must be 'minimize' or 'maximize'")

    if exploration_weight is not None:
        beta = exploration_weight
    if failure_penalty is not None:
        gamma = failure_penalty

    scored = []
    for candidate in candidates:
        predicted_value = float(candidate["predicted_value"])
        uncertainty = float(candidate["uncertainty"])
        failure_risk = _optional_risk(candidate.get("failure_risk"))
        applied_risk = 0.0 if failure_risk is None else failure_risk
        failure_penalty_value = gamma * applied_risk if failure_risk is not None else 0.0
        if objective == "minimize":
            base_score = lcb_minimization_score(predicted_value, uncertainty, beta)
            score = base_score + failure_penalty_value
        else:
            base_score = predicted_value + beta * uncertainty
            score = failure_aware_maximization_score(
                predicted_value,
                uncertainty,
                applied_risk,
                beta,
                gamma if failure_risk is not None else 0.0,
            )
        item = dict(candidate)
        item["candidate_id"] = candidate.get("candidate_id", candidate.get("id", candidate.get("record_id", len(scored))))
        item["predicted_value"] = predicted_value
        item["uncertainty"] = uncertainty
        item["failure_risk"] = "" if failure_risk is None else failure_risk
        item["failure_penalty"] = failure_penalty_value
        item["acquisition_score"] = score
        item["failure_aware_score"] = score
        item["risk_flag"] = _risk_flag(failure_risk, failure_risk_threshold)
        item["selection_reason"] = _selection_reason(failure_risk, gamma)
        item["_base_score"] = base_score
        scored.append(item)

    reverse = objective == "maximize"
    ranked = sorted(scored, key=lambda item: float(item["acquisition_score"]), reverse=reverse)
    for rank, item in enumerate(ranked, start=1):
        item["rank"] = rank
        item.pop("_base_score", None)
    return ranked


def _bounded_risk(value: float) -> float:
    return max(0.0, min(1.0, float(value)))


def _optional_risk(value: object) -> float | None:
    if value in (None, ""):
        return None
    return _bounded_risk(float(value))


def _risk_flag(failure_risk: float | None, threshold: float) -> str:
    if failure_risk is None:
        return "missing"
    return "elevated" if failure_risk >= threshold else "low"


def _selection_reason(failure_risk: float | None, gamma: float) -> str:
    if failure_risk is None:
        return "ranked by original LCB; failure_risk missing"
    if gamma == 0:
        return "ranked by original LCB; gamma=0"
    return "ranked by failure-aware LCB soft penalty"
