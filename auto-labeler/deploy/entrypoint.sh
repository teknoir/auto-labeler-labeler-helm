#!/usr/bin/env bash
set -e

echo "Starting auto-labeler..."
envsubst '${BASE_PATH}' < /etc/nginx/nginx.conf.template > /etc/nginx/conf.d/default.conf

nginx -g daemon off;