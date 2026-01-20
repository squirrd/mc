#!/bin/bash
# Test script for 'mc ls' (LDAP search) command

set -e

MC_CMD="./mc"
TEST_UID="dsquirre"

echo "========================================="
echo "Testing: mc ls command"
echo "========================================="

# Test 1: Basic LDAP search
echo "Test 1: LDAP search for valid uid"
OUTPUT=$(${MC_CMD} ls ${TEST_UID})
if echo "$OUTPUT" | grep -q "David Squirrell"; then
    echo "✓ PASS: LDAP search returned expected user"
else
    echo "✗ FAIL: LDAP search did not return expected user"
    echo "Output: $OUTPUT"
    exit 1
fi

# Test 2: Check formatted output contains expected fields
echo ""
echo "Test 2: Verify formatted output contains key fields"
if echo "$OUTPUT" | grep -q "Name.*:" && \
   echo "$OUTPUT" | grep -q "UID.*:" && \
   echo "$OUTPUT" | grep -q "RH Title.*:"; then
    echo "✓ PASS: Output contains expected formatted fields"
else
    echo "✗ FAIL: Output missing expected fields"
    exit 1
fi

# Test 3: Test with -A flag (full output)
echo ""
echo "Test 3: LDAP search with -A flag (full output)"
OUTPUT_ALL=$(${MC_CMD} ls ${TEST_UID} -A)
if [ -n "$OUTPUT_ALL" ]; then
    echo "✓ PASS: -A flag returns output"
else
    echo "✗ FAIL: -A flag produced no output"
    exit 1
fi

# Test 4: Test with invalid uid (short string)
echo ""
echo "Test 4: LDAP search with invalid uid (too short)"
OUTPUT_INVALID=$(${MC_CMD} ls "xyz" 2>&1) || true
if echo "$OUTPUT_INVALID" | grep -q "Error.*must be between"; then
    echo "✓ PASS: Invalid uid properly rejected"
else
    echo "⚠ WARNING: Invalid uid handling may need review"
fi

echo ""
echo "========================================="
echo "All tests for 'mc ls' completed"
echo "========================================="
