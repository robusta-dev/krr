import base64
import json
import os
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import pytest
import requests
import yaml
from pytest_httpserver import HTTPServer

ENFORCER_DIR = Path(__file__).parent.parent
FIXTURES_DIR = Path(__file__).parent / "fixtures"
ENFORCER_URL = "http://127.0.0.1:8443"
ACCOUNT_ID = "test-account"
CLUSTER_NAME = "test-cluster"
SCAN_ID = "test-scan"
USER = {
    "id": "test-user",
    "aud": "authenticated",
    "role": "authenticated",
    "email": "enforcer@example.com",
    "app_metadata": {},
    "user_metadata": {},
    "created_at": "2026-01-01T00:00:00Z",
}


def b64url(data: dict) -> str:
    return base64.urlsafe_b64encode(json.dumps(data).encode()).decode().rstrip("=")


def fake_jwt(expires_at: int) -> str:
    return f"{b64url({'alg': 'HS256', 'typ': 'JWT'})}.{b64url({'sub': USER['id'], 'exp': expires_at})}.c2lnbmF0dXJl"


def load_fixture(name: str):
    return json.loads((FIXTURES_DIR / name).read_text())


def register_supabase(server: HTTPServer) -> None:
    expires_at = int(time.time()) + 3600
    session = {
        "access_token": fake_jwt(expires_at),
        "refresh_token": "test-refresh-token",
        "token_type": "bearer",
        "expires_in": 3600,
        "expires_at": expires_at,
        "user": USER,
    }
    scan_meta = {"scan_id": SCAN_ID, "scan_start": datetime.now(timezone.utc).isoformat(), "latest": True}
    scan_filter = {"select": "*", "account_id": f"eq.{ACCOUNT_ID}", "cluster_id": f"eq.{CLUSTER_NAME}"}

    server.expect_request("/auth/v1/token", method="POST").respond_with_json(session)
    server.expect_request("/auth/v1/user").respond_with_json(USER)
    server.expect_request("/rest/v1/ScansMeta", query_string={**scan_filter, "latest": "eq.True"}).respond_with_json(
        [scan_meta]
    )
    server.expect_request("/rest/v1/ScansResults", query_string={**scan_filter, "scan_id": f"eq.{SCAN_ID}"}).respond_with_json(
        load_fixture("scans_results.json")
    )


def write_kubeconfig(path: Path, server_url: str) -> None:
    kubeconfig = {
        "apiVersion": "v1",
        "kind": "Config",
        "clusters": [{"name": "fake", "cluster": {"server": server_url}}],
        "users": [{"name": "fake", "user": {"token": "fake"}}],
        "contexts": [{"name": "fake", "context": {"cluster": "fake", "user": "fake"}}],
        "current-context": "fake",
    }
    path.write_text(yaml.safe_dump(kubeconfig))


def wait_until_healthy(process: subprocess.Popen) -> None:
    for _ in range(60):
        if process.poll() is not None:
            raise RuntimeError(f"enforcer exited with code {process.returncode}")
        try:
            if requests.get(f"{ENFORCER_URL}/health", timeout=1).ok:
                return
        except requests.ConnectionError:
            pass
        time.sleep(0.5)
    raise RuntimeError("enforcer did not become healthy within 30 seconds")


@pytest.fixture(scope="session")
def fake_backend():
    server = HTTPServer()
    server.start()
    register_supabase(server)
    server.expect_request("/apis/apps/v1/replicasets").respond_with_json(load_fixture("replicasets.json"))
    yield server
    server.stop()


@pytest.fixture(scope="session")
def enforcer(fake_backend, tmp_path_factory):
    backend_url = fake_backend.url_for("").rstrip("/")
    kubeconfig = tmp_path_factory.mktemp("kube") / "config"
    write_kubeconfig(kubeconfig, backend_url)
    token = {
        "store_url": backend_url,
        "api_key": fake_jwt(int(time.time()) + 3600),
        "account_id": ACCOUNT_ID,
        "email": USER["email"],
        "password": "test-password",
    }
    env = {
        **os.environ,
        "KUBECONFIG": str(kubeconfig),
        "ROBUSTA_UI_TOKEN": base64.b64encode(json.dumps(token).encode()).decode(),
        "CLUSTER_NAME": CLUSTER_NAME,
        "EXCLUDED_CONTAINERS": "istio-proxy",
    }
    env.pop("KUBERNETES_SERVICE_HOST", None)
    process = subprocess.Popen([sys.executable, "enforcer_main.py"], cwd=ENFORCER_DIR, env=env)
    try:
        wait_until_healthy(process)
        yield ENFORCER_URL
    finally:
        process.terminate()
        process.wait(timeout=10)
