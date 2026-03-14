"""Schedule configuration management.

Stores and retrieves scan schedule settings from a JSON config file.
Users can modify the schedule (interval, cron expression, or specific times)
through the CLI or by editing the config file directly.
"""

import json
import os

CONFIG_PATH = "scan_config.json"

DEFAULT_CONFIG = {
    "schedule": {
        "enabled": True,
        "type": "interval",
        "interval_minutes": 60,
        "cron": None,
        "timezone": "America/Montreal",
    },
    "scan": {
        "gmail_query": "has:attachment filename:pdf",
        "max_emails": 25,
        "target_email": "donglan.myan@gmail.com",
    },
    "output": {
        "csv_path": "output/invoices.csv",
        "json_path": "output/invoices.json",
        "excel_path": "output/invoices.xlsx",
        "append_mode": True,
    },
}


def load_config():
    """Load configuration from disk, creating defaults if missing."""
    if not os.path.exists(CONFIG_PATH):
        save_config(DEFAULT_CONFIG)
        return DEFAULT_CONFIG.copy()

    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        config = json.load(f)

    # Merge with defaults for any missing keys
    merged = _deep_merge(DEFAULT_CONFIG, config)
    return merged


def save_config(config):
    """Persist configuration to disk."""
    with open(CONFIG_PATH, "w", encoding="utf-8") as f:
        json.dump(config, f, indent=2)


def _deep_merge(defaults, overrides):
    """Recursively merge overrides into defaults."""
    result = defaults.copy()
    for key, value in overrides.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = _deep_merge(result[key], value)
        else:
            result[key] = value
    return result


def update_schedule(schedule_type=None, interval_minutes=None, cron=None,
                    enabled=None, timezone=None):
    """Update schedule settings and persist.

    Args:
        schedule_type: 'interval' or 'cron'
        interval_minutes: Minutes between scans (for interval type)
        cron: Cron expression string (for cron type), e.g. '0 8 * * *'
        enabled: True/False to enable/disable scheduling
        timezone: Timezone string, e.g. 'America/Montreal'

    Returns:
        dict: Updated config.
    """
    config = load_config()
    sched = config["schedule"]

    if schedule_type is not None:
        sched["type"] = schedule_type
    if interval_minutes is not None:
        sched["interval_minutes"] = interval_minutes
    if cron is not None:
        sched["cron"] = cron
    if enabled is not None:
        sched["enabled"] = enabled
    if timezone is not None:
        sched["timezone"] = timezone

    save_config(config)
    return config


def get_schedule_description(config=None):
    """Return a human-readable description of the current schedule."""
    if config is None:
        config = load_config()

    sched = config["schedule"]
    if not sched["enabled"]:
        return "Scheduling is disabled"

    if sched["type"] == "interval":
        mins = sched["interval_minutes"]
        if mins < 60:
            return f"Every {mins} minute(s)"
        hours = mins / 60
        if hours == int(hours):
            return f"Every {int(hours)} hour(s)"
        return f"Every {mins} minutes"
    elif sched["type"] == "cron":
        return f"Cron: {sched['cron']} ({sched.get('timezone', 'UTC')})"
    return "Unknown schedule type"
