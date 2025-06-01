import sys
import os

# Add parent directory to Python path so we can import enforcer modules  
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from enforcer.utils import add_custom_certificate

ADDITIONAL_CERTIFICATE: str = os.environ.get("CERTIFICATE", "")

if add_custom_certificate(ADDITIONAL_CERTIFICATE):
    print("added custom certificate")

# DO NOT ADD ANY CODE ABOVE THIS
# ADDING IMPORTS BEFORE ADDING THE CUSTOM CERTS MIGHT INIT HTTP CLIENTS THAT DOESN'T RESPECT THE CUSTOM CERT

import logging
import base64
import json
import re
import time
from typing import Dict, Any
from fastapi import FastAPI, HTTPException, Response
from pydantic import BaseModel
from prometheus_client import generate_latest, CONTENT_TYPE_LATEST

from enforcer.dal.supabase_dal import SupabaseDal
from enforcer.patch_manager import patch_container_resources
from enforcer.model import PodOwner, WorkloadRecommendation
from enforcer.env_vars import ENFORCER_SSL_KEY_FILE, ENFORCER_SSL_CERT_FILE, KRR_MUTATION_MODE_DEFAULT
from enforcer.resources.owner_store import OwnerStore
from enforcer.resources.recommendation_store import RecommendationStore
from enforcer.metrics import pod_admission_mutations, replicaset_admissions, rs_owners_size, admission_duration

# Configure logging
logger = logging.getLogger()
logHandler = logging.StreamHandler(sys.stdout)
formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
logHandler.setFormatter(formatter)
logger.addHandler(logHandler)
logger.setLevel(os.environ.get("LOG_LEVEL", "INFO"))

# Define the mention pattern regex
MENTION_PATTERN = re.compile(r'@[\w.-]+')
ENFORCE = "enforce"
IGNORE = "ignore"

app = FastAPI(
    title="KRR Enforcer mutation webhook",
    description="A KRR recommendations mutating webhook server for Kubernetes",
    version="1.0.0"
)

dal = SupabaseDal()
recommendation_store = RecommendationStore(dal)
owner_store = OwnerStore()

class AdmissionReview(BaseModel):
    apiVersion: str
    kind: str
    request: Dict[str, Any]

def admission_allowed(request: AdmissionReview) -> Dict[str, Any]:
    return \
        {
            "apiVersion": "admission.k8s.io/v1",
            "kind": "AdmissionReview",
            "response": {
                "uid": request.request.get('uid'),
                "allowed": True
        }
    }

def enforce_pod(pod: Dict[str, Any]) -> bool:
    mode = pod.get('metadata', {}).get('annotations', {}).get("admission.robusta.dev/krr-mutation-mode", None)
    if mode == ENFORCE:
        return True
    elif mode == IGNORE:
        return False
    else:
        return KRR_MUTATION_MODE_DEFAULT == ENFORCE


