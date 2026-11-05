import base64
import json
from pathlib import Path

import pytest
import requests

CASES_DIR = Path(__file__).parent / "fixtures" / "cases"
CASE_FILES = sorted(CASES_DIR.glob("*.json"))


def post_review(enforcer: str, review: dict) -> dict:
    response = requests.post(f"{enforcer}/mutate", json=review, timeout=5)
    response.raise_for_status()
    return response.json()["response"]


def decode_patch(admission_response: dict):
    if "patch" not in admission_response:
        return None
    assert admission_response["patchType"] == "JSONPatch"
    return json.loads(base64.b64decode(admission_response["patch"]))


@pytest.mark.parametrize("case_file", CASE_FILES, ids=[case.stem for case in CASE_FILES])
def test_mutate(enforcer, case_file):
    case = json.loads(case_file.read_text())
    for setup_review in case.get("setup", []):
        assert post_review(enforcer, setup_review)["allowed"]

    admission_response = post_review(enforcer, case["review"])

    assert admission_response["uid"] == case["review"]["request"]["uid"]
    assert admission_response["allowed"]
    assert decode_patch(admission_response) == case["expected_patch"]


def test_recommendations_endpoint(enforcer):
    response = requests.get(f"{enforcer}/recommendations/shop/StatefulSet/inventory-db", timeout=5)

    assert response.status_code == 200
    assert response.json()["containers"] == {
        "postgres": {
            "cpu": {"request": 0.5, "limit": 1.0},
            "memory": {"request": 536870912, "limit": 536870912},
        }
    }


def test_recommendations_endpoint_unknown_workload(enforcer):
    response = requests.get(f"{enforcer}/recommendations/shop/Deployment/unknown", timeout=5)

    assert response.status_code == 404


def test_recommendations_endpoint_skips_unknown_values(enforcer):
    response = requests.get(f"{enforcer}/recommendations/shop/Job/report-builder", timeout=5)

    assert response.status_code == 404


def test_mutate_rejects_review_without_request(enforcer):
    response = requests.post(f"{enforcer}/mutate", json={"apiVersion": "admission.k8s.io/v1", "kind": "AdmissionReview"}, timeout=5)

    assert response.status_code == 422


def test_health_endpoint(enforcer):
    response = requests.get(f"{enforcer}/health", timeout=5)

    assert response.json() == {"status": "healthy"}


def test_metrics_endpoint(enforcer):
    response = requests.get(f"{enforcer}/metrics", timeout=5)

    assert response.status_code == 200
    assert "krr_rs_owners_map_size" in response.text
