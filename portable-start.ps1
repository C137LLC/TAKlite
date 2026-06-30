param(
    [string]$BindIp = "127.0.0.1",
    [string]$ServerHost = "",
    [string]$BootstrapToken = ""
)

$ErrorActionPreference = "Stop"
$BaseDir = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $BaseDir

function New-TakliteToken {
    $bytes = New-Object byte[] 24
    [System.Security.Cryptography.RandomNumberGenerator]::Fill($bytes)
    return [Convert]::ToBase64String($bytes).Replace("+", "").Replace("/", "").Replace("=", "")
}

function Get-LanIPv4 {
    $ip = Get-NetIPAddress -AddressFamily IPv4 -ErrorAction SilentlyContinue |
        Where-Object { $_.IPAddress -notlike "127.*" -and $_.PrefixOrigin -ne "WellKnown" } |
        Select-Object -First 1 -ExpandProperty IPAddress
    if ($ip) { return $ip }
    return "127.0.0.1"
}

function Invoke-DockerCompose {
    param([string[]]$Args)
    docker compose version *> $null
    if ($LASTEXITCODE -eq 0) {
        & docker compose @Args
        return
    }
    $compose = Get-Command docker-compose -ErrorAction SilentlyContinue
    if ($compose) {
        & docker-compose @Args
        return
    }
    throw "Docker Compose was not found. Install Docker Desktop with Compose support."
}

docker info *> $null
if ($LASTEXITCODE -ne 0) {
    throw "Docker is not running, or this user cannot access Docker. Start Docker Desktop and try again."
}

New-Item -ItemType Directory -Force -Path "taklite\data", "taklite\packages", "taklite\certs" | Out-Null

if (Test-Path ".env") {
    Write-Host "[taklite-portable] Using existing .env"
} else {
    if (-not $ServerHost) {
        if ($BindIp -eq "0.0.0.0") {
            $ServerHost = Get-LanIPv4
        } else {
            $ServerHost = "127.0.0.1"
        }
    }
    if (-not $BootstrapToken) {
        $BootstrapToken = New-TakliteToken
    }

@"
WG_BIND_IP=$BindIp
TAKLITE_PUBLIC_HOST=$ServerHost
TAKLITE_SERVER_HOST=$ServerHost
TAKLITE_CONTAINER_USER=10001:10001
TAKLITE_AUTO_INIT_CERTS=true
TAKLITE_ADMIN_TOKEN=$BootstrapToken
TAKLITE_CERT_PASSWORD=atakatak
TAKLITE_COT_HOST_PORT=58087
TAKLITE_COT_TLS_HOST_PORT=8089
TAKLITE_HTTP_HOST_PORT=8080
TAKLITE_HTTPS_HOST_PORT=8443
TAKLITE_WGDASHBOARD_URL=
TAKLITE_MAX_UPLOAD_BYTES=268435456
TAKLITE_COT_TLS_REQUIRE_CLIENT_CERT=true
TAKLITE_ALLOW_LEGACY_CLIENT_CERT=false
TAKLITE_ACCESS_CONTROL_ENFORCE=true
TAKLITE_SOCKET_SEND_TIMEOUT_SECONDS=2.5
TAKLITE_GUI_UPDATE_ENABLED=false
TAKLITE_GUI_UPDATE_COMMAND=
TAKLITE_GUI_UPDATE_WORKDIR=
TAKLITE_GUI_UPDATE_TIMEOUT_SECONDS=900
TAKLITE_GUI_UPDATE_REQUEST_DIR=
TAKLITE_SETTINGS_REQUEST_DIR=
TAKLITE_FIREWALL_REQUEST_DIR=
TAKLITE_WG_INTERFACE=
TAKLITE_PUBLIC_INTERFACE=
TAKLITE_WIREGUARD_PORT=
TAKLITE_WGDASHBOARD_PORT=
"@ | Set-Content -Path ".env" -Encoding UTF8
}

Write-Host "[taklite-portable] Starting TAKlite portable container"
Invoke-DockerCompose @("up", "-d", "--build")

$envValues = Get-Content ".env" | Where-Object { $_ -match "=" } | ForEach-Object {
    $parts = $_ -split "=", 2
    [PSCustomObject]@{ Key = $parts[0]; Value = $parts[1] }
}
$hostValue = ($envValues | Where-Object Key -eq "TAKLITE_PUBLIC_HOST" | Select-Object -Last 1).Value
$httpPort = ($envValues | Where-Object Key -eq "TAKLITE_HTTP_HOST_PORT" | Select-Object -Last 1).Value
$httpsPort = ($envValues | Where-Object Key -eq "TAKLITE_HTTPS_HOST_PORT" | Select-Object -Last 1).Value
$token = ($envValues | Where-Object Key -eq "TAKLITE_ADMIN_TOKEN" | Select-Object -Last 1).Value

Write-Host ""
Write-Host "TAKlite portable mode is running."
Write-Host ""
Write-Host "Dashboard:      http://$hostValue`:$httpPort/"
Write-Host "HTTPS/Marti:    https://$hostValue`:$httpsPort/Marti"
Write-Host "Bootstrap token: $token"
Write-Host ""
Write-Host "Portable mode does not install WireGuard, WGDashboard, systemd services, or firewall rules."
