# QueueCTL Manual Test Script (PowerShell)
# Run from: e:\DA\QueueCTL\queuectl

$env:PYTHONPATH = "."
$PYTHON = "..\.venv\Scripts\python"

Write-Host "============================================" -ForegroundColor Cyan
Write-Host "QueueCTL Manual Test Script" -ForegroundColor Cyan
Write-Host "============================================" -ForegroundColor Cyan

# Clean up previous test data
Remove-Item -Recurse -Force "$env:USERPROFILE\.queuectl" -ErrorAction SilentlyContinue
Write-Host "[SETUP] Cleaned up previous data" -ForegroundColor Yellow

Write-Host ""
Write-Host "============================================" -ForegroundColor Cyan
Write-Host "TEST 1: Successful Job" -ForegroundColor Cyan
Write-Host "============================================" -ForegroundColor Cyan
& $PYTHON -m queuectl.main enqueue --command "echo Hello"
Write-Host "[TEST 1] Enqueued successful job"
Write-Host "Starting worker for 3 seconds..."
$job = Start-Job -ScriptBlock { 
    Set-Location $using:PWD
    $env:PYTHONPATH = "."
    & $using:PYTHON -m queuectl.main worker start --foreground 
}
Start-Sleep 3
Stop-Job $job -ErrorAction SilentlyContinue
& $PYTHON -m queuectl.main list --state completed
Write-Host "[TEST 1] PASS if job shows as completed" -ForegroundColor Green

Write-Host ""
Write-Host "============================================" -ForegroundColor Cyan
Write-Host "TEST 2: Failing Job with Retries" -ForegroundColor Cyan
Write-Host "============================================" -ForegroundColor Cyan
& $PYTHON -m queuectl.main enqueue --command "exit 1" --retries 2
Write-Host "[TEST 2] Enqueued failing job with 2 retries"
Write-Host "Starting worker for 15 seconds (waiting for retries)..."
$job = Start-Job -ScriptBlock { 
    Set-Location $using:PWD
    $env:PYTHONPATH = "."
    & $using:PYTHON -m queuectl.main worker start --foreground 
}
Start-Sleep 15
Stop-Job $job -ErrorAction SilentlyContinue
& $PYTHON -m queuectl.main dlq list
Write-Host "[TEST 2] PASS if job shows in DLQ" -ForegroundColor Green

Write-Host ""
Write-Host "============================================" -ForegroundColor Cyan
Write-Host "TEST 3: Configuration" -ForegroundColor Cyan
Write-Host "============================================" -ForegroundColor Cyan
& $PYTHON -m queuectl.main config set max-retries 5
& $PYTHON -m queuectl.main config get max-retries
& $PYTHON -m queuectl.main config list
Write-Host "[TEST 3] PASS if config values shown correctly" -ForegroundColor Green

Write-Host ""
Write-Host "============================================" -ForegroundColor Cyan
Write-Host "TEST 4: Status Overview" -ForegroundColor Cyan
Write-Host "============================================" -ForegroundColor Cyan
& $PYTHON -m queuectl.main status
Write-Host "[TEST 4] PASS if status shows job counts" -ForegroundColor Green

Write-Host ""
Write-Host "============================================" -ForegroundColor Cyan
Write-Host "All tests completed!" -ForegroundColor Green
Write-Host "============================================" -ForegroundColor Cyan
