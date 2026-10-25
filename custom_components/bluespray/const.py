"""Constants for the BlueSpray integration."""
from datetime import timedelta

DOMAIN = "bluespray"
FAST_INTERVAL = timedelta(seconds=30)   # /api/status
SLOW_INTERVAL = timedelta(minutes=5)    # everything else
