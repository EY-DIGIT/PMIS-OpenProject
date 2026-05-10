#!/usr/bin/env bash
set -euo pipefail

BRANCH="dev"
IMAGE_NAME="pmic-backend"
REPO_DIR="$HOME/pmis-backend"
VERSION_FILE="$HOME/pmis-env/backend_image_version.txt"

cd "$REPO_DIR"

echo "---------------------------------------"
echo " PMIS BACKEND DEPLOYMENT"
echo "---------------------------------------"

# ── Git Pull ───────────────────────────
echo "Pulling latest code..."
git fetch origin
git checkout "$BRANCH"
git pull origin "$BRANCH"

COMMIT=$(git rev-parse --short HEAD)

# ── Versioning ─────────────────────────
echo "Reading version..."
if [[ -f "$VERSION_FILE" ]]; then
  LAST_VERSION=$(cat "$VERSION_FILE")
else
  LAST_VERSION=0
fi

[[ "$LAST_VERSION" =~ ^[0-9]+$ ]] || LAST_VERSION=0

NEXT_VERSION=$((LAST_VERSION + 1))
IMAGE_TAG="v${NEXT_VERSION}"

echo "$NEXT_VERSION" > "$VERSION_FILE"

# ── Docker Hub Optional ────────────────
echo ""
read -rp "Push to Docker Hub? (y/n): " USE_DOCKER_HUB
USE_DOCKER_HUB=$(echo "$USE_DOCKER_HUB" | tr '[:upper:]' '[:lower:]')

if [[ "$USE_DOCKER_HUB" == "y" ]]; then
  read -rp "Docker Username: " DOCKER_USERNAME
  read -rsp "Docker Token/Password: " DOCKER_PASSWORD
  echo ""

  echo "$DOCKER_PASSWORD" | docker login -u "$DOCKER_USERNAME" --password-stdin

  FULL_IMAGE="${DOCKER_USERNAME}/${IMAGE_NAME}:${IMAGE_TAG}"
  LATEST_IMAGE="${DOCKER_USERNAME}/${IMAGE_NAME}:latest"
else
  DOCKER_USERNAME=""
  FULL_IMAGE="${IMAGE_NAME}:${IMAGE_TAG}"
  LATEST_IMAGE="${IMAGE_NAME}:latest"
fi

# ── Build ──────────────────────────────
echo "Building image: $FULL_IMAGE"
docker build -t "$FULL_IMAGE" .

echo "Tagging latest..."
docker tag "$FULL_IMAGE" "$LATEST_IMAGE"

# ── Push (optional) ────────────────────
if [[ "$USE_DOCKER_HUB" == "y" ]]; then
  echo "Pushing to Docker Hub..."
  docker push "$FULL_IMAGE"
  docker push "$LATEST_IMAGE"
else
  echo "Skipping Docker push..."
fi

# ── Export runtime variables ───────────
export IMAGE_TAG="$IMAGE_TAG"
export DOCKER_USERNAME="$DOCKER_USERNAME"

# ── Deploy (IMPORTANT CHANGE HERE) ─────
echo "Deploying container..."
docker compose down || true
docker compose up -d --remove-orphans

# ── Cleanup ────────────────────────────
echo "Cleaning unused images..."
docker image prune -f

# ── Done ───────────────────────────────
echo ""
echo "---------------------------------------"
echo " DEPLOYMENT SUCCESS"
echo "---------------------------------------"
echo " Image   : $FULL_IMAGE"
echo " Commit  : $COMMIT"
echo " Branch  : $BRANCH"
echo " Version : $IMAGE_TAG"
echo "---------------------------------------"
