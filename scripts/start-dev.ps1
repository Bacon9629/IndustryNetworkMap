param(
    [switch]$SkipInstall,
    [switch]$SkipImport,
    [switch]$NoOpen
)

$ErrorActionPreference = "Stop"

$Root = Resolve-Path (Join-Path $PSScriptRoot "..")
$InfraDir = Join-Path $Root "infra"
$IngestionDir = Join-Path $Root "ingestion"
$BackendDir = Join-Path $Root "backend"
$FrontendDir = Join-Path $Root "frontend"
$FrontendNextDir = Join-Path $FrontendDir ".next"

function Test-Command {
    param([string]$Name)
    $null -ne (Get-Command $Name -ErrorAction SilentlyContinue)
}

function Test-Port {
    param(
        [string]$HostName = "127.0.0.1",
        [int]$Port
    )
    $client = [System.Net.Sockets.TcpClient]::new()
    try {
        $task = $client.ConnectAsync($HostName, $Port)
        if (-not $task.Wait(300)) {
            return $false
        }
        return $client.Connected
    }
    catch {
        return $false
    }
    finally {
        $client.Dispose()
    }
}

function Wait-Port {
    param(
        [string]$Name,
        [int]$Port,
        [int]$TimeoutSeconds = 60
    )
    $deadline = (Get-Date).AddSeconds($TimeoutSeconds)
    while ((Get-Date) -lt $deadline) {
        if (Test-Port -Port $Port) {
            Write-Host "$Name is ready on port $Port."
            return
        }
        Start-Sleep -Seconds 1
    }
    throw "$Name did not become ready on port $Port within $TimeoutSeconds seconds."
}

function Test-HttpOk {
    param([string]$Url)
    try {
        $response = Invoke-WebRequest -UseBasicParsing -Uri $Url -TimeoutSec 5
        return $response.StatusCode -ge 200 -and $response.StatusCode -lt 500
    }
    catch {
        return $false
    }
}

function Stop-PortProcess {
    param([int]$Port)
    $connections = Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue
    $processIds = $connections | Select-Object -ExpandProperty OwningProcess -Unique
    foreach ($processId in $processIds) {
        if ($processId -and $processId -ne $PID) {
            Stop-Process -Id $processId -Force
        }
    }
}

function Start-DevWindow {
    param(
        [string]$Title,
        [string]$WorkingDirectory,
        [string]$Command
    )
    $quotedDir = $WorkingDirectory.Replace("'", "''")
    $quotedCommand = $Command.Replace("'", "''")
    $psCommand = "& { `$Host.UI.RawUI.WindowTitle = '$Title'; Set-Location '$quotedDir'; $quotedCommand }"
    Start-Process powershell -ArgumentList @(
        "-NoExit",
        "-ExecutionPolicy", "Bypass",
        "-Command", $psCommand
    ) | Out-Null
}

Set-Location $Root
Write-Host "IndustryNetworkMap dev startup"
Write-Host "Root: $Root"

if (-not (Test-Command "docker")) {
    throw "Docker was not found in PATH. Start Docker Desktop, then run this script again."
}
if (-not (Test-Command "python")) {
    throw "Python was not found in PATH."
}
if (-not (Test-Command "npm")) {
    throw "npm was not found in PATH."
}

Write-Host ""
Write-Host "Starting Neo4j..."
Push-Location $InfraDir
try {
    docker compose up -d
}
finally {
    Pop-Location
}
Wait-Port -Name "Neo4j Bolt" -Port 7687 -TimeoutSeconds 90

if (-not $SkipInstall) {
    Write-Host ""
    Write-Host "Installing Python dependencies..."
    Push-Location $IngestionDir
    try {
        python -m pip install -r requirements.txt
    }
    finally {
        Pop-Location
    }

    Push-Location $BackendDir
    try {
        python -m pip install -r requirements.txt
    }
    finally {
        Pop-Location
    }

    Write-Host ""
    Write-Host "Installing frontend dependencies..."
    Push-Location $FrontendDir
    try {
        npm install
    }
    finally {
        Pop-Location
    }
}

if (-not $SkipImport) {
    Write-Host ""
    Write-Host "Validating and importing seed graph..."
    Push-Location $IngestionDir
    try {
        python validators/validate.py
        python scripts/import_graph.py
    }
    finally {
        Pop-Location
    }
}

Write-Host ""
if (Test-Port -Port 8000) {
    Write-Host "Backend already appears to be running on http://localhost:8000."
}
else {
    Write-Host "Opening backend server window..."
    Start-DevWindow -Title "IndustryNetworkMap Backend :8000" -WorkingDirectory $BackendDir -Command "python -m uvicorn app.main:app --port 8000"
    Wait-Port -Name "Backend" -Port 8000 -TimeoutSeconds 45
}

if ((Test-Port -Port 3000) -and (Test-HttpOk -Url "http://localhost:3000")) {
    Write-Host "Frontend already appears to be running on http://localhost:3000."
}
else {
    if (Test-Port -Port 3000) {
        Write-Host "Frontend port is open but not healthy; restarting it..."
        Stop-PortProcess -Port 3000
        Start-Sleep -Seconds 1
    }
    if (Test-Path $FrontendNextDir) {
        $resolvedNextDir = Resolve-Path $FrontendNextDir
        if (-not $resolvedNextDir.Path.StartsWith($FrontendDir, [System.StringComparison]::OrdinalIgnoreCase)) {
            throw "Refusing to remove unexpected Next.js cache path: $resolvedNextDir"
        }
        Write-Host "Clearing stale Next.js dev cache..."
        Remove-Item -LiteralPath $resolvedNextDir.Path -Recurse -Force
    }
    Write-Host "Opening frontend server window..."
    Start-DevWindow -Title "IndustryNetworkMap Frontend :3000" -WorkingDirectory $FrontendDir -Command "npm run dev"
    Wait-Port -Name "Frontend" -Port 3000 -TimeoutSeconds 90
}

Write-Host ""
Write-Host "Ready:"
Write-Host "  Web app:       http://localhost:3000"
Write-Host "  Backend API:   http://localhost:8000"
Write-Host "  Neo4j Browser: http://localhost:7474"

if (-not $NoOpen) {
    Start-Process "http://localhost:3000"
}
