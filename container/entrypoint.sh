#!/bin/bash
# MC Container Entrypoint Script
#
# This script initializes the container environment before dropping into an
# interactive bash shell. It sets up environment variables, customizes the
# shell prompt, and changes to the workspace directory.
#
# Environment variables expected:
# - CASE_NUMBER: Case number (e.g., "12345678") passed from ContainerManager
# - CUSTOMER_NAME: Customer name passed from ContainerManager
# - MC_RUNTIME_MODE: Set to "agent" via Containerfile ENV directive
#
# Usage:
#   Called automatically via ENTRYPOINT directive in Containerfile
#   Not intended for manual execution

set -euo pipefail

# Export case metadata with defaults
# These environment variables are set by ContainerManager when creating the container
# Default to "unknown" if not provided (edge case for manual container runs)
export CASE_NUMBER="${CASE_NUMBER:-unknown}"
export CUSTOMER_NAME="${CUSTOMER_NAME:-unknown}"
export WORKSPACE_PATH="/case"

# Customize shell prompt to show case number
# Format matches CONTEXT.md requirement: [case-12345678]$
# \w shows current working directory, \$ shows $ for regular user (# for root)
export PS1="[case-${CASE_NUMBER}]\$ "

# Change to workspace directory
# Fallback to root if workspace not mounted (shouldn't happen in normal operation)
cd "${WORKSPACE_PATH}" || cd /

# Execute command passed as arguments
# Default from CMD directive: /bin/bash
# Using exec replaces entrypoint process with bash (proper signal handling for PID 1)
exec "$@"
