#!/bin/bash
# Test script for 'mc check' command

set -e

MC_CMD="./mc"
TEST_CASE="04349708"
WORKSPACE_PATH="/Users/dsquirre/Cases/IBM_Netherl_B_V/04349708-Transfe_of_ownersh_a_c"

echo "========================================="
echo "Testing: mc check command"
echo "========================================="

# Setup: Remove test workspace if it exists
echo "Setup: Cleaning up any existing test workspace"
rm -rf "${WORKSPACE_PATH}"

# Test 1: Check non-existent workspace (should return WARN)
echo ""
echo "Test 1: Check non-existent workspace"
OUTPUT=$(${MC_CMD} check ${TEST_CASE})
if echo "$OUTPUT" | grep -q "CheckStaus: WARN"; then
    echo "✓ PASS: Non-existent workspace returns WARN status"
else
    echo "✗ FAIL: Expected WARN status for non-existent workspace"
    echo "Output: $OUTPUT"
    exit 1
fi

# Test 2: Verify expected file paths are checked
echo ""
echo "Test 2: Verify expected paths are being checked"
if echo "$OUTPUT" | grep -q "00-caseComments.md" && \
   echo "$OUTPUT" | grep -q "files/attach" && \
   echo "$OUTPUT" | grep -q "10-notes.md"; then
    echo "✓ PASS: Expected paths are checked"
else
    echo "✗ FAIL: Not all expected paths were checked"
    exit 1
fi

# Test 3: Check with --fix flag (should create files)
echo ""
echo "Test 3: Check with --fix flag (creates missing files)"
${MC_CMD} check ${TEST_CASE} --fix > /dev/null
if [ -d "${WORKSPACE_PATH}" ] && \
   [ -f "${WORKSPACE_PATH}/00-caseComments.md" ] && \
   [ -d "${WORKSPACE_PATH}/files/attach" ]; then
    echo "✓ PASS: --fix flag created workspace files"
else
    echo "✗ FAIL: --fix flag did not create expected files"
    exit 1
fi

# Test 4: Check existing workspace (should return OK)
echo ""
echo "Test 4: Check existing workspace"
OUTPUT=$(${MC_CMD} check ${TEST_CASE})
if echo "$OUTPUT" | grep -q "CheckStaus: OK"; then
    echo "✓ PASS: Existing workspace returns OK status"
else
    echo "✗ FAIL: Expected OK status for existing workspace"
    echo "Output: $OUTPUT"
    exit 1
fi

# Cleanup
echo ""
echo "Cleanup: Removing test workspace"
rm -rf "${WORKSPACE_PATH}"

echo ""
echo "========================================="
echo "All tests for 'mc check' completed"
echo "========================================="
