#!/bin/bash
# Test script for 'mc go' command

set -e

MC_CMD="./mc"
TEST_CASE="04349708"
EXPECTED_URL="https://gss--c.vf.force.com/apex/Case_View?sbstr=${TEST_CASE}"

echo "========================================="
echo "Testing: mc go command"
echo "========================================="

# Test 1: Basic URL generation
echo "Test 1: Generate Salesforce URL without launch"
OUTPUT=$(${MC_CMD} go ${TEST_CASE})
if [ "$OUTPUT" == "$EXPECTED_URL" ]; then
    echo "✓ PASS: URL generated correctly"
else
    echo "✗ FAIL: Expected '${EXPECTED_URL}', got '${OUTPUT}'"
    exit 1
fi

# Test 2: Launch flag (just verify no error, can't test actual browser launch)
echo ""
echo "Test 2: Launch flag --launch (should not error)"
${MC_CMD} go ${TEST_CASE} --launch && echo "✓ PASS: Launch command executed without error" || echo "✗ FAIL: Launch command failed"

echo ""
echo "========================================="
echo "All tests for 'mc go' completed"
echo "========================================="
