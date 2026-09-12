"""Home Assistant entity and notification discovery helpers."""

import math


POSITIVE = {
    "mains": 70,
    "grid voltage": 65,
    "grid": 35,
    "utility": 30,
    "eskom": 45,
    "ac voltage": 25,
    "inverter": 8,
}
NEGATIVE = {
    "pv": -60,
    "solar": -55,
    "battery": -55,
    "load": -35,
    "output": -25,
    "generator": -45,
    "essential": -20,
    "non essential": -20,
}


def _number(value):
    try:
        result = float(value)
        return result if math.isfinite(result) else None
    except (TypeError, ValueError):
        return None


def score_entity(entity):
    entity_id = entity.get("entity_id", "")
    attributes = entity.get("attributes", {}) or {}
    name = str(attributes.get("friendly_name", ""))
    haystack = f"{entity_id} {name}".lower().replace("_", " ")
    score = 0
    reasons = []
    for phrase, points in POSITIVE.items():
        if phrase in haystack:
            score += points
            reasons.append(f"{phrase} +{points}")
    for phrase, points in NEGATIVE.items():
        if phrase in haystack:
            score += points
            reasons.append(f"{phrase} {points}")

    unit = str(attributes.get("unit_of_measurement", "")).strip().lower()
    numeric = _number(entity.get("state"))
    if unit in ("v", "volt", "volts"):
        score += 55
        reasons.append("voltage unit +55")
    if numeric is not None and 150 <= numeric <= 280:
        score += 20
        reasons.append("plausible mains voltage +20")
    device_class = str(attributes.get("device_class", "")).lower()
    if device_class in ("voltage", "power"):
        score += 10
        reasons.append(f"{device_class} class +10")
    if entity_id.startswith(("sensor.", "binary_sensor.")):
        score += 3
    else:
        score -= 30
    return {"entity_id": entity_id, "name": name or entity_id, "state": entity.get("state"),
            "unit": attributes.get("unit_of_measurement", ""), "score": score,
            "reasons": reasons}


def rank_mains_entities(states, limit=25):
    ranked = [score_entity(entity) for entity in states]
    ranked = [row for row in ranked if row["score"] > 0]
    return sorted(ranked, key=lambda row: (-row["score"], row["entity_id"]))[:limit]


def mobile_notify_services(service_domains):
    discovered = []
    for domain in service_domains:
        if domain.get("domain") != "notify":
            continue
        for name in domain.get("services", {}):
            if name.startswith("mobile_app_"):
                discovered.append(f"notify.{name}")
    return sorted(set(discovered))

