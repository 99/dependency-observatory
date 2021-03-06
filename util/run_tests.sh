#!/bin/bash

# requires a running api container
CONTAINER_NAME=${CONTAINER_NAME:-$(kubectl get pods -l io.kompose.service=api -o go-template --template '{{range .items}}{{.metadata.name}}{{"\n"}}{{end}}')}

kubectl exec -it "$CONTAINER_NAME" -- pytest -c /app/pyproject.toml /app/tests /app/depobs/ "$@"
