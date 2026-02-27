import json
from datetime import datetime
from pathlib import Path


class AlarmLogger:
    """Log all alarm events to file for later analysis"""

    def __init__(self, log_dir="alarm_logs"):
        self.log_dir = Path(log_dir)
        self.log_dir.mkdir(exist_ok=True)

        # Create daily log file
        today = datetime.now().strftime("%Y-%m-%d")
        self.log_file = self.log_dir / f"alarms_{today}.jsonl"

    def log_alarm(self, cavity, severity, description=""):
        """Log an alarm event"""
        event = {
            "timestamp": datetime.now().isoformat(),
            "cryomodule": cavity.cryomodule.name,
            "cavity": cavity.number,
            "severity": severity,
            "severity_text": {0: "OK", 1: "WARNING", 2: "ALARM"}.get(
                severity, "UNKNOWN"
            ),
            "description": description,
        }

        with open(self.log_file, "a") as f:
            f.write(json.dumps(event) + "\n")

    def get_recent_alarms(self, hours=24):
        """Get alarms from the last N hours"""
        cutoff = datetime.now().timestamp() - (hours * 3600)
        recent = []

        if self.log_file.exists():
            with open(self.log_file, "r") as f:
                for line in f:
                    event = json.loads(line)
                    event_time = datetime.fromisoformat(
                        event["timestamp"]
                    ).timestamp()
                    if event_time >= cutoff:
                        recent.append(event)

        return recent
