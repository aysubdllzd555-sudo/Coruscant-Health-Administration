from django import template

register = template.Library()

# (warn_low, warn_high, abn_low, abn_high) roughly following NEWS2 thresholds
RANGES = {
    "hr": (50, 91, 40, 131),
    "spo2": (95, None, 91, None),
    "temp": (36.0, 38.1, 35.0, 39.1),
    "sys": (110, 220, 90, 220),
    "rr": (11, 21, 8, 25),
}


@register.filter
def vclass(value, kind):
    if value in (None, ""):
        return ""
    v = float(value)
    wl, wh, al, ah = RANGES[kind]
    if (al is not None and v <= al) or (ah is not None and v >= ah):
        return "abn"
    if (wl is not None and v <= wl) or (wh is not None and v >= wh):
        return "warn"
    return ""


@register.filter
def hm(minutes):
    if minutes is None:
        return "–"
    return f"{int(minutes) // 60}:{int(minutes) % 60:02d}"


@register.filter
def filesize(n):
    for unit in ("B", "KB", "MB"):
        if n < 1024:
            return f"{n:.0f} {unit}" if unit == "B" else f"{n:.1f} {unit}"
        n /= 1024
    return f"{n:.1f} GB"


@register.filter
def get(d, key):
    return d.get(key) if hasattr(d, "get") else None
