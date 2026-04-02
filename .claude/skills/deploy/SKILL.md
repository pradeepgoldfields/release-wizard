---
name: deploy
description: Build the Conduit Docker image, verify it starts cleanly, and optionally push to the registry or apply the Helm chart.
argument-hint: "[local|push|helm-dev|helm-prod] [image-tag]"
---

# Deploy — Conduit

Target: **$ARGUMENTS** (defaults to `local` if empty)

## local — Build and smoke-test locally

```bash
# Build the image
docker build -t conduit:local .

# Run it
docker run --rm -p 8080:8080 conduit:local &
CONTAINER_PID=$!

# Wait for startup
sleep 3

# Health check
curl -sf http://localhost:8080/healthz && echo "✅ /healthz OK" || echo "❌ /healthz FAILED"
curl -sf http://localhost:8080/readyz  && echo "✅ /readyz OK"  || echo "❌ /readyz FAILED"

# Stop
kill $CONTAINER_PID 2>/dev/null
```

## push — Build and push to registry

```bash
# Requires IMAGE_REPO set in Jenkinsfile or environment
IMAGE_TAG="${1:-latest}"
docker build -t ${IMAGE_REPO}/conduit:${IMAGE_TAG} .
docker push ${IMAGE_REPO}/conduit:${IMAGE_TAG}
```

## helm-dev — Deploy to dev namespace via Helm

```bash
helm lint ./helm/conduit
helm upgrade --install conduit ./helm/conduit \
  -f helm/conduit/values-dev.yaml \
  --set image.tag=${IMAGE_TAG:-latest} \
  --set secrets.databaseUrl="sqlite:///instance/conduit.db" \
  -n conduit-dev --create-namespace
kubectl rollout status deployment/conduit -n conduit-dev
```

## helm-prod — Deploy to prod (requires manual tag confirmation)

```bash
# Only on release/* branches
helm upgrade --install conduit ./helm/conduit \
  -f helm/conduit/values-prod.yaml \
  --set image.tag=${IMAGE_TAG} \
  -n conduit --create-namespace
```

Report the outcome of each step and stop if anything fails.