@app.post("/mutate")
async def mutate(request: AdmissionReview):
    """
    Handle mutating webhook requests from Kubernetes.
    
    Args:
        request (AdmissionReview): The admission review request from Kubernetes
        
    Returns:
        dict: Admission review response
    """
    start_time = time.time()
    try:
        logging.debug("Admission request received %s", request)
        # Extract the object being reviewed
        object_to_review = request.request.get('object', {})
        kind = request.request.get('kind', {}).get('kind')

        if kind == "ReplicaSet":  # use create/delete admission requests, to track new/removed replica sets owners
            owner_store.handle_rs_admission(request.request)
            operation = request.request.get('operation', 'UNKNOWN')
            replicaset_admissions.labels(operation=operation).inc()
            admission_duration.labels(kind='ReplicaSet').observe(time.time() - start_time)
            # Update rs_owners size metric
            rs_owners_size.set(owner_store.get_rs_owners_count())
            return admission_allowed(request)


        if kind != "Pod":
            logger.warning(f"Received unexpected resource mutation: {kind}")
            return admission_allowed(request)

        logger.debug("Processing pod: %s", owner_store.get_pod_name(object_to_review.get("metadata", {})))

        if not enforce_pod(object_to_review):
            logger.debug("pod skipped %s", object_to_review)
            pod_admission_mutations.labels(mutated="false", reason="ignored_by_annotation").inc()
            admission_duration.labels(kind="Pod").observe(time.time() - start_time)
            return admission_allowed(request)

        pod_owner: PodOwner = owner_store.get_pod_owner(object_to_review)

        if not pod_owner:
            logger.debug("no owner found. pod skipped %s", object_to_review)
            pod_admission_mutations.labels(mutated="false", reason="no_owner_found").inc()
            admission_duration.labels(kind="Pod").observe(time.time() - start_time)
            return admission_allowed(request)

        logger.debug("Pod owner %s", pod_owner)

        recommendations: WorkloadRecommendation = recommendation_store.get_recommendations(
            name=pod_owner.name, namespace=pod_owner.namespace, kind=pod_owner.kind
        )

        if not recommendations:
            logger.debug("no recommendations found for %s. Skipping", pod_owner)
            pod_admission_mutations.labels(mutated="false", reason="no_recommendations_found").inc()
            admission_duration.labels(kind="Pod").observe(time.time() - start_time)
            return admission_allowed(request)

        logger.debug("Pod Recommendations %s", recommendations)

        patches = []
        
        containers = object_to_review.get("spec", {}).get("containers", [])
        for i, container in enumerate(containers):
            container_name = container.get("name")
            patches.extend(patch_container_resources(i, container, recommendations.get(container_name)))
        
        # Record metrics for Pod mutation
        was_mutated = len(patches) > 0
        reason = "success" if was_mutated else "no_changes_needed"
        pod_admission_mutations.labels(mutated=str(was_mutated).lower(), reason=reason).inc()
        admission_duration.labels(kind="Pod").observe(time.time() - start_time)

        logger.debug("Pod patches %s", patches)

        return {
            "apiVersion": "admission.k8s.io/v1",
            "kind": "AdmissionReview",
            "response": {
                "uid": request.request.get("uid"),
                "allowed": True,
                "patchType": "JSONPatch",
                "patch": base64.b64encode(json.dumps(patches).encode()).decode() if patches else None
            }
        }
        
    except Exception as e:
        logger.exception("Error processing webhook request")
        # Record failure metric for Pod requests
        if request.request.get('kind', {}).get('kind') == "Pod":
            pod_admission_mutations.labels(mutated="false", reason="processing_error").inc()
            admission_duration.labels(kind="Pod").observe(time.time() - start_time)
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/health")
async def health_check():
    """
    Health check endpoint.
    
    Returns:
        dict: Health status
    """
    owner_store.finalize_owner_initialization()  # Init loading owners from api server, after accepting api requests
    return {"status": "healthy"}

@app.get("/recommendations/{namespace}/{kind}/{name}")
async def get_recommendations(namespace: str, kind: str, name: str):
    """
    Get recommendations for a workload.
    
    Args:
        namespace: Kubernetes namespace
        kind: Workload kind (e.g., Deployment, StatefulSet)
        name: Workload name
        
    Returns:
        dict: Recommendations per container or 404 if not found
    """
    try:
        recommendations: WorkloadRecommendation = recommendation_store.get_recommendations(
            name=name, namespace=namespace, kind=kind
        )
        
        if not recommendations:
            raise HTTPException(status_code=404, detail="No recommendations found for this workload")
        
        result = {}
        for container_name, container_recommendation in recommendations.container_recommendations.items():
            result[container_name] = {
                "cpu": {
                    "request": container_recommendation.cpu.request,
                    "limit": container_recommendation.cpu.limit
                } if container_recommendation.cpu else None,
                "memory": {
                    "request": container_recommendation.memory.request, 
                    "limit": container_recommendation.memory.limit
                } if container_recommendation.memory else None
            }
        
        return {
            "namespace": namespace,
            "kind": kind, 
            "name": name,
            "containers": result
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Error retrieving recommendations")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/metrics")
async def metrics():
    """
    Prometheus metrics endpoint.
    
    Returns:
        Response: Prometheus metrics in text format
    """
    # Update rs_owners size metric before returning metrics
    rs_owners_size.set(owner_store.get_rs_owners_count())
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)

if __name__ == "__main__":
    import uvicorn
    logger.info("Starting Kubernetes Webhook server on 8443...")
    uvicorn.run(app, host="0.0.0.0", port=8443, ssl_keyfile=ENFORCER_SSL_KEY_FILE, ssl_certfile=ENFORCER_SSL_CERT_FILE, log_level="warning")