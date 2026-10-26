"""
Clinical scoring helpers.

NEWS2 (Royal College of Physicians, 2017) is used as the early-warning score for
device readings: higher = sicker. Trend compares the mean NEWS2 of the most
recent readings with the preceding window.
"""
from statistics import mean


def _band(value, bands):
    for low, high, score in bands:
        if (low is None or value >= low) and (high is None or value <= high):
            return score
    return 0


def news2(reading) -> int | None:
    parts = []
    if reading.resp_rate is not None:
        parts.append(_band(reading.resp_rate, [(None, 8, 3), (9, 11, 1), (12, 20, 0), (21, 24, 2), (25, None, 3)]))
    if reading.spo2 is not None:
        parts.append(_band(reading.spo2, [(None, 91, 3), (92, 93, 2), (94, 95, 1), (96, None, 0)]))
    if reading.systolic is not None:
        parts.append(_band(reading.systolic, [(None, 90, 3), (91, 100, 2), (101, 110, 1), (111, 219, 0), (220, None, 3)]))
    if reading.heart_rate is not None:
        parts.append(_band(reading.heart_rate, [(None, 40, 3), (41, 50, 1), (51, 90, 0), (91, 110, 1), (111, 130, 2), (131, None, 3)]))
    if reading.temperature_c is not None:
        t = float(reading.temperature_c)
        parts.append(_band(t, [(None, 35.0, 3), (35.1, 36.0, 1), (36.1, 38.0, 0), (38.1, 39.0, 1), (39.1, None, 2)]))
    if not parts:
        return None
    return sum(parts)


def risk_level(score):
    if score is None:
        return "unknown"
    if score >= 7:
        return "high"
    if score >= 5:
        return "medium"
    if score >= 1:
        return "low"
    return "none"


TREND_IMPROVING = "improving"
TREND_STABLE = "stable"
TREND_WORSENING = "worsening"
TREND_UNKNOWN = "insufficient"


def trend(readings, window=5) -> str:
    """`readings` newest-first. Compares the newest window vs the previous one."""
    scores = [s for s in (news2(r) for r in readings) if s is not None]
    if len(scores) < 2:
        return TREND_UNKNOWN
    w = min(window, len(scores) // 2)
    recent, previous = scores[:w], scores[w : 2 * w]
    delta = mean(recent) - mean(previous)
    if delta <= -1:
        return TREND_IMPROVING
    if delta >= 1:
        return TREND_WORSENING
    return TREND_STABLE
