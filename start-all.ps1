param(
    [switch]$NoMock,
    [switch]$NoReload,
    [switch]$Restart
)

$ErrorActionPreference = "Stop"
$projectRoot = $PSScriptRoot
$serverRoot = Join-Path $projectRoot "server"
$webRoot = Join-Path $projectRoot "web"
$venvPython = Join-Path $serverRoot ".venv\Scripts\python.exe"
$processes = [System.Collections.Generic.List[System.Diagnostics.Process]]::new()

function Test-PortAvailable([int]$Port) {
    $listener = Get-NetTCPConnection -State Listen -LocalPort $Port -ErrorAction SilentlyContinue
    return $null -eq $listener
}

function Get-PortProcessIds([int]$Port) {
    return @(Get-NetTCPConnection -State Listen -LocalPort $Port -ErrorAction SilentlyContinue |
        Select-Object -ExpandProperty OwningProcess -Unique)
}

function Find-BootstrapPython {
    $bundled = Join-Path $projectRoot ".tools\python312\python.exe"
    if (Test-Path -LiteralPath $bundled) {
        return @{ File = $bundled; Args = @() }
    }
    if (Get-Command py.exe -ErrorAction SilentlyContinue) {
        return @{ File = "py.exe"; Args = @("-3") }
    }
    if (Get-Command python.exe -ErrorAction SilentlyContinue) {
        return @{ File = "python.exe"; Args = @() }
    }
    throw "Python 3.12 or newer was not found."
}

function Stop-ProcessTree([System.Diagnostics.Process]$Process) {
    if ($null -eq $Process -or $Process.HasExited) { return }
    $savedPreference = $ErrorActionPreference
    $ErrorActionPreference = "SilentlyContinue"
    & taskkill.exe /PID $Process.Id /T /F 2>$null | Out-Null
    if (-not $Process.HasExited) {
        try { $Process.Kill() } catch { }
    }
    $ErrorActionPreference = $savedPreference
}

function Start-ChildProcess(
    [string]$FileName,
    [string]$Arguments,
    [string]$WorkingDirectory
) {
    # Process.Start avoids a Windows PowerShell Start-Process bug when the
    # inherited environment contains both Path and PATH.
    $info = [System.Diagnostics.ProcessStartInfo]::new()
    $info.FileName = $FileName
    $info.Arguments = $Arguments
    $info.WorkingDirectory = $WorkingDirectory
    $info.UseShellExecute = $false
    $info.CreateNoWindow = $true
    return [System.Diagnostics.Process]::Start($info)
}

function Wait-Services([int[]]$Ports, [int]$TimeoutSeconds = 20) {
    $deadline = [DateTime]::UtcNow.AddSeconds($TimeoutSeconds)
    while ([DateTime]::UtcNow -lt $deadline) {
        foreach ($process in $processes) {
            if ($process.HasExited) {
                throw "A service stopped during startup (PID $($process.Id), exit code $($process.ExitCode))."
            }
        }
        $allReady = $true
        foreach ($port in $Ports) {
            if (Test-PortAvailable $port) { $allReady = $false; break }
        }
        if ($allReady) { return }
        Start-Sleep -Milliseconds 250
    }
    throw "Services did not become ready within $TimeoutSeconds seconds."
}

