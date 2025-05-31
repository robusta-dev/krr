import logging
from typing import Optional, Dict, Any, List

from pydantic import BaseModel


class PodOwner(BaseModel):
    kind: str
    name: str
    namespace: str

class RsOwner(BaseModel):
    rs_name: str
    namespace: str
    owner_name: str
    owner_kind: str
    deletion_ts: Optional[float] = None

class Resources(BaseModel):
    request: float
    limit: Optional[float]


class ResourcesRecommendation(BaseModel):
    cpu: Optional[Resources] = None
    memory: Optional[Resources] = None

class WorkloadRecommendation(BaseModel):
    workload_key: str
    container_recommendations: Dict[str, ResourcesRecommendation] = {}

    def get(self, container: str) -> Optional[ResourcesRecommendation]:
        return self.container_recommendations.get(container, None)

    @staticmethod
    def build(recommendation: Dict[str, Any]) -> Optional[ResourcesRecommendation]:
        resource_recommendation = ResourcesRecommendation()
        content: List[Dict] = recommendation["content"]
        for container_resource in content:
            resource = container_resource["resource"]
            if resource not in ["memory", "cpu"]:
                continue

            recommended: Dict[str, Any] = container_resource["recommended"]
            request = recommended.get("request", 0.0)
            limit = recommended.get("limit", None)

            if request == 0.0:
                logging.debug(f"skipping container recommendations without request, %s", recommendation)
                return

            if request == "?" or limit == "?":
                logging.debug(f"skipping container recommendations with '?', %s", recommendation)
                return

            resources = Resources(request=request, limit=limit)
            if resource == "memory":
                resource_recommendation.memory = resources
            elif resource == "cpu":
                resource_recommendation.cpu = resources

        return resource_recommendation

    def add(self, container: str, recommendation: ResourcesRecommendation):
        self.container_recommendations[container] = recommendation