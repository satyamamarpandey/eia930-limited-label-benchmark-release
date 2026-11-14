"""Experiment orchestration: one *cell* = (authority, seed, missingness condition,
experiment variant). Within a cell every detector sees the same observed series,
the same eligible hours and the same injected events (matched comparisons)."""
from __future__ import annotations

import hashlib
import itertools
import time
from dataclasses import dataclass

import numpy as np
import pandas as pd

from . import features as feat
from . import inject, io, metrics
from .detectors import IForestDetector, PULogisticDetector, RobustSeasonalDetector, sample_label_budget

FEATURE_SETS = {
    "full": feat.ALL_FEATURES,
    "no_residual": feat.BASE_FEATURES + feat.MISSING_FEATURES,
    "no_missing_ind": feat.RESIDUAL_FEATURES + feat.BASE_FEATURES,
}


@dataclass
class BAContext:
    ba: str
    ba_idx: int
    index: pd.DatetimeIndex
    x: np.ndarray            # reported demand, NaN where naturally invalid
    valid: np.ndarray
    hour: np.ndarray
    dow: np.ndarray
    split_of: np.ndarray     # 'train' / 'val' / 'test'
    split_pos: dict
    warm: np.ndarray         # True during warm-up
    suspect: np.ndarray      # natural-suspect audit flag (evaluation sensitivity only)


def make_context(df: pd.DataFrame, ba: str, ba_idx: int, cfg: dict) -> BAContext:
    s = io.build_series(df, ba)
    hour, dow = feat.local_calendar(s["local_end"])
    idx = s.index
    split_of = np.full(len(idx), "", dtype=object)
    split_pos = {}
    for name, (lo, hi) in cfg["splits"].items():
        m = (idx >= pd.Timestamp(lo)) & (idx <= pd.Timestamp(hi))
        split_of[m] = name
        pos = np.flatnonzero(m)
        split_pos[name] = (int(pos[0]), int(pos[-1]))
    if (split_of == "").any():
        raise ValueError(f"{ba}: hours outside all splits")
    warm = np.arange(len(idx)) < cfg["warmup_hours"]
    x = s["demand"].to_numpy(dtype=float)
    return BAContext(ba, ba_idx, idx, x, ~np.isnan(x), hour, dow, split_of, split_pos, warm,
                     s["natural_suspect"].to_numpy(dtype=bool))


def injected(ctx: BAContext, seed: int, cfg: dict, n_train: int):
    epf = dict(cfg["injection"]["events_per_family"])
    epf["train"] = n_train
    rng = inject.make_rng(seed, ctx.ba_idx, inject.STREAM_EVENTS, n_train)
    events = inject.place_events(ctx.valid, ctx.split_pos, cfg["injection"], epf, rng)
    x_inj, label, owner = inject.apply_events(ctx.x, events)
    return events, x_inj, label, owner


def observed(ctx: BAContext, x_inj, owner, seed: int, cond_idx: int, cond: dict, cfg: dict):
    rng = inject.make_rng(seed, ctx.ba_idx, inject.STREAM_MISSING, cond_idx)
    # v1.1: masks are independent of injections (protecting event windows, as in v1.0,
    # made the missingness indicators predictive of the label)
    protect = (owner >= 0) if cfg["missingness"].get("protect_injected_hours", False) else np.zeros(len(owner), bool)
    mask = inject.background_missingness(ctx.valid, protect, cond["rate"], cond["mechanism"],
                                         tuple(cfg["missingness"]["block_length"]), rng)
    x_obs = x_inj.copy()
    x_obs[mask] = np.nan
    return x_obs, mask


def _fam_array(events, owner):
    fam = np.array([""] * len(owner), dtype=object)
    tier = np.array([""] * len(owner), dtype=object)
    for e in events:
        w = owner == e.event_id
        fam[w] = e.family
        tier[w] = e.tier
    return fam, tier


