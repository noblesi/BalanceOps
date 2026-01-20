from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class PromoteDecision:
    should_promote: bool
    reason: str


def should_promote(candidate: dict, current: dict | None) -> PromoteDecision:
    # current가 없으면 최초 승격
    if not current:
        return PromoteDecision(True, "no current model yet")

    cand_bal = float(candidate.get("bal_acc", 0.0))
    curr_bal = float(current.get("bal_acc", 0.0))

    cand_rec = float(candidate.get("recall_1", 0.0))
    curr_rec = float(current.get("recall_1", 0.0))

    # 예시 규칙: bal_acc는 +0.005 이상 개선, recall은 -0.01 이상 악화되면 승격 금지
    if cand_bal >= curr_bal + 0.005 and cand_rec >= curr_rec - 0.01:
        return PromoteDecision(True, f"improved bal_acc {curr_bal:.4f}->{cand_bal:.4f}")
    return PromoteDecision(False, f"not enough improvement (bal {curr_bal:.4f}->{cand_bal:.4f}, rec {curr_rec:.4f}->{cand_rec:.4f})")
