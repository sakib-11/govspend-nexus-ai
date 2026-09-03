#!/bin/bash
# Helper functions for Docker registry

registry_list() {
    local port=${1:-5000}
    curl -s "http://localhost:$port/v2/_catalog" | jq .
}

registry_tags() {
    local repo=$1
    local port=${2:-5000}
    curl -s "http://localhost:$port/v2/$repo/tags/list" | jq .
}

registry_delete() {
    local repo=$1
    local tag=$2
    local port=${3:-5000}
    
    # Get digest
    digest=$(curl -s -I "http://localhost:$port/v2/$repo/manifests/$tag" \
        | grep -i "Docker-Content-Digest" \
        | awk '{print $2}' \
        | tr -d '\r')
    
    if [ -n "$digest" ]; then
        curl -X DELETE "http://localhost:$port/v2/$repo/manifests/$digest"
        echo "✅ Deleted $repo:$tag"
    else
        echo "❌ Failed to get digest for $repo:$tag"
    fi
}

registry_gc() {
    local port=${1:-5000}
    echo "Running garbage collection..."
    docker exec govspend-registry bin/registry garbage-collect /etc/docker/registry/config.yml
    echo "✅ GC complete"
}

# Usage
if [ "${BASH_SOURCE[0]}" != "${0}" ]; then
    # Script is being sourced, export functions
    export -f registry_list registry_tags registry_delete registry_gc
else
    # Script is being executed
    case "$1" in
        list)
            registry_list "$2"
            ;;
        tags)
            registry_tags "$2" "$3"
            ;;
        delete)
            registry_delete "$2" "$3" "$4"
            ;;
        gc)
            registry_gc "$2"
            ;;
        *)
            echo "Usage: source $0  # to import functions"
            echo "  Then use:"
            echo "    registry_list [port]"
            echo "    registry_tags <repo> [port]"
            echo "    registry_delete <repo> <tag> [port]"
            echo "    registry_gc [port]"
            ;;
    esac
fi
