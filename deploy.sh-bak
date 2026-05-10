#!/bin/bash
set -euo pipefail

BRANCH="dev"
IMAGE="ritamhudait/pmic-backend"
REPO_DIR="$HOME/pmis-backend"
VERSION_FILE="$HOME/pmis-env/backend_image_version.txt"

cd "$REPO_DIR"

echo "Pulling latest code from GitHub..."
git fetch origin
git checkout "$BRANCH"
git pull origin "$BRANCH"

echo "Reading version..."
if [ -f "$VERSION_FILE" ]; then
    LAST_VERSION=$(cat "$VERSION_FILE")
else
    LAST_VERSION=0
fi

if ! [[ "$LAST_VERSION" =~ ^[0-9]+$ ]]; then
    LAST_VERSION=0
fi

NEXT_VERSION=$((LAST_VERSION + 1))
IMAGE_TAG="v${NEXT_VERSION}"

echo "$NEXT_VERSION" > "$VERSION_FILE"

echo "Building image: $IMAGE:$IMAGE_TAG"
docker build -t "$IMAGE:$IMAGE_TAG" .

echo "Tagging latest..."
docker tag "$IMAGE:$IMAGE_TAG" "$IMAGE:latest"

echo "Logging in to Docker Hub..."
docker login -u ritamhudait

echo "Pushing images..."
docker push "$IMAGE:$IMAGE_TAG"
docker push "$IMAGE:latest"

echo "Deploying container..."
export IMAGE_TAG="$IMAGE_TAG"
docker compose --env-file "$HOME/pmis-env/.env" up -d --remove-orphans

echo "Cleaning unused images..."
docker image prune -f

echo "Done. Deployed version: $IMAGE_TAG"
