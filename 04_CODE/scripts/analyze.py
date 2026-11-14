"""Aggregate raw final results into tables, paired comparisons, ablations and error analysis.

Inputs : 05_RESULTS/final/raw/*  (never modified)
Outputs: 05_RESULTS/final/tables/*.csv, 05_RESULTS/final/key_numbers.json
Usage  : python scripts/analyze.py [--results 05_RESULTS/final]
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd

CODE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(CODE))
from gridbench import inject  # noqa: E402
from gridbench.config import load_config, project_paths  # noqa: E402
from gridbench.stats import cell_means, hier_bootstrap, method_label, paired_difference, sign_flip_p  # noqa: E402

METHODS = ["stat", "iforest", "pu_B8", "pu_B32", "pu_B128"]
NAMES = {"stat": "Robust seasonal (A)", "iforest": "Isolation Forest (B)", "pu_B8": "PU-LR, B=8 (C)",
         "pu_B32": "PU-LR, B=32 (C)", "pu_B128": "PU-LR, B=128 (C)"}
COND = ["none", "mcar5", "mcar15", "block5", "block15"]
TZ = {"CISO": "America/Los_Angeles", "ERCO": "America/Chicago", "NYIS": "America/New_York",
      "PJM": "America/New_York", "SWPP": "America/Chicago"}
# U.S. federal holidays in the test period (2024) plus Dec 24 / Dec 31 (commonly low-load days)
HOLIDAYS = {"2024-09-02": "Labor Day", "2024-10-14": "Columbus Day", "2024-11-11": "Veterans Day",
            "2024-11-28": "Thanksgiving", "2024-11-29": "Day after Thanksgiving", "2024-12-24": "Christmas Eve",
            "2024-12-25": "Christmas", "2024-12-31": "New Year's Eve"}
DST_DAY = "2024-11-03"


def utc_index(paths, ba: str, n: int) -> pd.DatetimeIndex:
    """Exact hour-ending UTC index of a saved score file, rebuilt from the source
    manifest (the `utc_index` field stored in the score files is truncated; see
    06_AUDIT and 06_AUDIT/protocol/PROTOCOL_CHANGES.md)."""
    man = json.loads((paths["data"] / "dataset_manifest.json").read_text())
    return pd.date_range(man["integrity"][ba]["utc_end_first"], periods=n, freq="h")


def ba_balanced(cm: pd.DataFrame, col: str) -> float:
    """Mean over authorities of the mean over seeds (equal authority weight)."""
    return float(cm.groupby(["ba"])[col].mean().mean())


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--results", default="05_RESULTS/final", help="relative to the final project folder")
    args = ap.parse_args()
    cfg = load_config()
    paths = project_paths(cfg)
    R = paths["root"] / args.results
    raw, out = R / "raw", R / "tables"
    out.mkdir(exist_ok=True)
    reps, bseed = cfg["ablations"]["bootstrap_reps"], cfg["ablations"]["bootstrap_seed"]
    K = {}

    prim = pd.read_csv(raw / "runs_primary.csv")
    prim["mlabel"] = method_label(prim)
    metric_cols = [c for c in prim.columns if prim[c].dtype.kind in "fiu" and c not in
                   ("seed", "miss_rate", "budget", "draw", "threshold", "val_ap_select", "fit_seconds",
                    "eval_seconds")]
    cm = cell_means(prim, metric_cols)
    cm.to_csv(out / "primary_cell_means.csv", index=False)

    # ---------------- design / prevalence facts
    one = prim[prim.mlabel == "stat"]
    K["n_cells_primary"] = int(len(one))
    K["n_result_rows_primary"] = int(len(prim))
    K["test_prevalence_mean"] = float(one[one.condition == "none"]["prevalence"].mean())
    K["test_prevalence_min"] = float(one["prevalence"].min())
    K["test_prevalence_max"] = float(one["prevalence"].max())
    K["test_pos_hours_mean"] = float(one[one.condition == "none"]["n_pos"].mean())
    K["test_eval_hours_none_mean"] = float(one[one.condition == "none"]["n_eval"].mean())
    inj = pd.read_csv(raw / "injection_ground_truth.csv")
    inj6 = inj[inj.n_train_events_per_family == cfg["injection"]["events_per_family"]["train"]]
    K["n_injected_events_primary"] = int(len(inj6))
    K["n_test_events_primary"] = int((inj6.split == "test").sum())
    K["n_altered_hours_test"] = int(inj6[inj6.split == "test"]["n_altered"].sum())
    K["n_window_hours_test"] = int(inj6[inj6.split == "test"]["length"].sum())
    K["train_contamination_frac_mean"] = float((one["train_contamination_hours"] / one["train_rows"]).mean())
    pu = prim[prim.method == "pu"]
    K["label_accounting_all_correct"] = bool(pu.label_pos_correct.all() and pu.label_neg_correct.all()
                                             and (pu.n_verified_labels == pu.budget).all())
    K["weak_neg_contam_frac_mean"] = float((pu.weak_negatives_contaminated / pu.n_weak_unlabeled).mean())
    K["weak_neg_n_mean"] = float(pu.n_weak_unlabeled.mean())
    inj6.groupby(["split", "family", "tier"]).agg(events=("event_id", "count"), mean_len=("length", "mean"),
                                                   altered=("n_altered", "sum")).to_csv(out / "injection_summary.csv")

    # ---------------- main table (no added missingness)
    rows = []
    none = cm[cm.condition == "none"]
    for m in METHODS:
        d = none[none.mlabel == m]
        row = {"method": m, "name": NAMES[m]}
        for col in ["ap", "auroc", "tpr_at_fpr", "precision", "recall", "f1", "false_alerts_per_week",
                    "event_detection_rate", "event_delay_h_mean", "ap_excl_suspect", "fp_on_suspect", "fp"]:
            row[col] = ba_balanced(d, col)
        for col in ["ap", "f1", "event_detection_rate", "auroc"]:
            p, lo, hi = hier_bootstrap(d[["ba", "seed", col]], col, reps, bseed)
            row[col + "_lo"], row[col + "_hi"] = lo, hi
        rows.append(row)
    main_t = pd.DataFrame(rows)
    main_t.to_csv(out / "table_main_none.csv", index=False)
    for _, r in main_t.iterrows():
        for col in main_t.columns:
            if col not in ("method", "name"):
                K[f"main_{r['method']}_{col}"] = float(r[col])

    # ---------------- by condition
    rows = []
    for m in METHODS:
        for c in COND:
            d = cm[(cm.mlabel == m) & (cm.condition == c)]
            p, lo, hi = hier_bootstrap(d[["ba", "seed", "ap"]], "ap", reps, bseed)
            pa, alo, ahi = hier_bootstrap(d[["ba", "seed", "auroc"]], "auroc", reps, bseed)
            dl = d.assign(lift=d["ap"] / d["prevalence"])
            rows.append({"method": m, "condition": c, "ap": p, "ap_lo": lo, "ap_hi": hi,
                         "auroc": pa, "auroc_lo": alo, "auroc_hi": ahi,
                         "prevalence": ba_balanced(d, "prevalence"), "ap_lift": ba_balanced(dl, "lift"),
                         "f1": ba_balanced(d, "f1"), "edr": ba_balanced(d, "event_detection_rate"),
                         "fa_week": ba_balanced(d, "false_alerts_per_week")})
            K[f"cond_{m}_{c}_auroc"], K[f"cond_{m}_{c}_ap_lift"] = pa, rows[-1]["ap_lift"]
            K[f"cond_{m}_{c}_prevalence"] = rows[-1]["prevalence"]
            K[f"cond_{m}_{c}_ap"] = p
            K[f"cond_{m}_{c}_ap_lo"], K[f"cond_{m}_{c}_ap_hi"] = lo, hi
            K[f"cond_{m}_{c}_edr"] = rows[-1]["edr"]
    pd.DataFrame(rows).to_csv(out / "table_by_condition.csv", index=False)

    # ---------------- per authority (none)
    per_ba = none.groupby(["mlabel", "ba"])[["ap", "prevalence", "false_alerts_per_week",
                                             "event_detection_rate"]].mean().reset_index()
    per_ba.to_csv(out / "table_per_ba_none.csv", index=False)
    for _, r in per_ba.iterrows():
        K[f"ba_{r['mlabel']}_{r['ba']}_ap"] = float(r["ap"])
    fam_ba = none.groupby(["mlabel", "ba"])[[f"ap_{f}" for f in inject.FAMILIES]
                                            + [f"edr_{f}" for f in inject.FAMILIES]].mean().reset_index()
    fam_ba.to_csv(out / "table_per_ba_family_none.csv", index=False)
    for _, r in fam_ba.iterrows():
        for f in inject.FAMILIES:
            K[f"bafam_{r['mlabel']}_{r['ba']}_{f}_ap"] = float(r[f"ap_{f}"])
            K[f"bafam_{r['mlabel']}_{r['ba']}_{f}_edr"] = float(r[f"edr_{f}"])
    best_by_ba = per_ba[per_ba.mlabel.isin(METHODS)].loc[lambda x: x.groupby("ba")["ap"].idxmax()]
    K["best_method_by_ba"] = dict(zip(best_by_ba.ba, best_by_ba.mlabel))

    # ---------------- per family / tier (none)
    rows = []
    for m in METHODS:
        d = none[none.mlabel == m]
        r = {"method": m}
        for f in inject.FAMILIES:
            r[f"ap_{f}"] = ba_balanced(d, f"ap_{f}")
            r[f"edr_{f}"] = ba_balanced(d, f"edr_{f}")
            K[f"fam_{m}_{f}_ap"], K[f"fam_{m}_{f}_edr"] = r[f"ap_{f}"], r[f"edr_{f}"]
        for t in inject.TIERS:
            r[f"ap_tier_{t}"] = ba_balanced(d, f"ap_tier_{t}")
            r[f"edr_tier_{t}"] = ba_balanced(d, f"edr_tier_{t}")
            K[f"tier_{m}_{t}_ap"], K[f"tier_{m}_{t}_edr"] = r[f"ap_tier_{t}"], r[f"edr_tier_{t}"]
        rows.append(r)
    pd.DataFrame(rows).to_csv(out / "table_family_tier_none.csv", index=False)
    fam_prev = {}
    for f in inject.FAMILIES:
        d = prim[(prim.mlabel == "stat") & (prim.condition == "none")]
        fam_prev[f] = float((d[f"npos_{f}"] / (d["n_eval"] - d["n_pos"] + d[f"npos_{f}"])).mean())
        K[f"fam_prev_{f}"] = fam_prev[f]

    # event-level by family x tier (none), from raw event detections
    ev = pd.read_csv(raw / "event_detections_primary.csv")
    ev["mlabel"] = method_label(ev)
    evn = ev[ev.condition == "none"]
    ft = evn.groupby(["mlabel", "family", "tier"]).agg(detected=("detected", "mean"),
                                                       delay=("delay_h", "mean"), n=("detected", "size")).reset_index()
    ft.to_csv(out / "table_event_family_tier_none.csv", index=False)
    K["n_test_event_evaluations_per_method_none"] = int(evn[evn.mlabel == "stat"].shape[0])

    # ---------------- paired comparisons
    pairs = [("pu_B128", "stat"), ("pu_B32", "stat"), ("pu_B8", "stat"), ("iforest", "stat"),
             ("pu_B128", "iforest"), ("pu_B128", "pu_B8"), ("pu_B32", "pu_B8"), ("pu_B128", "pu_B32")]
    rows = []
    for a, b in pairs:
        for conds, tag in ((["none"], "none"), (None, "all")):
            for metric in ("ap", "event_detection_rate"):
                r = paired_difference(cm, a, b, metric, reps, bseed, conds)
                rows.append(r)
                K[f"pair_{a}_vs_{b}_{tag}_{metric}"] = {k: r[k] for k in ("mean_diff", "ci_lo", "ci_hi",
                                                                        "n_ba_positive", "sign_flip_p")}
    pd.DataFrame(rows).to_csv(out / "table_paired_differences.csv", index=False)

    # missingness effect: paired within method, condition c minus none
    rows = []
    for m, metric in [(m, mt) for mt in ("ap", "auroc") for m in METHODS]:
        d = cm[cm.mlabel == m].pivot_table(index=["ba", "seed"], columns="condition", values=metric).reset_index()
        for c in COND[1:]:
            dd = d[["ba", "seed"]].copy()
            dd["diff"] = d[c] - d["none"]
            p, lo, hi = hier_bootstrap(dd, "diff", reps, bseed)
            bam = dd.groupby("ba")["diff"].mean()
            rows.append({"method": m, "metric": metric, "condition": c, "mean_diff": p, "ci_lo": lo, "ci_hi": hi,
                         "n_ba_negative": int((bam < 0).sum()), "sign_flip_p": sign_flip_p(bam.to_numpy())})
            K[f"missdiff_{metric}_{m}_{c}"] = {"mean_diff": p, "ci_lo": lo, "ci_hi": hi, "n_ba_negative": int((bam < 0).sum())}
    pd.DataFrame(rows).to_csv(out / "table_missingness_effect.csv", index=False)

    # ---------------- threshold sensitivity (none)
    rows = []
    for m in METHODS:
        d = none[none.mlabel == m]
        r = {"method": m}
        for tag, rate in (("_at0.01", 0.01), ("", 0.02), ("_at0.05", 0.05)):
            r[f"recall@{rate}"] = ba_balanced(d, f"recall{tag}")
            r[f"precision@{rate}"] = ba_balanced(d, f"precision{tag}")
            r[f"fa_week@{rate}"] = ba_balanced(d, f"false_alerts_per_week{tag}")
            r[f"edr@{rate}"] = ba_balanced(d, f"event_detection_rate{tag}")
            for k in ("recall", "precision", "fa_week", "edr"):
                K[f"thr_{m}_{rate}_{k}"] = r[f"{k}@{rate}"]
        rows.append(r)
    pd.DataFrame(rows).to_csv(out / "table_threshold_sensitivity.csv", index=False)
    K["realized_test_alert_rate"] = {m: float((none[none.mlabel == m]["alerts"]
                                               / none[none.mlabel == m]["n_eval"]).mean()) for m in METHODS}

    # ---------------- ablations (matched cells)
    abl_rows = []

    def ablation(name, variant_file, base_df, labels, conds, metric="ap", note=""):
        f = raw / f"runs_{variant_file}.csv"
        a = pd.read_csv(f)
        a["mlabel"] = method_label(a)
        acm = cell_means(a, [metric])
        for lab_a, lab_b in labels:
            for c in conds:
                x = acm[(acm.mlabel == lab_a) & (acm.condition == c)].set_index(["ba", "seed"])[metric]
                y = base_df[(base_df.mlabel == lab_b) & (base_df.condition == c)].set_index(["ba", "seed"])[metric]
                j = pd.concat([x.rename("x"), y.rename("y")], axis=1, join="inner").reset_index()
                j["diff"] = j["x"] - j["y"]
                p, lo, hi = hier_bootstrap(j, "diff", reps, bseed)
                bam = j.groupby("ba")["diff"].mean()
                r = {"ablation": name, "variant_method": lab_a, "reference_method": lab_b, "condition": c,
                     "metric": metric, "variant_mean": ba_balanced(j, "x"), "reference_mean": ba_balanced(j, "y"),
                     "mean_diff": p, "ci_lo": lo, "ci_hi": hi, "n_ba_positive": int((bam > 0).sum()),
                     "n_cells": int(len(j)), "note": note}
                abl_rows.append(r)
                K[f"abl_{name}_{lab_a}_{c}_{metric}"] = {k: r[k] for k in ("variant_mean", "reference_mean",
                                                                         "mean_diff", "ci_lo", "ci_hi", "n_ba_positive")}

    ablation("no_residual", "abl_no_residual", cm, [("iforest", "iforest"), ("pu_B32", "pu_B32"),
                                                    ("pu_B128", "pu_B128")], ["none", "mcar15", "block15"])
    ablation("no_missing_ind", "abl_no_missing_ind", cm, [("iforest", "iforest"), ("pu_B32", "pu_B32"),
                                                          ("pu_B128", "pu_B128")], ["none", "mcar15", "block15"])
    # post-hoc (added at final review): matched difference-in-differences separating the part of the
    # missingness-induced AP change that is attributable to the missingness-indicator features:
    # did = (full[c] - full[none]) - (no_ind[c] - no_ind[none]), per (ba, seed), cluster bootstrap.
    ni = pd.read_csv(raw / "runs_abl_no_missing_ind.csv")
    ni["mlabel"] = method_label(ni)
    ni_cm = cell_means(ni, ["ap"])
    did_rows = []
    for m in ("iforest", "pu_B32", "pu_B128"):
        full_w = cm[cm.mlabel == m].pivot_table(index=["ba", "seed"], columns="condition", values="ap")
        noind_w = ni_cm[ni_cm.mlabel == m].pivot_table(index=["ba", "seed"], columns="condition", values="ap")
        for c in ("mcar15", "block15"):
            j = pd.concat([(full_w[c] - full_w["none"]).rename("loss_full"),
                           (noind_w[c] - noind_w["none"]).rename("loss_noind")], axis=1, join="inner").reset_index()
            j["did"] = j["loss_full"] - j["loss_noind"]
            p, lo, hi = hier_bootstrap(j[["ba", "seed", "did"]], "did", reps, bseed)
            pn, nlo, nhi = hier_bootstrap(j[["ba", "seed", "loss_noind"]], "loss_noind", reps, bseed)
            bam = j.groupby("ba")["did"].mean()
            r = {"method": m, "condition": c, "loss_full": ba_balanced(j, "loss_full"),
                 "loss_noind": pn, "loss_noind_ci_lo": nlo, "loss_noind_ci_hi": nhi,
                 "did": p, "did_ci_lo": lo, "did_ci_hi": hi, "n_ba_negative": int((bam < 0).sum()),
                 "sign_flip_p": sign_flip_p(bam.to_numpy()), "n_cells": int(len(j))}
            r["share_attributable"] = r["did"] / r["loss_full"] if r["loss_full"] else float("nan")
            did_rows.append(r)
            K[f"missind_did_{m}_{c}"] = {k: v for k, v in r.items() if k not in ("method", "condition")}
    pd.DataFrame(did_rows).to_csv(out / "table_missingness_indicator_did.csv", index=False)

    ablation("labels_only", "abl_labels_only", cm, [(f"labels_only_B{b}", f"pu_B{b}") for b in (8, 32, 128)],
             ["none", "mcar15"])
    for n in cfg["ablations"]["contamination_events_per_family"]:
        if n == cfg["injection"]["events_per_family"]["train"]:
            continue
        labs = [("stat", "stat"), ("iforest", "iforest"), ("pu_B8", "pu_B8"), ("pu_B32", "pu_B32")]
        if n >= 6:
            labs.append(("pu_B128", "pu_B128"))
        ablation(f"contam_{n}", f"contam_{n}", cm, labs, ["none"],
                 note="training and test injections both re-drawn (RNG stream keyed by training count); paired by authority and seed")
    ablation("tuned", "tuned", cm, [(m, m) for m in METHODS], COND, note="uses validation injection labels")
    for f in inject.FAMILIES:
        ablation(f"holdout_{f}", f"holdout_{f}", cm, [("pu_B32", "pu_B32")], ["none"], metric=f"ap_{f}",
                 note=f"positives exclude {f}; metric is AP on held-out family")
    pd.DataFrame(abl_rows).to_csv(out / "table_ablations.csv", index=False)

    # check that contamination variants share test events with primary
    ev_test = inj[inj.split == "test"].groupby("n_train_events_per_family").apply(
        lambda g: g[["ba", "seed", "family", "start", "length"]].sort_values(["ba", "seed", "start"]).to_numpy().tolist(),
        include_groups=False)
    K["contam_test_events_identical"] = bool(all(v == ev_test.iloc[0] for v in ev_test))

    # tuned hyperparameter choices
    tu = pd.read_csv(raw / "runs_tuned.csv")
    tu["mlabel"] = method_label(tu)
    tu[tu.draw.fillna(0) == 0].groupby(["mlabel", "hp"]).size().rename("n_cells").reset_index().to_csv(
        out / "tuned_hyperparameter_choices.csv", index=False)

    # ---------------- natural-suspect sensitivity
    K["suspect_neg_hours_test_by_ba"] = one[one.condition == "none"].groupby("ba")["n_suspect_neg"].mean().to_dict()
    for m in METHODS:
        d = none[none.mlabel == m]
        K[f"suspect_{m}_ap_excl"] = ba_balanced(d, "ap_excl_suspect")
        K[f"suspect_{m}_fp_on_suspect_share"] = float(d["fp_on_suspect"].sum() / max(d["fp"].sum(), 1))

    # ---------------- error analysis from saved scores (condition none)
    fp_rows, top_rows = [], []
    for ba in cfg["data"]["authorities"]:
        for seed in cfg["seeds"]:
            z = np.load(raw / "scores" / f"{ba}_s{seed}_none.npz", allow_pickle=True)
            utc = utc_index(paths, ba, len(z["label"]))
            loc = (utc - pd.Timedelta(hours=1)).tz_localize("UTC").tz_convert(ZoneInfo(TZ[ba]))
            ldate = loc.strftime("%Y-%m-%d")
            split, label, scored, owner, susp = z["split_of"], z["label"], z["scored"], z["owner"], z["suspect"]
            x_orig = z["x_orig"]
            ev_ = (split == "test") & scored
            val = (split == "val") & scored
            hol = np.isin(ldate, list(HOLIDAYS))
            dst = ldate == DST_DAY
            nat_inv = np.isnan(x_orig)
            near_inv = np.zeros(len(x_orig), bool)
            for i in np.flatnonzero(nat_inv):
                near_inv[i + 1:i + 25] = True
            near_inv &= ~nat_inv
            in_window = owner >= 0
            after_event = np.zeros(len(owner), bool)
            for e in np.unique(owner[owner >= 0]):
                last = np.flatnonzero(owner == e).max()
                after_event[last + 1:last + 169] = True  # 7 days in which seasonal lags still see the event
            after_event &= ~in_window
            keys = [k for k in z.files if k.startswith("score__")]
            for k in keys:
                m = k.replace("score__", "")
                ml = m if not m.startswith("pu_") else m.rsplit("_d", 1)[0].replace("pu_B", "pu_B")
                s = z[k].astype(float)
                thr = np.quantile(s[val], 1 - cfg["thresholds"]["primary_alert_rate"], method="higher")
                fp = ev_ & ~label & (s >= thr)
                neg = ev_ & ~label
                for cat, mask in (("holiday", hol), ("dst_day", dst), ("natural_suspect", susp),
                                  ("after_natural_gap_24h", near_inv), ("seasonal_echo_of_event", after_event),
                                  ("unaltered_hour_in_event_window", in_window), ("all", np.ones(len(s), bool))):
                    fp_rows.append({"ba": ba, "seed": seed, "method": ml, "category": cat,
                                    "neg_hours": int((neg & mask).sum()), "fp": int((fp & mask).sum())})
                if m in ("stat", "iforest", "pu_B32_d0"):
                    for i in np.flatnonzero(fp)[np.argsort(-s[fp])][:5]:
                        top_rows.append({"ba": ba, "seed": seed, "method": m, "utc_end": str(utc[i]),
                                         "local_date": ldate[i], "score": float(s[i]), "demand": float(x_orig[i]),
                                         "holiday": HOLIDAYS.get(ldate[i], ""), "natural_suspect": bool(susp[i]),
                                         "seasonal_echo": bool(after_event[i]), "after_gap": bool(near_inv[i])})
    fpd = pd.DataFrame(fp_rows).groupby(["method", "category"])[["neg_hours", "fp"]].sum().reset_index()
    fpd["fp_rate"] = fpd.fp / fpd.neg_hours.where(fpd.neg_hours > 0)
    base = fpd[fpd.category == "all"].set_index("method")["fp_rate"]
    fpd["rate_ratio_vs_all"] = fpd.apply(lambda r: r.fp_rate / base[r.method], axis=1)
    fpd.to_csv(out / "error_analysis_fp_categories.csv", index=False)
    pd.DataFrame(top_rows).to_csv(out / "error_analysis_top_false_positives.csv", index=False)
    for _, r in fpd.iterrows():
        K[f"fpcat_{r['method']}_{r['category']}"] = {"fp_rate": float(r.fp_rate) if pd.notna(r.fp_rate) else None,
                                                      "ratio": float(r.rate_ratio_vs_all) if pd.notna(r.rate_ratio_vs_all) else None,
                                                      "fp": int(r.fp), "neg_hours": int(r.neg_hours)}

    # ---------------- post-hoc exploratory (only if scripts/exploratory_swpp.py has been run)
    exp = R / "exploratory" / "swpp_weak_negative_cleaning.csv"
    if exp.exists():
        x = pd.read_csv(exp).groupby(["ba", "budget", "variant"])[["ap", "ap_flatline", "weak_negatives"]].mean()
        for (ba, b, v), r in x.iterrows():
            for c in ("ap", "ap_flatline", "weak_negatives"):
                K[f"exp_{ba}_B{b}_{v}_{c}"] = float(r[c])

    # ---------------- v1.0 leak diagnostic (archived protected-missingness run), reported in the amendment
    # (read directly from the stored evidence archive in 06_AUDIT/historical_evidence; never extracted)
    v10_zip, v10_member = paths["v1_0_archive"], "final_v1_0_protected/raw/scores/PJM_s11_mcar15.npz"
    if v10_zip.exists():
        import io as _io
        import zipfile
        with zipfile.ZipFile(v10_zip) as zf:
            v10 = _io.BytesIO(zf.read(v10_member))
        for tag, f in (("v10", v10), ("v11", raw / "scores" / "PJM_s11_mcar15.npz")):
            z = np.load(f, allow_pickle=True)
            prev_missing = np.r_[False, np.isnan(z["x_obs"])[:-1]]
            ev_ = (z["split_of"] == "test") & z["scored"]
            K[f"leak_{tag}_prevmiss_injected"] = float(prev_missing[ev_ & z["label"]].mean())
            K[f"leak_{tag}_prevmiss_normal"] = float(prev_missing[ev_ & ~z["label"]].mean())

    # ---------------- run bookkeeping
    man = json.loads((R / "run_manifest.json").read_text())
    K["run_wall_seconds"] = man["wall_seconds"]
    K["run_cells"] = man["cells"]
    K["run_errors"] = len(man["errors"])
    K["run_result_rows_total"] = int(sum(v["result_rows"] for v in man["counts"].values()))
    K["n_model_fits_primary"] = int(len(prim))
    K["fit_seconds_mean"] = prim.groupby("mlabel")["fit_seconds"].mean().to_dict()
    K["protocol_config_sha256"] = man["protocol_config_sha256"]
    (R / "key_numbers.json").write_text(json.dumps(K, indent=1, default=float))
    print(f"wrote {len(K)} key numbers and tables to {out}")


if __name__ == "__main__":
    main()