def evaluate_scores(s, label, scored, split_of, events, fam_h, tier_h, cfg, eval_split, suspect=None):
    """All metrics for one score vector. Thresholds come from validation scores only."""
    val = scored & (split_of == "val")
    ev = scored & (split_of == eval_split)
    tcfg = cfg["thresholds"]
    out = {}
    y = label[ev]
    out.update(metrics.ranking_metrics(s[ev], y, tcfg["ranking_fpr"]))
    for fam in inject.FAMILIES:
        m = ev & (~label | (fam_h == fam))
        r = metrics.ranking_metrics(s[m], label[m], tcfg["ranking_fpr"])
        out[f"ap_{fam}"] = r["ap"]
        out[f"npos_{fam}"] = r["n_pos"]
    for t in inject.TIERS:
        m = ev & (~label | (tier_h == t))
        out[f"ap_tier_{t}"] = metrics.ranking_metrics(s[m], label[m], tcfg["ranking_fpr"])["ap"]
    if suspect is not None:
        # sensitivity: drop naturally suspicious unlabeled hours from the negatives
        m = ev & ~(suspect & ~label)
        out["n_suspect_neg"] = int((ev & suspect & ~label).sum())
        out["ap_excl_suspect"] = metrics.ranking_metrics(s[m], label[m], tcfg["ranking_fpr"])["ap"]
    ev_events = [e for e in events if e.split == eval_split]
    if eval_split == "test":
        rates = [tcfg["primary_alert_rate"]] + list(tcfg["sensitivity_alert_rates"])
        for k, rate in enumerate(rates):
            thr = metrics.label_free_threshold(s[val], rate)
            om = metrics.operating_metrics(s[ev], y, thr, int(ev.sum()))
            erows = metrics.event_metrics(s, label, scored, ev_events, thr)
            det = np.array([r["detected"] for r in erows], dtype=float)
            tag = "" if k == 0 else f"_at{rate:g}"
            if k == 0:
                out.update(om)
                if suspect is not None:
                    out["fp_on_suspect"] = int((ev & suspect & ~label & (s >= thr)).sum())
                out["event_detection_rate"] = float(np.nanmean(det))
                out["event_delay_h_mean"] = float(np.nanmean([r["delay_h"] for r in erows])) if np.any(det == 1) else np.nan
                for fam in inject.FAMILIES:
                    d = [r["detected"] for r in erows if r["family"] == fam]
                    out[f"edr_{fam}"] = float(np.nanmean(d)) if len(d) else np.nan
                for t in inject.TIERS:
                    d = [r["detected"] for r in erows if r["tier"] == t]
                    out[f"edr_tier_{t}"] = float(np.nanmean(d)) if len(d) else np.nan
                out["_event_rows"] = erows
            else:
                out[f"recall{tag}"] = om["recall"]
                out[f"precision{tag}"] = om["precision"]
                out[f"false_alerts_per_week{tag}"] = om["false_alerts_per_week"]
                out[f"event_detection_rate{tag}"] = float(np.nanmean(det))
    return out


