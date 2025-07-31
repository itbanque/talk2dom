#!/bin/bash

set -e

# Deploy ConfigMap (recommended to delete and recreate before each deployment)
echo "📦 Creating configmap from .env..."
kubectl delete configmap talk2dom-env --ignore-not-found
kubectl create configmap talk2dom-env --from-env-file=.env

# Deploy using Helm
echo "🚀 Deploying with Helm..."
helm upgrade --install talk2dom ./charts/talk2dom-api

# Check rollout status
echo "🔍 Waiting for pod to be ready..."
kubectl rollout status deployment/talk2dom-api

# Print service information
echo "✅ All done. Current service endpoints:"
kubectl get svc talk2dom-service