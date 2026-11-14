"""Controlled fault injection and background missingness for hourly demand series.

All randomness comes from numpy Generators seeded with explicit integer tuples, so
an injection is a pure function of (seed, authority index, stream, settings).

Fault families (applied to the *observed* reported demand x):
  spike        x'_t = x_t (1 + s*d)                    for one hour
  level_shift  x'_t = x_t (1 + s*d)                    for L consecutive hours
  drift        x'_t = x_t (1 + s*d*(i+1)/L), i=0..L-1  linear ramp to peak d
  flatline     x'_t = x_{t0-1}                          for L hours (stale repeat of last value)
  timing       x'_t = x_{t-k}, k = s*K                  for L hours (delayed or advanced values)
with s in {-1, +1} random. A hour is labeled anomalous iff x'_t != x_t.
"""
from __future__ import annotations

from dataclasses import dataclass, asdict

import numpy as np
import pandas as pd

FAMILIES = ["spike", "level_shift", "drift", "flatline", "timing"]
TIERS = ["low", "medium", "high"]
STREAM_EVENTS, STREAM_MISSING, STREAM_LABELS, STREAM_MODEL = 0, 1, 2, 3


def make_rng(*keys: int) -> np.random.Generator:
    return np.random.default_rng([int(k) for k in keys])


@dataclass
class Event:
    event_id: int
    split: str
    family: str
    tier: str
    severity: float      # magnitude (fraction), stale length, or shift hours
    sign: int
    start: int           # position of first window hour in the series
    length: int
    n_altered: int = 0

    def window(self) -> range:
        return range(self.start, self.start + self.length)


def _draw_event_shape(family: str, tier: str, fam_cfg: dict, rng: np.random.Generator):
    if family == "flatline":
        lo, hi = fam_cfg["tiers"][tier]
        length = int(rng.integers(lo, hi + 1))
        severity = float(length)
    else:
        lo, hi = fam_cfg["length"]
        length = int(rng.integers(lo, hi + 1))
        severity = float(fam_cfg["tiers"][tier])
    sign = int(rng.choice([-1, 1]))
    return length, severity, sign


def place_events(valid: np.ndarray, split_pos: dict[str, tuple[int, int]], inj_cfg: dict,
                 events_per_family: dict[str, int], rng: np.random.Generator,
                 max_tries: int = 20000) -> list[Event]:
    """Place non-overlapping events at random valid positions.

    valid: boolean array, True where original reported demand is valid.
    split_pos: split name -> (first_pos, last_pos) inclusive.
    Each window (and the source hours it copies from) must be fully valid; windows
    are separated by at least `min_gap_hours`, kept `boundary_buffer_hours` away from
    split boundaries and after `require_history_hours`."""
    gap = inj_cfg["min_gap_hours"]
    buf = inj_cfg["boundary_buffer_hours"]
    hist = inj_cfg["require_history_hours"]
    occupied = np.zeros(len(valid), dtype=bool)
    events: list[Event] = []
    eid = 0
    for split, (lo, hi) in split_pos.items():
        n_per = events_per_family[split]
        plan = []
        for fam in FAMILIES:
            offset = int(rng.integers(0, len(TIERS)))
            for j in range(n_per):
                plan.append((fam, TIERS[(offset + j) % len(TIERS)]))
        order = rng.permutation(len(plan))
        for pi in order:
            fam, tier = plan[pi]
            length, severity, sign = _draw_event_shape(fam, tier, inj_cfg["families"][fam], rng)
            k = int(severity) if fam == "timing" else 0
            for _ in range(max_tries):
                start = int(rng.integers(max(lo + buf, hist + k + 1), hi - buf - length - k + 1))
                end = start + length  # exclusive
                if fam == "flatline":
                    src = np.arange(start - 1, start)
                elif fam == "timing":
                    src = np.arange(start - sign * k, end - sign * k)
                else:
                    src = np.arange(start, end)
                need = np.unique(np.concatenate([np.arange(start, end), src]))
                if not valid[need].all():
                    continue
                if occupied[max(0, start - gap):min(len(valid), end + gap)].any():
                    continue
                occupied[start:end] = True
                events.append(Event(eid, split, fam, tier, severity, sign, start, length))
                eid += 1
                break
            else:
                raise RuntimeError(f"could not place {fam}/{tier} in {split}")
    events.sort(key=lambda e: e.start)
    for i, e in enumerate(events):
        e.event_id = i
    return events


def apply_events(x: np.ndarray, events: list[Event]) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Return (x_injected, label, event_index) where label marks altered hours and
    event_index gives the owning event id (-1 outside events)."""
    xi = x.copy()
    label = np.zeros(len(x), dtype=bool)
    owner = np.full(len(x), -1, dtype=int)
    for e in events:
        w = np.arange(e.start, e.start + e.length)
        if e.family in ("spike", "level_shift"):
            xi[w] = x[w] * (1.0 + e.sign * e.severity)
        elif e.family == "drift":
            ramp = (np.arange(e.length) + 1) / e.length
            xi[w] = x[w] * (1.0 + e.sign * e.severity * ramp)
        elif e.family == "flatline":
            xi[w] = x[e.start - 1]
        elif e.family == "timing":
            xi[w] = x[w - e.sign * int(e.severity)]
        else:
            raise ValueError(e.family)
        altered = xi[w] != x[w]
        label[w[altered]] = True
        owner[w] = e.event_id
        e.n_altered = int(altered.sum())
    return xi, label, owner


def background_missingness(valid: np.ndarray, protected: np.ndarray, rate: float, mechanism: str,
                           block_len: tuple[int, int], rng: np.random.Generator) -> np.ndarray:
    """Boolean mask of hours to blank out. Only valid, unprotected hours are eligible.
    Protocol v1.1 passes no protected hours, so missingness is independent of the
    injected faults (masked injected hours are simply not scored). Exact count =
    round(rate * #eligible)."""
    eligible = valid & ~protected
    n_target = int(round(rate * eligible.sum()))
    mask = np.zeros(len(valid), dtype=bool)
    if n_target == 0 or mechanism == "none":
        return mask
    if mechanism == "mcar":
        pos = np.flatnonzero(eligible)
        mask[rng.choice(pos, size=n_target, replace=False)] = True
        return mask
    if mechanism == "block":
        lo, hi = block_len
        tries = 0
        while mask.sum() < n_target:
            tries += 1
            if tries > 1_000_000:
                raise RuntimeError("block missingness placement failed")
            L = int(rng.integers(lo, hi + 1))
            L = min(L, n_target - int(mask.sum()))
            s = int(rng.integers(0, len(valid) - L))
            seg = slice(s, s + L)
            if eligible[seg].all() and not mask[seg].any():
                mask[seg] = True
        return mask
    raise ValueError(mechanism)


def events_frame(events: list[Event], index: pd.DatetimeIndex, **meta) -> pd.DataFrame:
    rows = []
    for e in events:
        d = asdict(e)
        d["start_utc_end"] = str(index[e.start])
        d["end_utc_end"] = str(index[e.start + e.length - 1])
        d.update(meta)
        rows.append(d)
    return pd.DataFrame(rows)
