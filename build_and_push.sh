#!/bin/bash
set -e

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

# Configuration
REGISTRY="europe-west12-docker.pkg.dev"
PROJECT="formazione-ion-boleac"
REPOSITORY="tools"
IMAGE_NAME="holo-krr"
FULL_IMAGE="${REGISTRY}/${PROJECT}/${REPOSITORY}/${IMAGE_NAME}"

# Dockerfile to use (default: gcloud-based)
DOCKERFILE="${1:-Dockerfile.gcloud}"
TAG="${2:-latest}"

echo -e "${GREEN}╔══════════════════════════════════════════════════╗${NC}"
echo -e "${GREEN}║         Build & Push KRR to Artifact Registry    ║${NC}"
echo -e "${GREEN}╚══════════════════════════════════════════════════╝${NC}"
echo ""
echo "Dockerfile:  ${DOCKERFILE}"
echo "Image:       ${FULL_IMAGE}:${TAG}"
echo "Registry:    ${REGISTRY}"
echo ""

# Check if Dockerfile exists
if [ ! -f "${DOCKERFILE}" ]; then
    echo -e "${RED}Error: ${DOCKERFILE} not found${NC}"
    exit 1
fi

# Authenticate to Artifact Registry
echo -e "${YELLOW}→ Configuring Docker authentication...${NC}"
gcloud auth configure-docker ${REGISTRY} --quiet

echo -e "${GREEN}✓ Authentication configured${NC}"
echo ""

# Build the image
echo -e "${YELLOW}→ Building Docker image...${NC}"
docker build -f "${DOCKERFILE}" -t "${FULL_IMAGE}:${TAG}" .

echo -e "${GREEN}✓ Image built: ${FULL_IMAGE}:${TAG}${NC}"
echo ""

# Also tag as latest if not already
if [ "${TAG}" != "latest" ]; then
    docker tag "${FULL_IMAGE}:${TAG}" "${FULL_IMAGE}:latest"
    echo -e "${GREEN}✓ Also tagged as: ${FULL_IMAGE}:latest${NC}"
fi

# Tag with version from krr.py if exists
VERSION=$(grep "VERSION = " krr.py 2>/dev/null | cut -d'"' -f2 || echo "")
if [ -n "${VERSION}" ]; then
    docker tag "${FULL_IMAGE}:${TAG}" "${FULL_IMAGE}:v${VERSION}"
    echo -e "${GREEN}✓ Also tagged as: ${FULL_IMAGE}:v${VERSION}${NC}"
fi

echo ""

# Push the image
echo -e "${YELLOW}→ Pushing image to Artifact Registry...${NC}"
docker push "${FULL_IMAGE}:${TAG}"

if [ "${TAG}" != "latest" ]; then
    docker push "${FULL_IMAGE}:latest"
fi

if [ -n "${VERSION}" ]; then
    docker push "${FULL_IMAGE}:v${VERSION}"
fi

echo ""
echo -e "${GREEN}╔══════════════════════════════════════════════════╗${NC}"
echo -e "${GREEN}║              ✓ Push completed                    ║${NC}"
echo -e "${GREEN}╚══════════════════════════════════════════════════╝${NC}"
echo ""
echo "Available tags:"
echo "  - ${FULL_IMAGE}:${TAG}"
[ "${TAG}" != "latest" ] && echo "  - ${FULL_IMAGE}:latest"
[ -n "${VERSION}" ] && echo "  - ${FULL_IMAGE}:v${VERSION}"
echo ""
echo "Pull command:"
echo "  docker pull ${FULL_IMAGE}:${TAG}"
echo ""
echo "Run command:"
echo "  docker run --rm ${FULL_IMAGE}:${TAG}"
echo ""
