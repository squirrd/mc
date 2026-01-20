#!/bin/bash
# Test script for 'mc case-comments' command
# NOTE: This command should be renamed to 'mc case-comments' or similar

set -e

MC_CMD="./mc"
TEST_CASE="04349708"

echo "========================================="
echo "Testing: mc case-comments command"
echo "========================================="
echo "NOTE: This command fetches case comments, not actual OCM login"
echo "      Should be renamed to avoid confusion with 'mc case' architecture"
echo ""

# Test 1: Fetch case comments
echo "Test 1: Fetch case comments"
OUTPUT=$(${MC_CMD} case-comments ${TEST_CASE})
if echo "$OUTPUT" | grep -q "Logging into OCM backplane"; then
    echo "✓ PASS: Command executed and fetched data"
else
    echo "✗ FAIL: Command did not execute properly"
    echo "Output: $OUTPUT"
    exit 1
fi

# Test 2: Verify comments structure (should contain comment data)
echo ""
echo "Test 2: Verify comments data structure"
if echo "$OUTPUT" | grep -q "caseNumber" && \
   echo "$OUTPUT" | grep -q "commentBody"; then
    echo "✓ PASS: Comments contain expected data structure"
else
    echo "✗ FAIL: Comments missing expected data fields"
    exit 1
fi

# Test 3: Verify API authentication works (should fetch comments without error)
echo ""
echo "Test 3: Verify API authentication"
${MC_CMD} case-comments ${TEST_CASE} > /dev/null 2>&1 && echo "✓ PASS: API authentication successful" || {
    echo "✗ FAIL: API authentication failed"
    exit 1
}

echo ""
echo "========================================="
echo "All tests for 'mc case-comments' completed"
echo "========================================="
echo ""
echo "REMINDER: Rename this command to 'mc case-comments' or similar"
