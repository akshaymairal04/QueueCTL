# QueueCTL Advanced Test Script (PowerShell)
# Covers: Custom IDs, Concurrency, Config Changes, DLQ Clearing via Flags

$env:PYTHONPATH = "."
$PYTHON = "..\.venv\Scripts\python"

Write-Host "============================================" -ForegroundColor Cyan
Write-Host "QueueCTL Advanced Test Suite" -ForegroundColor Cyan
Write-Host "============================================" -ForegroundColor Cyan

# 0. Clean Slatte
Remove-Item -Recurse -Force "$env:USERPROFILE\.queuectl" -ErrorAction SilentlyContinue
Write-Host "[INIT] Cleaned environment" -ForegroundColor Yellow

# 1. Config Test
Write-Host "`n[TEST 1] Configuration Changes" -ForegroundColor Cyan
& $PYTHON -m queuectl.main config set poll-interval 0.5
& $PYTHON -m queuectl.main config set max-retries 5
$val = & $PYTHON -m queuectl.main config get poll-interval | Out-String
if ($val -match "0.5") { Write-Host "✓ Config updated" -ForegroundColor Green } else { Write-Host "✗ Config fail" -ForegroundColor Red }

# 2. Custom ID via Flags (Bypassing JSON escaping issues)
Write-Host "`n[TEST 2] Custom ID via Flags" -ForegroundColor Cyan
& $PYTHON -m queuectl.main enqueue --command "echo CUSTOM_ID_JOB" --retries 0 --id "custom-job-123"
$status = & $PYTHON -m queuectl.main status custom-job-123 | Out-String
if ($status -match "custom-job-123") { Write-Host "✓ Custom ID accepted" -ForegroundColor Green } else { Write-Host "✗ Custom ID fail" -ForegroundColor Red }

# 3. Concurrency (Sleeping Jobs)
Write-Host "`n[TEST 3] Concurrency (3 Parallel Workers)" -ForegroundColor Cyan
& $PYTHON -m queuectl.main enqueue --command "timeout 3"
& $PYTHON -m queuectl.main enqueue --command "timeout 3"
& $PYTHON -m queuectl.main enqueue --command "timeout 3"

# Start 3 workers
Write-Host "Starting 3 workers..."
$job = Start-Job -ScriptBlock { 
    Set-Location $using:PWD
    $env:PYTHONPATH = "."
    & $using:PYTHON -m queuectl.main worker start --count 3 --interval 0.5
}

Start-Sleep 5
$running = & $PYTHON -m queuectl.main worker list | Out-String
Write-Host $running
Start-Sleep 5 # Wait for jobs to finish

Stop-Job $job -ErrorAction SilentlyContinue
& $PYTHON -m queuectl.main worker stop

# Verify all completed
$list = & $PYTHON -m queuectl.main list --state completed | Out-String
if ($list -match "timeout 3") { Write-Host "✓ Parallel jobs completed" -ForegroundColor Green } else { Write-Host "✗ Parallel jobs fail" -ForegroundColor Red }

# 4. DLQ Clearing
Write-Host "`n[TEST 4] DLQ Cleanup" -ForegroundColor Cyan
& $PYTHON -m queuectl.main enqueue --command "exit 1" --retries 0
# Process it (start worker briefly)
$djob = Start-Job -ScriptBlock { 
    Set-Location $using:PWD
    $env:PYTHONPATH = "."
    & $using:PYTHON -m queuectl.main worker start --foreground --interval 0.1
}
Start-Sleep 5
Stop-Job $djob -ErrorAction SilentlyContinue

& $PYTHON -m queuectl.main dlq list
& $PYTHON -m queuectl.main dlq clear --force
$dlq = & $PYTHON -m queuectl.main dlq list | Out-String
if ($dlq -match "No jobs") { Write-Host "✓ DLQ Cleared" -ForegroundColor Green } else { Write-Host "✗ DLQ Clear fail" -ForegroundColor Red }

Write-Host "`n============================================" -ForegroundColor Cyan
Write-Host "Tests Completed" -ForegroundColor Cyan
Write-Host "============================================" -ForegroundColor Cyan