try {
    Write-Host "[CHECK] Personal Gateway Plus" -ForegroundColor Cyan

    if (-not (Test-Path -LiteralPath $venvPython)) {
        $python = Find-BootstrapPython
        Write-Host "[SETUP] Creating Python virtual environment..." -ForegroundColor Yellow
        & $python.File @($python.Args) -m venv (Join-Path $serverRoot ".venv")
        if ($LASTEXITCODE -ne 0) { throw "Failed to create Python virtual environment." }

        Write-Host "[SETUP] Installing backend dependencies..." -ForegroundColor Yellow
        & $venvPython -m pip install -r (Join-Path $serverRoot "requirements.txt")
        if ($LASTEXITCODE -ne 0) { throw "Failed to install backend dependencies." }
    }

    $envFile = Join-Path $serverRoot ".env"
    if (-not (Test-Path -LiteralPath $envFile)) {
        Copy-Item -LiteralPath (Join-Path $serverRoot ".env.example") -Destination $envFile
        Write-Host "[NOTICE] Created server\.env. Set GATEWAY_MASTER_KEY before saving real API keys." -ForegroundColor Yellow
    }

    $npmCommand = Get-Command npm.cmd -ErrorAction SilentlyContinue
    $nodeCommand = Get-Command node.exe -ErrorAction SilentlyContinue
    if (-not $npmCommand -or -not $nodeCommand) {
        throw "npm.cmd was not found. Install Node.js and add it to PATH."
    }
    if (-not (Test-Path -LiteralPath (Join-Path $webRoot "node_modules"))) {
        Write-Host "[SETUP] Installing Web dependencies..." -ForegroundColor Yellow
        Push-Location $webRoot
        try { & npm.cmd ci } finally { Pop-Location }
        if ($LASTEXITCODE -ne 0) { throw "Failed to install Web dependencies." }
    }

    $requiredPorts = @(8000, 5173)
    if (-not $NoMock) { $requiredPorts += 8100 }
    foreach ($port in $requiredPorts) {
        if (-not (Test-PortAvailable $port)) {
            $owners = @(Get-PortProcessIds $port)
            if ($Restart) {
                Write-Host "[RESTART] Stopping PID $($owners -join ', ') on port $port..." -ForegroundColor Yellow
                foreach ($ownerPid in $owners) {
                    $savedPreference = $ErrorActionPreference
                    $ErrorActionPreference = "SilentlyContinue"
                    & taskkill.exe /PID $ownerPid /T /F 2>$null | Out-Null
                    $ErrorActionPreference = $savedPreference
                }
                Start-Sleep -Milliseconds 500
                if (-not (Test-PortAvailable $port)) {
                    throw "Port $port could not be released. Close PID $($owners -join ', ') manually."
                }
            } else {
                throw "Port $port is already used by PID $($owners -join ', '). Stop the old service, or run .\start-all.bat -Restart."
            }
        }
    }

    $backendArgs = "-m uvicorn app.main:app --host 127.0.0.1 --port 8000"
    if (-not $NoReload) { $backendArgs += " --reload" }
    $backend = Start-ChildProcess $venvPython $backendArgs $serverRoot
    $processes.Add($backend)

    if (-not $NoMock) {
        $mock = Start-ChildProcess $venvPython "mock_upstream.py" $serverRoot
        $processes.Add($mock)
    }

    $viteEntry = Join-Path $webRoot "node_modules\vite\bin\vite.js"
    if (-not (Test-Path -LiteralPath $viteEntry)) {
        throw "Vite entry file was not found after installing Web dependencies."
    }
    $web = Start-ChildProcess $nodeCommand.Source "`"$viteEntry`" --host 127.0.0.1" $webRoot
    $processes.Add($web)

    Wait-Services $requiredPorts

    Write-Host ""
    Write-Host "[READY] Backend: http://127.0.0.1:8000" -ForegroundColor Green
    Write-Host "[READY] Web:     http://127.0.0.1:5173" -ForegroundColor Green
    if (-not $NoMock) {
        Write-Host "[READY] Mock:    http://127.0.0.1:8100" -ForegroundColor Green
    }
    Write-Host "Press Ctrl+C once to stop all services." -ForegroundColor Cyan

    while ($true) {
        foreach ($process in $processes) {
            if ($process.HasExited) {
                throw "A service stopped unexpectedly (PID $($process.Id), exit code $($process.ExitCode))."
            }
        }
        Start-Sleep -Seconds 1
    }
}
catch {
    if ($_.Exception.Message -notlike "*pipeline has been stopped*") {
        Write-Host "[ERROR] $($_.Exception.Message)" -ForegroundColor Red
    }
}
finally {
    Write-Host "`n[STOP] Shutting down all services..." -ForegroundColor Yellow
    foreach ($process in $processes) { Stop-ProcessTree $process }
    Write-Host "[STOP] Done." -ForegroundColor Green
}
