import base64
import binascii
import json
import logging
import os
import threading
from datetime import datetime, timezone, timedelta
from typing import Dict, Optional, List

import yaml
from enforcer.dal.robusta_config import RobustaConfig, RobustaToken
from supabase import create_client
from supabase.lib.client_options import ClientOptions
from cachetools import TTLCache
from postgrest._sync.request_builder import SyncQueryRequestBuilder
from postgrest.exceptions import APIError as PGAPIError

from enforcer.env_vars import (
    ROBUSTA_CONFIG_PATH,
    ROBUSTA_ACCOUNT_ID,
    STORE_URL,
    STORE_API_KEY,
    STORE_EMAIL,
    STORE_PASSWORD,
    SCAN_AGE_HOURS_THRESHOLD,
)
from enforcer.params_utils import get_env_replacement

SUPABASE_TIMEOUT_SECONDS = int(os.getenv("SUPABASE_TIMEOUT_SECONDS", 3600))

SCANS_META_TABLE = "ScansMeta"
SCANS_RESULTS_TABLE = "ScansResults"


class SupabaseDal:
    def __init__(self):
        # disable info/debug logs for each db call
        for http_logger_name in ["httpx", "httpcore", "hpack"]:
            http_logger = logging.getLogger(http_logger_name)
            if http_logger:
                logging.info(f"Setting logging level for {http_logger_name} to WARNING")
                http_logger.setLevel(logging.WARNING)

        self.enabled = self.__init_config()
        if not self.enabled:
            logging.info("Not connecting to Robusta platform - robusta token not provided")
            return
        logging.info(
            f"Initializing Robusta platform connection for account {self.account_id} cluster {self.cluster}"
        )
        options = ClientOptions(postgrest_client_timeout=SUPABASE_TIMEOUT_SECONDS)
        self.client = create_client(self.url, self.api_key, options)
        self.user_id = self.sign_in()
        ttl = int(os.environ.get("SAAS_SESSION_TOKEN_TTL_SEC", "82800"))  # 23 hours
        self.patch_postgrest_execute()
        self.token_cache = TTLCache(maxsize=1, ttl=ttl)
        self.lock = threading.Lock()

    def patch_postgrest_execute(self):
        logging.info("Patching postgres execute")

        # This is somewhat hacky.
        def execute_with_retry(_self):
            try:
                return self._original_execute(_self)
            except PGAPIError as exc:
                message = exc.message or ""
                if exc.code == "PGRST301" or "expired" in message.lower():
                    # JWT expired. Sign in again and retry the query
                    logging.error(
                        "JWT token expired/invalid, signing in to Supabase again"
                    )
                    self.sign_in()
                    # update the session to the new one, after re-sign in
                    _self.session = self.client.postgrest.session
                    return self._original_execute(_self)
                else:
                    raise

        self._original_execute = SyncQueryRequestBuilder.execute
        SyncQueryRequestBuilder.execute = execute_with_retry

    @staticmethod
    def __load_robusta_config() -> (Optional[RobustaToken],Optional[str]):
        config_file_path = ROBUSTA_CONFIG_PATH
        env_ui_token = os.environ.get("ROBUSTA_UI_TOKEN")
        cluster_name = os.environ.get("CLUSTER_NAME")
        if env_ui_token and cluster_name:
            logging.info(f"Loading Robusta env configuration - ROBUSTA_UI_TOKEN_OVERRIDE")
            # token provided as env var
            try:
                decoded = base64.b64decode(env_ui_token)
                return RobustaToken(**json.loads(decoded)), cluster_name
            except binascii.Error:
                raise Exception(
                    "binascii.Error encountered. The Robusta UI token is not a valid base64."
                )
            except json.JSONDecodeError:
                raise Exception(
                    "json.JSONDecodeError encountered. The Robusta UI token could not be parsed as JSON after being base64 decoded."
                )

        if not os.path.exists(config_file_path):
            logging.info(f"No robusta config in {config_file_path}")
            return None, None

        logging.info(f"loading config {config_file_path}")
        with open(config_file_path) as file:
            yaml_content = yaml.safe_load(file)
            config = RobustaConfig(**yaml_content)
            for conf in config.sinks_config:
                if "robusta_sink" in conf.keys():
                    token = conf["robusta_sink"].get("token")
                    if not token:
                        raise Exception(
                            "No robusta token provided.\n"
                            "Please set a valid Robusta UI token.\n "
                        )
                    env_replacement_token = get_env_replacement(token)
                    if env_replacement_token:
                        token = env_replacement_token

                    if "{{" in token:
                        raise ValueError(
                            "The robusta token configured for Krr-enforcer appears to be a templating placeholder (e.g. `{ env.UI_SINK_TOKEN }`).\n "
                            "Ensure your Helm chart or environment variables are set correctly.\n "
                            "If you store the token in a secret, you must also pass "
                            "the environment variables ROBUSTA_UI_TOKEN and CLUSTER_NAME to krr-enforcer.\n "
                        )
                    try:
                        decoded = base64.b64decode(token)
                        return RobustaToken(**json.loads(decoded)), config.global_config.get("cluster_name")
                    except binascii.Error:
                        raise Exception(
                            "binascii.Error encountered. The robusta token provided is not a valid base64."
                        )
                    except json.JSONDecodeError:
                        raise Exception(
                            "json.JSONDecodeError encountered. The Robusta token provided could not be parsed as JSON after being base64 decoded."
                        )
        return None, None

    def __init_config(self) -> bool:
        # trying to load the supabase connection parameters from the robusta token, if exists
        # if not, using env variables as fallback
        robusta_token, cluster_name = self.__load_robusta_config()
        if robusta_token:
            self.account_id = robusta_token.account_id
            self.url = robusta_token.store_url
            self.api_key = robusta_token.api_key
            self.email = robusta_token.email
            self.password = robusta_token.password
        else:
            self.account_id = ROBUSTA_ACCOUNT_ID
            self.url = STORE_URL
            self.api_key = STORE_API_KEY
            self.email = STORE_EMAIL
            self.password = STORE_PASSWORD

        if cluster_name:
            self.cluster = cluster_name
        else:
            raise Exception("Missing mandatory cluster name")

        # valid only if all store parameters are provided
        return all([self.account_id, self.url, self.api_key, self.email, self.password])

    def sign_in(self) -> str:
        logging.info("Supabase DAL login")
        res = self.client.auth.sign_in_with_password(
            {"email": self.email, "password": self.password}
        )
        self.client.auth.set_session(
            res.session.access_token, res.session.refresh_token
        )
        self.client.postgrest.auth(res.session.access_token)
        return res.user.id

    def get_latest_krr_scan(self, current_scan_id: Optional[str]) -> (Optional[str], Optional[List[Dict]]):
        if not self.enabled:
            return None, None

        try:
            scans_meta_response = (
                self.client.table(SCANS_META_TABLE)
                .select("*")
                .eq("account_id", self.account_id)
                .eq("cluster_id", self.cluster)
                .eq("latest", True)
                .execute()
            )
            if not len(scans_meta_response.data):
                logging.warning(f"No scans found for account {self.account_id} cluster {self.cluster}")
                return None, None

            if len(scans_meta_response.data) > 1:
                logging.warning(f"Multiple latest scans found. Using newest scan")
                # Sort by scan_start string (ISO format sorts chronologically)
                sorted_scans = sorted(scans_meta_response.data, key=lambda x: x["scan_start"], reverse=True)
                latest_scan_data = sorted_scans[0]
            else:
                latest_scan_data = scans_meta_response.data[0]
                
            latest_scan_id = latest_scan_data["scan_id"]

            if latest_scan_id == current_scan_id:
                logging.info(f"Latest scan ID matches current scan ID {current_scan_id}. Reload not required.")
                return None, None

            scan_start = latest_scan_data["scan_start"]
            scan_datetime = datetime.fromisoformat(scan_start)
            max_age = timedelta(hours=SCAN_AGE_HOURS_THRESHOLD)
            if datetime.now(timezone.utc) - scan_datetime > max_age:
                logging.warning(f"Latest scan {latest_scan_id} is too old (started {scan_start}). No fresh KRR scan available.")
                return None, None

            scans_results_response = (
                self.client.table(SCANS_RESULTS_TABLE)
                .select("*")
                .eq("account_id", self.account_id)
                .eq("cluster_id", self.cluster)
                .eq("scan_id", latest_scan_id)
                .execute()
            )
            if not len(scans_results_response.data):
                return None, None

            return latest_scan_id, scans_results_response.data
        except Exception:
            logging.exception("Supabase error while retrieving krr scan data")
            return None, None



