"""Detector families. Every detector is fit on training-period rows only and
returns higher scores for more anomalous hours."""
from __future__ import annotations

import numpy as np
from sklearn.ensemble import IsolationForest
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

STAT_COMPONENTS = {"seasonal": "rs", "weekly": "rw", "diff": "d1res"}


class RobustSeasonalDetector:
    """Method A: max robust z-score of causal seasonal residuals.

    z_c(t) = |r_c(t) - med_train(r_c)| / (1.4826 * MAD_train(r_c)); score = max_c z_c.
    Components unavailable at t (missing lags) are skipped; if none is available the
    score is 0 (no evidence)."""

    def __init__(self, components=("seasonal", "diff")):
        self.cols = [STAT_COMPONENTS[c] for c in components]

    def fit(self, F_train):
        self.center, self.scale = {}, {}
        for c in self.cols:
            v = F_train[c].to_numpy()
            v = v[~np.isnan(v)]
            med = np.median(v)
            mad = 1.4826 * np.median(np.abs(v - med))
            self.center[c], self.scale[c] = med, max(mad, 1e-9)
        return self

    def score(self, F):
        Z = np.vstack([np.abs(F[c].to_numpy() - self.center[c]) / self.scale[c] for c in self.cols])
        allnan = np.isnan(Z).all(axis=0)
        s = np.nanmax(np.where(allnan[None, :], 0.0, Z), axis=0)
        return s


class IForestDetector:
    """Method B: Isolation Forest on the shared causal feature space."""

    def __init__(self, cols, n_estimators=200, max_samples=256, max_features=1.0, random_state=0):
        self.cols = list(cols)
        self.imp = SimpleImputer(strategy="median")
        self.model = IsolationForest(n_estimators=n_estimators, max_samples=max_samples,
                                     max_features=max_features, random_state=random_state, n_jobs=1)

    def fit(self, F_train):
        X = self.imp.fit_transform(F_train[self.cols].to_numpy())
        self.model.fit(X)
        return self

    def score(self, F):
        return -self.model.score_samples(self.imp.transform(F[self.cols].to_numpy()))


class PULogisticDetector:
    """Method C: L2 logistic regression with a fixed budget of verified labels plus
    unlabeled training hours used as *weak* (assumed) negatives.

    Sample weights: verified positives share 0.5 of total weight; the negative side
    (0.5) is split between verified negatives (1 - u) and unlabeled weak negatives (u).
    u = 0 gives a labels-only learner. Weights are rescaled to sum to the number of
    training rows. Imputer and scaler are fit on all training rows (features only)."""

    def __init__(self, cols, C=1.0, unlabeled_weight_share=0.5, max_iter=2000):
        self.cols = list(cols)
        self.u = unlabeled_weight_share
        self.pipe = make_pipeline(SimpleImputer(strategy="median"), StandardScaler(),
                                  LogisticRegression(C=C, max_iter=max_iter))

    def fit(self, F_train, pos_idx, neg_idx, unl_idx):
        X_all = F_train[self.cols].to_numpy()
        imp, sc = self.pipe.steps[0][1], self.pipe.steps[1][1]
        Xt = sc.fit_transform(imp.fit_transform(X_all))
        parts_X, parts_y, parts_w = [Xt[pos_idx]], [np.ones(len(pos_idx))], [np.full(len(pos_idx), 0.5 / len(pos_idx))]
        neg_share = 0.5 * (1 - self.u) if len(unl_idx) and self.u > 0 else 0.5
        parts_X.append(Xt[neg_idx]); parts_y.append(np.zeros(len(neg_idx)))
        parts_w.append(np.full(len(neg_idx), neg_share / len(neg_idx)))
        if self.u > 0 and len(unl_idx):
            parts_X.append(Xt[unl_idx]); parts_y.append(np.zeros(len(unl_idx)))
            parts_w.append(np.full(len(unl_idx), 0.5 * self.u / len(unl_idx)))
        X, y, w = np.vstack(parts_X), np.concatenate(parts_y), np.concatenate(parts_w)
        w = w * len(X_all) / w.sum()
        self.pipe.steps[2][1].fit(X, y, sample_weight=w)
        self.n_iter_ = int(self.pipe.steps[2][1].n_iter_[0])
        return self

    def score(self, F):
        return self.pipe.decision_function(F[self.cols].to_numpy())


def sample_label_budget(budget: int, label: np.ndarray, owner: np.ndarray, train_rows: np.ndarray,
                        rng: np.random.Generator, exclude_families=None, event_family=None):
    """Draw the verified-label set for one budget from TRAINING rows only.

    budget = total expert-verified hour labels; budget/2 positives (altered hours,
    spread round-robin over randomly ordered training events) and budget/2 verified
    normals (unaltered, not inside any event window). Returns (pos, neg, unlabeled)
    as positions into train_rows."""
    n_pos = budget // 2
    n_neg = budget - n_pos
    lab = label[train_rows]
    own = owner[train_rows]
    ev_ids = np.unique(own[lab])
    if exclude_families is not None:
        ev_ids = np.array([e for e in ev_ids if event_family[e] not in exclude_families])
    ev_ids = rng.permutation(ev_ids)
    pools = {e: list(rng.permutation(np.flatnonzero(lab & (own == e)))) for e in ev_ids}
    pos = []
    while len(pos) < n_pos:
        progressed = False
        for e in ev_ids:
            if pools[e] and len(pos) < n_pos:
                pos.append(pools[e].pop())
                progressed = True
        if not progressed:
            raise RuntimeError("not enough positive training hours for budget")
    normal = np.flatnonzero(~lab & (own == -1))
    neg = rng.choice(normal, size=n_neg, replace=False)
    used = np.zeros(len(train_rows), dtype=bool)
    used[pos] = True
    used[neg] = True
    unl = np.flatnonzero(~used)
    return np.array(pos), np.array(neg), unl
