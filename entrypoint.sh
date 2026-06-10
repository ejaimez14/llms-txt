#!/bin/sh
set -e
if [ -n "$GITHUB_TOKEN" ]; then
    git config --global user.email "agent@llms-txt.internal"
    git config --global user.name "llms-txt Agent"
    GH_TOKEN="$GITHUB_TOKEN" gh auth setup-git
fi
exec "$@"
