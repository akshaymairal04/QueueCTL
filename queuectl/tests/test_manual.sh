#!/usr/bin/env bash
# QueueCTL Manual Test Script
# Run from: e:\DA\QueueCTL\queuectl
# Usage: ..\venv\Scripts\python -m queuectl.main <command>

# Set up environment
export PYTHONPATH="."
PYTHON="../.venv/Scripts/python"
QUEUECTL="$PYTHON -m queuectl.main"

echo "============================================"
echo "QueueCTL Manual Test Script"
echo "============================================"

# Clean up previous test data
rm -rf ~/.queuectl 2>/dev/null
echo "[SETUP] Cleaned up previous data"

echo ""
echo "============================================"
echo "TEST 1: Successful Job"
echo "============================================"
$QUEUECTL enqueue --command "echo 'Hello, World!'"
echo "[TEST 1] Enqueued successful job"
$QUEUECTL worker start --foreground &
WORKER_PID=$!
sleep 3
kill $WORKER_PID 2>/dev/null
$QUEUECTL list --state completed
echo "[TEST 1] PASS if job shows as completed"

echo ""
echo "============================================"
echo "TEST 2: Failing Job with Retries"
echo "============================================"
$QUEUECTL enqueue --command "exit 1" --retries 2
echo "[TEST 2] Enqueued failing job with 2 retries"
$QUEUECTL worker start --foreground &
WORKER_PID=$!
sleep 10
kill $WORKER_PID 2>/dev/null
$QUEUECTL list --state pending
$QUEUECTL list --state dead
echo "[TEST 2] PASS if job moved to dead after retries"

echo ""
echo "============================================"
echo "TEST 3: DLQ Operations"
echo "============================================"
$QUEUECTL dlq list
JOB_ID=$($QUEUECTL dlq list | grep -oE '[a-f0-9-]{36}' | head -1)
if [ -n "$JOB_ID" ]; then
    $QUEUECTL dlq retry $JOB_ID
    $QUEUECTL list --state pending
    echo "[TEST 3] PASS if job moved back to pending"
else
    echo "[TEST 3] SKIP - no jobs in DLQ"
fi

echo ""
echo "============================================"
echo "TEST 4: Multiple Workers"
echo "============================================"
$QUEUECTL enqueue --command "echo 'Job 1'"
$QUEUECTL enqueue --command "echo 'Job 2'"
$QUEUECTL enqueue --command "echo 'Job 3'"
$QUEUECTL worker start --count 2
sleep 2
$QUEUECTL worker list
$QUEUECTL worker stop
$QUEUECTL list --state completed
echo "[TEST 4] PASS if all jobs completed and workers stopped"

echo ""
echo "============================================"
echo "TEST 5: Configuration"
echo "============================================"
$QUEUECTL config set max-retries 5
$QUEUECTL config get max-retries
$QUEUECTL config list
echo "[TEST 5] PASS if config values shown correctly"

echo ""
echo "============================================"
echo "TEST 6: Status Overview"
echo "============================================"
$QUEUECTL status
echo "[TEST 6] PASS if status shows job counts"

echo ""
echo "============================================"
echo "All tests completed!"
echo "============================================"
