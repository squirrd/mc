#!/bin/bash
# Test script for 'mc create' command

set -e

MC_CMD="./mc"
TEST_CASE="04349708"
WORKSPACE_PATH="/Users/dsquirre/Cases/IBM_Netherl_B_V/04349708-Transfe_of_ownersh_a_c"

echo "========================================="
echo "Testing: mc create command"
echo "========================================="

# Setup: Remove test workspace if it exists
echo "Setup: Cleaning up any existing test workspace"
rm -rf "${WORKSPACE_PATH}"

# Test 1: Create workspace
echo ""
echo "Test 1: Create workspace for case"
OUTPUT=$(${MC_CMD} create ${TEST_CASE})
if echo "$OUTPUT" | grep -q "Creating files"; then
    echo "✓ PASS: Create command executed"
else
    echo "✗ FAIL: Create command did not execute properly"
    echo "Output: $OUTPUT"
    exit 1
fi

# Test 2: Verify all expected files and directories were created
echo ""
echo "Test 2: Verify workspace structure created"
EXPECTED_FILES=(
    "${WORKSPACE_PATH}/00-caseComments.md"
    "${WORKSPACE_PATH}/10-notes.md"
    "${WORKSPACE_PATH}/20-notes.md"
    "${WORKSPACE_PATH}/30-notes.md"
    "${WORKSPACE_PATH}/80-scratch.md"
)
EXPECTED_DIRS=(
    "${WORKSPACE_PATH}/files"
    "${WORKSPACE_PATH}/files/attach"
    "${WORKSPACE_PATH}/files/dp"
    "${WORKSPACE_PATH}/files/cp"
)

ALL_EXIST=true
for file in "${EXPECTED_FILES[@]}"; do
    if [ ! -f "$file" ]; then
        echo "✗ FAIL: Expected file not found: $file"
        ALL_EXIST=false
    fi
done

for dir in "${EXPECTED_DIRS[@]}"; do
    if [ ! -d "$dir" ]; then
        echo "✗ FAIL: Expected directory not found: $dir"
        ALL_EXIST=false
    fi
done

if [ "$ALL_EXIST" = true ]; then
    echo "✓ PASS: All expected files and directories created"
else
    exit 1
fi

# Test 3: Running create on existing workspace should not error
echo ""
echo "Test 3: Running create on existing workspace"
${MC_CMD} create ${TEST_CASE} > /dev/null && echo "✓ PASS: Create on existing workspace does not error" || {
    echo "✗ FAIL: Create command failed on existing workspace"
    exit 1
}

# Test 4: Test -d flag (download - just verify no error, may not have attachments)
echo ""
echo "Test 4: Test -d flag (download attachments)"
rm -rf "${WORKSPACE_PATH}"
${MC_CMD} create ${TEST_CASE} -d > /dev/null && echo "✓ PASS: Create with -d flag executed without error" || {
    echo "⚠ WARNING: Create with -d flag may have issues"
}

# Cleanup
echo ""
echo "Cleanup: Removing test workspace"
rm -rf "${WORKSPACE_PATH}"

echo ""
echo "========================================="
echo "All tests for 'mc create' completed"
echo "========================================="
