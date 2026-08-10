$ErrorActionPreference = "Stop"

$serverRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$pythonPath = Join-Path $serverRoot ".venv\Scripts\python.exe"
$backendPort = 18000
$primaryPort = 18100
$backupPort = 18101
$databasePath = Join-Path $serverRoot "data\pgp-integration-$([guid]::NewGuid().ToString('N')).db"
$processes = @()

function Wait-Health([string]$url) {
    for ($attempt = 0; $attempt -lt 40; $attempt++) {
        try {
            $null = Invoke-RestMethod -Uri $url -TimeoutSec 1
            return
        } catch {
            Start-Sleep -Milliseconds 250
        }
    }
    throw "服务未就绪：$url"
}

function Post-Json([string]$url, [object]$body) {
    Invoke-RestMethod -Method Post -Uri $url -ContentType "application/json" `
        -Body ($body | ConvertTo-Json -Depth 10)
}

try {
    if (-not (Test-Path -LiteralPath $pythonPath)) {
        throw "未找到后端虚拟环境：$pythonPath"
    }

    $savedMockPort = $env:MOCK_PORT
    $env:MOCK_PORT = [string]$primaryPort
    $processes += Start-Process -FilePath $pythonPath `
        -ArgumentList "mock_upstream.py" -WorkingDirectory $serverRoot `
        -WindowStyle Hidden -PassThru
    $env:MOCK_PORT = [string]$backupPort
    $processes += Start-Process -FilePath $pythonPath `
        -ArgumentList "mock_upstream.py" -WorkingDirectory $serverRoot `
        -WindowStyle Hidden -PassThru
    if ($null -eq $savedMockPort) { Remove-Item Env:MOCK_PORT } else { $env:MOCK_PORT = $savedMockPort }

    $savedDatabase = $env:DATABASE_PATH
    $savedMasterKey = $env:GATEWAY_MASTER_KEY
    $env:DATABASE_PATH = $databasePath
    $env:GATEWAY_MASTER_KEY = "11" * 32
    $processes += Start-Process -FilePath $pythonPath `
        -ArgumentList "-m","uvicorn","app.main:app","--host","127.0.0.1","--port",$backendPort `
        -WorkingDirectory $serverRoot -WindowStyle Hidden -PassThru
    if ($null -eq $savedDatabase) { Remove-Item Env:DATABASE_PATH } else { $env:DATABASE_PATH = $savedDatabase }
    if ($null -eq $savedMasterKey) { Remove-Item Env:GATEWAY_MASTER_KEY } else { $env:GATEWAY_MASTER_KEY = $savedMasterKey }

    Wait-Health "http://127.0.0.1:$primaryPort/health"
    Wait-Health "http://127.0.0.1:$backupPort/health"
    Wait-Health "http://127.0.0.1:$backendPort/health"

    $primary = Post-Json "http://127.0.0.1:$backendPort/api/admin/upstreams" @{
        providerId = "deepseek"
        displayName = "Primary Mock"
        baseUrl = "http://127.0.0.1:$primaryPort"
        apiKey = "sk-primary-test"
        defaultModel = "mock-model"
        timeoutMs = 5000
    }
    $backup = Post-Json "http://127.0.0.1:$backendPort/api/admin/upstreams" @{
        providerId = "deepseek"
        displayName = "Backup Mock"
        baseUrl = "http://127.0.0.1:$backupPort"
        apiKey = "sk-backup-test"
        defaultModel = "mock-model"
        timeoutMs = 5000
    }
    $group = Post-Json "http://127.0.0.1:$backendPort/api/admin/groups" @{
        name = "Integration Group"
        routeKey = "integration-route"
        maxAttempts = 3
        enabled = $true
    }
    $null = Post-Json "http://127.0.0.1:$backendPort/api/admin/groups/$($group.id)/members" @{
        upstreamEndpointId = $primary.id
        upstreamModelName = "mock-primary-model"
        priorityRank = 1
    }
    $null = Post-Json "http://127.0.0.1:$backendPort/api/admin/groups/$($group.id)/members" @{
        upstreamEndpointId = $backup.id
        upstreamModelName = "mock-backup-model"
        priorityRank = 2
    }

    $chatBody = @{
        model = "integration-route"
        messages = @(@{ role = "user"; content = "integration test" })
        stream = $false
    }

    $scenarios = @("500", "timeout")
    foreach ($scenario in $scenarios) {
        $null = Invoke-RestMethod -Method Put `
            -Uri "http://127.0.0.1:$primaryPort/_mock/scenario" `
            -ContentType "application/json" `
            -Body (@{ scenario = $scenario } | ConvertTo-Json)

        $response = Invoke-WebRequest -UseBasicParsing -Method Post `
            -Uri "http://127.0.0.1:$backendPort/v1/chat/completions" `
            -ContentType "application/json" `
            -Body ($chatBody | ConvertTo-Json -Depth 10)
        if ($response.StatusCode -ne 200) { throw "$scenario 未返回 200" }
        if ($response.Headers["X-Upstream"] -ne "Backup Mock") {
            throw "$scenario 未切换到 Backup Mock"
        }
        $requestId = $response.Headers["X-Request-Id"]
        $attempts = Invoke-RestMethod `
            -Uri "http://127.0.0.1:$backendPort/api/admin/requests/$requestId/attempts"
        if ($attempts.Count -ne 2 -or $attempts[1].resultCategory -ne "success") {
            throw "$scenario 路由尝试链不正确"
        }
        Write-Output "PASS $scenario -> Backup Mock, requestId=$requestId, attempts=$($attempts.Count)"
    }
} finally {
    foreach ($process in $processes) {
        if ($process -and -not $process.HasExited) {
            Stop-Process -Id $process.Id -Force -ErrorAction SilentlyContinue
        }
    }
    if (Test-Path -LiteralPath $databasePath) {
        Remove-Item -LiteralPath $databasePath -Force
    }
}
