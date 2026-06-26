from __future__ import annotations

from collections.abc import Iterable


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
    exploration_weight: float = 1.0,
    failure_penalty: float = 1.0,
) -> list[dict[str, object]]:
    """Rank candidate dictionaries with failure-aware acquisition scores.

    Required keys:
    - `predicted_value`
    - `uncertainty`
    - `failure_risk`
    """

    if objective not in {"minimize", "maximize"}:
        raise ValueError("objective must be 'minimize' or 'maximize'")

    scored = []
    for candidate in candidates:
        predicted_value = float(candidate["predicted_value"])
        uncertainty = float(candidate["uncertainty"])
        failure_risk = float(candidate["failure_risk"])
        if objective == "minimize":
            score = failure_aware_minimization_score(
                predicted_value,
                uncertainty,
                failure_risk,
                exploration_weight,
                failure_penalty,
            )
        else:
            score = failure_aware_maximization_score(
                predicted_value,
                uncertainty,
                failure_risk,
                exploration_weight,
                failure_penalty,
            )
        item = dict(candidate)
        item["failure_aware_score"] = score
        scored.append(item)

    reverse = objective == "maximize"
    return sorted(scored, key=lambda item: float(item["failure_aware_score"]), reverse=reverse)


def _bounded_risk(value: float) -> float:
    return max(0.0, min(1.0, float(value)))

