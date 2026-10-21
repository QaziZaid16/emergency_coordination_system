from math import asin, cos, radians, sin, sqrt


def priority_for(emergency_type: str, severity: int, urgency: int) -> tuple[str, str]:
    # Preserve lib/domain/dispatch_rules.dart exactly: 2x severity + 2x
    # urgency plus category factor (medical/fire=2, rescue/security=1, other=0).
    kind = emergency_type.lower()
    category_factor = 2 if "medical" in kind or "fire" in kind else 1 if "rescue" in kind or "security" in kind else 0
    score = (max(1, min(5, severity)) * 2) + (max(1, min(5, urgency)) * 2) + category_factor
    priority = "Critical" if score >= 18 else "High" if score >= 14 else "Medium" if score >= 9 else "Low"
    response_factor = f" + {emergency_type} response factor" if category_factor else ""
    reason = f"Severity {severity}/5 + urgency {urgency}/5{response_factor} = {score}/22"
    return priority, reason


def distance_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    d_lat, d_lon = radians(lat2 - lat1), radians(lon2 - lon1)
    a = sin(d_lat / 2) ** 2 + cos(radians(lat1)) * cos(radians(lat2)) * sin(d_lon / 2) ** 2
    return 6371.0 * 2 * asin(sqrt(a))
