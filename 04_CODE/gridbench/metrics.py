"""Point- and event-level metrics for rare injected anomalies.

Undefined metrics (e.g., AP with no positives, precision with no alerts) are NaN,
never 0 or 1, and are reported as such."""
from __future__ import annotations

import numpy as np
from sklearn.metrics import average_precision_score, roc_auc_score, roc_curve


def label_free_threshold(val_scores: np.ndarray, alert_rate: float) -> float:
    """Threshold = (1 - alert_rate) quantile of validation scores (no labels used)."""
    v = val_scores[~np.isnan(val_scores)]
    return float(np.quantile(v, 1.0 - alert_rate, method="higher"))


def ranking_metrics(score: np.ndarray, y: np.ndarray, fpr_target: float) -> dict:
    n_pos, n_neg = int(y.sum()), int((~y).sum())
    out = {"n_eval": int(len(y)), "n_pos": n_pos, "prevalence": n_pos / len(y) if len(y) else np.nan}
    if n_pos == 0 or n_neg == 0:
        out.update(ap=np.nan, auroc=np.nan, tpr_at_fpr=np.nan)
        return out
    out["ap"] = float(average_precision_score(y, score))
    out["auroc"] = float(roc_auc_score(y, score))
    fpr, tpr, _ = roc_curve(y, score)
    out["tpr_at_fpr"] = float(tpr[fpr <= fpr_target].max())
    return out


def operating_metrics(score: np.ndarray, y: np.ndarray, thr: float, hours: int) -> dict:
    alert = score >= thr
    tp = int((alert & y).sum()); fp = int((alert & ~y).sum()); fn = int((~alert & y).sum())
    prec = tp / (tp + fp) if (tp + fp) > 0 else np.nan
    rec = tp / (tp + fn) if (tp + fn) > 0 else np.nan
    f1 = 2 * tp / (2 * tp + fp + fn) if (tp + fn) > 0 else np.nan
    n_neg = int((~y).sum())
    return {"threshold": thr, "alerts": int(alert.sum()), "tp": tp, "fp": fp, "fn": fn,
            "precision": prec, "recall": rec, "f1": f1,
            "fpr": fp / n_neg if n_neg else np.nan,
            "false_alerts_per_week": fp / (hours / 168.0) if hours else np.nan}


def event_metrics(score_full: np.ndarray, label_full: np.ndarray, eligible_full: np.ndarray,
                  events, thr: float) -> list[dict]:
    """Per-event detection: an event is detected if any of its altered, scored hours
    raises an alert; delay = hours from first altered hour to first alert."""
    rows = []
    for e in events:
        w = np.arange(e.start, e.start + e.length)
        w = w[label_full[w] & eligible_full[w]]
        if len(w) == 0:
            rows.append({"event_id": e.event_id, "family": e.family, "tier": e.tier, "scored_hours": 0,
                         "detected": np.nan, "delay_h": np.nan})
            continue
        hit = w[score_full[w] >= thr]
        rows.append({"event_id": e.event_id, "family": e.family, "tier": e.tier, "scored_hours": int(len(w)),
                     "detected": float(len(hit) > 0), "delay_h": float(hit[0] - w[0]) if len(hit) else np.nan,
                     "max_score": float(np.max(score_full[w]))})
    return rows
