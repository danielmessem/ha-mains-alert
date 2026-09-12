"""Pure outage detection state machine, separated for testing."""

from dataclasses import dataclass
from typing import Optional


@dataclass
class DetectionResult:
    event: Optional[str]
    condition: str


class MainsDetector:
    def __init__(self):
        self.status = "unknown"
        self.candidate = None
        self.candidate_since = None

    @staticmethod
    def condition(value, config):
        mode = config.get("mode", "numeric")
        if value is None:
            return "unknown"
        if mode == "state":
            text = str(value).strip().lower()
            off_values = {str(x).strip().lower() for x in config.get("off_values", [])}
            on_values = {str(x).strip().lower() for x in config.get("on_values", [])}
            if text in off_values:
                return "off"
            if text in on_values:
                return "on"
            return "unknown"
        try:
            number = float(value)
        except (TypeError, ValueError):
            return "unknown"
        if number < float(config.get("off_threshold", 50)):
            return "off"
        if number > float(config.get("on_threshold", 180)):
            return "on"
        return "unknown"

    def update(self, value, now, config, allow_event=True):
        condition = self.condition(value, config)
        if condition == "unknown":
            self.candidate = None
            self.candidate_since = None
            return DetectionResult(None, condition)

        if self.status == "unknown":
            self.status = condition
            return DetectionResult(None, condition)
        if condition == self.status:
            self.candidate = None
            self.candidate_since = None
            return DetectionResult(None, condition)
        if self.candidate != condition:
            self.candidate = condition
            self.candidate_since = now
            return DetectionResult(None, condition)

        delay_key = "off_delay" if condition == "off" else "on_delay"
        if now - self.candidate_since < float(config.get(delay_key, 15)):
            return DetectionResult(None, condition)

        self.status = condition
        self.candidate = None
        self.candidate_since = None
        event = condition if allow_event else None
        return DetectionResult(event, condition)

