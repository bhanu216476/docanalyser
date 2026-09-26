"""
Answer correctness evaluation metric.

Evaluates generated answers against ground truth using normalized token
overlap, semantic token F1, and abstention compliance.
"""

from __future__ import annotations

import re
import string


def _normalize_text(text: str) -> str:
    """Normalize text by lowering, removing punctuation, and stripping whitespace."""
    text = text.lower()
    # Remove citations like [1], [2], [doc:1]
    text = re.sub(r"\[[^\]]+\]", " ", text)
    # Remove punctuation
    text = text.translate(str.maketrans("", "", string.punctuation))
    # Normalize whitespace
    return " ".join(text.split())


def _token_f1_score(prediction: str, ground_truth: str) -> float:
    """Compute token-level F1 score between prediction and ground truth."""
    pred_tokens = _normalize_text(prediction).split()
    gt_tokens = _normalize_text(ground_truth).split()

    if not pred_tokens and not gt_tokens:
        return 1.0
    if not pred_tokens or not gt_tokens:
        return 0.0

    common_tokens = set(pred_tokens) & set(gt_tokens)
    if not common_tokens:
        return 0.0

    precision = sum(1 for t in pred_tokens if t in common_tokens) / len(pred_tokens)
    recall = sum(1 for t in gt_tokens if t in common_tokens) / len(gt_tokens)

    if precision + recall == 0:
        return 0.0

    return 2.0 * (precision * recall) / (precision + recall)


def evaluate_answer_correctness(
    generated_answer: str,
    ground_truth_answer: str,
    answerable: bool = True,
) -> float:
    """
    Determine whether generated answer matches ground-truth answer.

    For answerable=False:
        Returns 1.0 if the answer correctly abstains, 0.0 if it hallucinates an answer.
    For answerable=True:
        Returns harmonic combination of exact containment and token F1.
    """
    if not answerable:
        from evals.metrics.no_answer import is_abstention

        return 1.0 if is_abstention(generated_answer) else 0.0

    if not ground_truth_answer.strip():
        return 1.0 if not generated_answer.strip() else 0.0

    norm_gen = _normalize_text(generated_answer)
    norm_gt = _normalize_text(ground_truth_answer)

    # Exact or full substring match
    if norm_gt in norm_gen:
        return 1.0

    # Token F1 score
    f1 = _token_f1_score(generated_answer, ground_truth_answer)
    return round(f1, 4)