def run_cell(ctx: BAContext, seed: int, cond_idx: int, cond: dict, cfg: dict, variant: dict,
             eval_split: str, keep_scores: bool = False):
    """Run all detectors of one experiment variant on one cell."""
    n_train = variant.get("n_train", cfg["injection"]["events_per_family"]["train"])
    events, x_inj, label, owner = injected(ctx, seed, cfg, n_train)
    x_obs, miss = observed(ctx, x_inj, owner, seed, cond_idx, cond, cfg)
    F = feat.compute_features(x_obs, ctx.hour, ctx.dow, cfg["features"])
    scored = ~np.isnan(x_obs)
    train_rows = np.flatnonzero(scored & (ctx.split_of == "train") & ~ctx.warm)
    F_train = F.iloc[train_rows].reset_index(drop=True)
    fam_h, tier_h = _fam_array(events, owner)
    ev_family = {e.event_id: e.family for e in events}
    fset = variant.get("feature_set", "full")
    cols = FEATURE_SETS[fset]
    mcfg = cfg["methods"]
    regime = variant.get("regime", "default")
    methods = variant.get("methods", ["stat", "iforest", "pu"])
    budgets = variant.get("budgets", mcfg["label_budgets"])
    draws = range(cfg["label_draws_per_seed"])
    u_share = variant.get("u_share", mcfg["pu_logreg"]["unlabeled_weight_share"])
    excl = variant.get("exclude_families")
    common = {"experiment": variant["name"], "ba": ctx.ba, "seed": seed, "condition": cond["name"],
              "miss_rate": cond["rate"], "miss_mechanism": cond["mechanism"], "feature_set": fset,
              "regime": regime, "n_train_events_per_family": n_train, "eval_split": eval_split,
              "masked_hours_train": int((miss & (ctx.split_of == "train")).sum()),
              "masked_hours_val": int((miss & (ctx.split_of == "val")).sum()),
              "masked_hours_test": int((miss & (ctx.split_of == "test")).sum()),
              "train_rows": int(len(train_rows)),
              "train_contamination_hours": int(label[train_rows].sum())}
    rows, event_rows, scores = [], [], {}

    def record(method, s, extra, fit_s):
        t0 = time.perf_counter()
        res = evaluate_scores(s, label, scored, ctx.split_of, events, fam_h, tier_h, cfg, eval_split, ctx.suspect)
        erows = res.pop("_event_rows", [])
        row = {**common, "method": method, **extra, **res, "fit_seconds": fit_s,
               "eval_seconds": time.perf_counter() - t0}
        rows.append(row)
        for r in erows:
            event_rows.append({**{k: common[k] for k in ("experiment", "ba", "seed", "condition", "regime", "feature_set")},
                               "method": method, **{k: extra.get(k) for k in ("budget", "draw")}, **r})
        if keep_scores:
            key = method if extra.get("budget") is None else f"{method}_B{extra['budget']}_d{extra['draw']}"
            scores[key] = s.astype(np.float32)

    val_rows = scored & (ctx.split_of == "val")

    def val_ap(s):
        return metrics.ranking_metrics(s[val_rows], label[val_rows], cfg["thresholds"]["ranking_fpr"])["ap"]

    # --- Method A: robust seasonal statistics
    if "stat" in methods:
        grid = [mcfg["stat"]["components"]] if regime == "default" else cfg["tuning"]["stat"]["components"]
        best = None
        for comps in grid:
            t0 = time.perf_counter()
            det = RobustSeasonalDetector(comps).fit(F_train)
            s = det.score(F)
            fit_s = time.perf_counter() - t0
            sel = val_ap(s) if regime == "tuned" else 0.0
            if best is None or sel > best[0]:
                best = (sel, s, {"hp": "+".join(comps), "budget": None, "draw": None, "val_ap_select": sel}, fit_s)
        record("stat", best[1], best[2], best[3])

    # --- Method B: Isolation Forest
    if "iforest" in methods:
        ic = mcfg["iforest"]
        if regime == "default":
            grid = [(ic["n_estimators"], ic["max_samples"], ic["max_features"])]
        else:
            tg = cfg["tuning"]["iforest"]
            grid = list(itertools.product(tg["n_estimators"], tg["max_samples"], tg["max_features"]))
        best = None
        for ne, ms, mf in grid:
            t0 = time.perf_counter()
            det = IForestDetector(cols, ne, ms, mf, random_state=seed * 100 + ctx.ba_idx).fit(F_train)
            s = det.score(F)
            fit_s = time.perf_counter() - t0
            sel = val_ap(s) if regime == "tuned" else 0.0
            if best is None or sel > best[0]:
                best = (sel, s, {"hp": f"n={ne},ms={ms},mf={mf}", "budget": None, "draw": None,
                                 "val_ap_select": sel}, fit_s)
        record("iforest", best[1], best[2], best[3])

    # --- Method C: budgeted PU logistic regression
    if "pu" in methods:
        pc = mcfg["pu_logreg"]
        Cgrid = [pc["C"]] if regime == "default" else cfg["tuning"]["pu_logreg"]["C"]
        mname = "pu" if u_share > 0 else "labels_only"
        for B in budgets:
            cand = {}
            for C in Cgrid:
                res = []
                for d in draws:
                    rng = inject.make_rng(seed, ctx.ba_idx, inject.STREAM_LABELS, B, d,
                                          0 if excl is None else 1 + inject.FAMILIES.index(excl[0]))
                    pos, neg, unl = sample_label_budget(B, label, owner, train_rows, rng,
                                                        exclude_families=excl, event_family=ev_family)
                    t0 = time.perf_counter()
                    det = PULogisticDetector(cols, C=C, unlabeled_weight_share=u_share,
                                             max_iter=pc["max_iter"]).fit(F_train, pos, neg, unl)
                    s = det.score(F)
                    fit_s = time.perf_counter() - t0
                    lab_train = label[train_rows]
                    acct = {"budget": B, "draw": d, "hp": f"C={C}", "n_label_pos": int(len(pos)),
                            "n_label_neg": int(len(neg)), "n_verified_labels": int(len(pos) + len(neg)),
                            "n_weak_unlabeled": int(len(unl)) if u_share > 0 else 0,
                            "weak_negatives_contaminated": int(lab_train[unl].sum()) if u_share > 0 else 0,
                            "label_pos_correct": bool(lab_train[pos].all()),
                            "label_neg_correct": bool((~lab_train[neg]).all()),
                            "pos_families": "|".join(sorted({fam_h[train_rows[p]] for p in pos})),
                            "lr_n_iter": det.n_iter_}
                    res.append((s, acct, fit_s))
                sel = float(np.mean([val_ap(r[0]) for r in res])) if regime == "tuned" else 0.0
                cand[C] = (sel, res)
            Cbest = max(cand, key=lambda c: cand[c][0])
            for s, acct, fit_s in cand[Cbest][1]:
                record(mname, s, {**acct, "val_ap_select": cand[Cbest][0]}, fit_s)

    ev_df = inject.events_frame(events, ctx.index, ba=ctx.ba, seed=seed, n_train_events_per_family=n_train)
    blob = None
    if keep_scores:
        blob = {"scores": scores, "label": label, "scored": scored, "owner": owner, "split_of": ctx.split_of,
                "x_obs": x_obs, "x_orig": ctx.x, "missing_mask": miss, "suspect": ctx.suspect,
                "utc_index": ctx.index.as_unit("s").asi8}
    mask_hash = hashlib.sha256(miss.tobytes()).hexdigest()[:16]
    for r in rows:
        r["missing_mask_sha16"] = mask_hash
    return rows, event_rows, ev_df, blob
