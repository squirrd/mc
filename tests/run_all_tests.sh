#!/bin/bash
# Run all mc command tests

set -e

echo "========================================="
echo "Running ALL mc command tests"
echo "========================================="
echo ""

# Change to project root directory
cd "$(dirname "$0")/.."

# Track test results
TESTS_PASSED=0
TESTS_FAILED=0
FAILED_TESTS=()

# Function to run a test and track results
run_test() {
    local test_name=$1
    local test_script=$2

    echo ""
    echo "Running: ${test_name}"
    echo "-----------------------------------------"

    if bash "${test_script}"; then
        ((TESTS_PASSED++))
        echo "✓ ${test_name} PASSED"
    else
        ((TESTS_FAILED++))
        FAILED_TESTS+=("${test_name}")
        echo "✗ ${test_name} FAILED"
    fi
    echo ""
}

# Run all tests
run_test "mc go" "tests/test_go.sh"
run_test "mc ls" "tests/test_ls.sh"
run_test "mc check" "tests/test_check.sh"
run_test "mc create" "tests/test_create.sh"
run_test "mc case-comments" "tests/test_case_comments.sh"

# Print summary
echo "========================================="
echo "TEST SUMMARY"
echo "========================================="
echo "Total Passed: ${TESTS_PASSED}"
echo "Total Failed: ${TESTS_FAILED}"

if [ ${TESTS_FAILED} -gt 0 ]; then
    echo ""
    echo "Failed tests:"
    for test in "${FAILED_TESTS[@]}"; do
        echo "  - ${test}"
    done
    exit 1
else
    echo ""
    echo "✓ All tests passed!"
fi
