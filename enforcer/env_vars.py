import os

ROBUSTA_CONFIG_PATH = os.environ.get(
    "ROBUSTA_CONFIG_PATH", "/etc/robusta/config/active_playbooks.yaml"
)
ROBUSTA_ACCOUNT_ID = os.environ.get("ROBUSTA_ACCOUNT_ID", "")
STORE_URL = os.environ.get("STORE_URL", "")
STORE_API_KEY = os.environ.get("STORE_API_KEY", "")
STORE_EMAIL = os.environ.get("STORE_EMAIL", "")
STORE_PASSWORD = os.environ.get("STORE_PASSWORD", "")

DISCOVERY_MAX_BATCHES = int(os.environ.get("DISCOVERY_MAX_BATCHES", 50))
DISCOVERY_BATCH_SIZE = int(os.environ.get("DISCOVERY_BATCH_SIZE", 30000))

UPDATE_THRESHOLD = float(os.environ.get("UPDATE_THRESHOLD", 20.0))

SCAN_RELOAD_INTERVAL = int(os.environ.get("SCAN_RELOAD_INTERVAL", 3600))
KRR_MUTATION_MODE_DEFAULT = os.environ.get("KRR_MUTATION_MODE_DEFAULT", "enforce")
REPLICA_SET_CLEANUP_INTERVAL = int(os.environ.get("REPLICA_SET_CLEANUP_INTERVAL", 600))
REPLICA_SET_DELETION_WAIT = int(os.environ.get("REPLICA_SET_DELETION_WAIT", 600))
SCAN_AGE_HOURS_THRESHOLD = int(os.environ.get("SCAN_AGE_HOURS_THRESHOLD", 360)) # 15 days

ENFORCER_SSL_KEY_FILE = os.environ.get("ENFORCER_SSL_KEY_FILE", "")
ENFORCER_SSL_CERT_FILE = os.environ.get("ENFORCER_SSL_CERT_FILE", "")