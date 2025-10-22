#!/usr/bin/env bash
set -eo pipefail
#set -x

export TARGET="dataset-curation"
export NAMESPACE=${TARGET}
export CONTEXT="gke_teknoir_us-central1-c_teknoir-cluster"
export PROJECT="teknoir"
export CLUSTER="teknoir-cluster"
export DOMAIN="teknoir.cloud"

context_exists() {
    kubectl config get-contexts -o name | grep -q "^$1$"
}

check_port() {
    local port=$1
    if nc -z localhost $port 2>/dev/null; then
        return 0  # Port is in use
    else
        return 1  # Port is free
    fi
}

# Function to check if a specific service is already running
check_service_running() {
    local service=$1
    local port=$2
    local pidfile="/tmp/compass/$service.pid"

    # Check if pidfile exists and process is still running
    if [ -f "$pidfile" ]; then
        local pid=$(cat "$pidfile")
        if kill -0 "$pid" 2>/dev/null; then
            echo "[$service] Already running (PID: $pid)"
            return 0
        else
            echo "[$service] Stale pidfile found, removing..."
            rm "$pidfile"
            return 1
        fi
    fi

    # Check if port is in use (might be running from another terminal)
    if check_port $port; then
        echo "[$service] Port $port is already in use (running from another terminal?)"
        return 0
    fi

    return 1
}

port_forward() {
  echo "kubectl --context=$CONTEXT port-forward -n $4 svc/$1"
  kubectl --context=$CONTEXT port-forward -n "$4" svc/$1 $2:$3 2>&1 &
  child_pid=$!
  echo "$child_pid" > "/tmp/compass/$service.pid"
}

if context_exists "$CONTEXT"; then
  export CONTEXT="$CONTEXT"
else
  export CONTEXT="teknoir"
fi

kubectl config use-context ${CONTEXT}

if [ -z "$TARGET" ]; then
    echo "Error: No target specified. Please specify a target with -t or --target"
    echo "Usage: $0 -t <target>"
    echo "Available targets: demonstrations, victra-poc, teknoir-ai, boxer-property"
    exit 1
fi

echo "Using context: $CONTEXT"
echo "Using namespace: $NAMESPACE"


#export -f port_forward

forward_and_catch() {
  service=$1
  port_from=$2
  prot_to=$3
  ns=$4
  echo "[$service] Starting port forwarding"
  has_error=true
  while [[ "${has_error}" == "true" ]]; do
    exec 3< <(port_forward ${service} ${port_from} ${prot_to} ${ns})
    has_error=false
    while IFS= read <&3 line && [[ "${has_error}" == "false" ]]
      do
        child_pid=$(cat "/tmp/compass/$service.pid")
        if [[ $line == *"broken pipe"* || $line == *"Timeout"* ]]; then
          echo "[$service] ERROR: $line"
          kill -9 "$child_pid"
          echo "[$service] Restarting port forwarding"
          has_error=true
          break
        else
          echo "[$service][$child_pid] $line"
        fi
      done
  done
  echo "[$service] Port forwarding has stopped"
}


if ! check_service_running "auto-labeler-backend" 8081; then
    forward_and_catch "auto-labeler-backend" 8081 8000 "$NAMESPACE" &
fi

echo "Waiting for essential services..."
for i in {1..30}; do
    if nc -z localhost 8081 2>/dev/null; then
        echo "Essential services are ready!"
        break
    fi
    if [ $i -eq 30 ]; then
        echo "Timeout waiting for services"
        exit 1
    fi
    sleep 1
done

cleanup() {
    echo "Cleaning up port forwarding processes..."
    if [ -d "/tmp/compass" ]; then
        for pidfile in /tmp/compass/*.pid; do
            if [ -f "$pidfile" ]; then
                pid=$(cat "$pidfile")
                kill -9 "$pid" 2>/dev/null || true
                rm "$pidfile"
            fi
        done
    fi
}

trap cleanup EXIT

# Start the app after port forwarding
echo "Starting ..."
export EXPORT_API_BASE="http://localhost:8081/dataset-curation/auto-labeler-labeler/api"
curl -X GET "${EXPORT_API_BASE}/batches/tattoo2k25/tracks/export?status_filter=complete"
python scripts/export_via_api.py


# Wait for all background processes to complete
echo "All background tasks have completed."

