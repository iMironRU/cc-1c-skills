#Requires -Version 5.1
<#
.SYNOPSIS
    Управление агентом 1С Конфигуратора — тестовая среда для Mac-разработчика.
    Запускай от имени администратора если нужна публикация на Apache.

.USAGE
    powershell -ExecutionPolicy Bypass -File start-1c-agent.ps1
#>

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Definition
$ConfigFile = Join-Path $ScriptDir '1c-agent.config.json'

if (-not (Test-Path $ConfigFile)) {
    Write-Host "Файл конфига не найден: $ConfigFile" -ForegroundColor Red
    Write-Host "Скопируй 1c-agent.config.json рядом со скриптом и заполни пути."
    exit 1
}

$cfg = Get-Content $ConfigFile -Raw | ConvertFrom-Json

# Validate required fields
foreach ($field in @('v8path','ib_path','ib_user','agent_port','agent_base_dir','ssh_public_key_file')) {
    if (-not $cfg.$field) {
        Write-Host "Не заполнено поле '$field' в конфиге." -ForegroundColor Red
        exit 1
    }
}

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

function Write-Header($text) {
    Write-Host ""
    Write-Host ("=" * 55) -ForegroundColor Cyan
    Write-Host "  $text" -ForegroundColor Cyan
    Write-Host ("=" * 55) -ForegroundColor Cyan
}

function Write-Ok($text)   { Write-Host "  [OK] $text" -ForegroundColor Green }
function Write-Err($text)  { Write-Host "  [!!] $text" -ForegroundColor Red }
function Write-Info($text) { Write-Host "  [  ] $text" -ForegroundColor Gray }

function Get-AgentProcess {
    Get-Process -Name '1cv8' -ErrorAction SilentlyContinue |
        Where-Object { $_.CommandLine -like '*/AgentMode*' -or $_.MainWindowTitle -like '*Агент*' }
}

function Show-Status {
    Write-Header "Статус агента 1С"
    $proc = Get-AgentProcess
    if ($proc) {
        Write-Ok  "Агент запущен  (PID $($proc.Id))"
        Write-Info "Порт:     $($cfg.agent_port)"
        Write-Info "База:     $($cfg.ib_path)"
        Write-Info "Base dir: $($cfg.agent_base_dir)"
        Write-Info ""
        Write-Info "Подключение с Mac:"
        Write-Info "  ssh -i ~/.ssh/id_1c_agent -p $($cfg.agent_port) $($cfg.ib_user)@<host>"
    } else {
        Write-Err "Агент не запущен"
    }

    # Apache status
    Write-Host ""
    $apache = Get-Process -Name 'httpd' -ErrorAction SilentlyContinue
    if ($apache) {
        Write-Ok "Apache запущен"
        Write-Info "URL: http://localhost/$($cfg.web_app_name)"
    } else {
        Write-Info "Apache не запущен"
    }
}

function Start-Agent {
    Write-Header "Запуск агента 1С"

    if (-not (Test-Path $cfg.v8path)) {
        Write-Err "Платформа 1С не найдена: $($cfg.v8path)"
        Write-Info "Проверь v8path в конфиге."
        return
    }
    if (-not (Test-Path $cfg.ib_path)) {
        Write-Err "ИБ не найдена: $($cfg.ib_path)"
        return
    }

    $existing = Get-AgentProcess
    if ($existing) {
        Write-Info "Агент уже запущен (PID $($existing.Id))"
        return
    }

    # Ensure agent base dir exists
    New-Item -ItemType Directory -Force -Path $cfg.agent_base_dir | Out-Null
    New-Item -ItemType Directory -Force -Path "$($cfg.agent_base_dir)\out" | Out-Null

    $args = @(
        'DESIGNER',
        "/F`"$($cfg.ib_path)`"",
        "/N`"$($cfg.ib_user)`"",
        '/AgentMode',
        "/AgentPort $($cfg.agent_port)",
        '/AgentListenAddress 0.0.0.0',
        '/AgentSSHHostKeyAuto',
        "/AgentBaseDir `"$($cfg.agent_base_dir)`"",
        '/DisableStartupDialogs'
    )

    if ($cfg.ib_password) {
        $args += "/P`"$($cfg.ib_password)`""
    }
    if ($cfg.ssh_public_key_file -and (Test-Path $cfg.ssh_public_key_file)) {
        $args += "/AgentSSHPublicKeyFile `"$($cfg.ssh_public_key_file)`""
        Write-Info "SSH-ключ: $($cfg.ssh_public_key_file)"
    } else {
        Write-Info "Файл SSH-ключа не найден — агент будет без аутентификации по ключу"
        Write-Info "  Сгенерируй на Mac: ssh-keygen -t ed25519 -f ~/.ssh/id_1c_agent"
        Write-Info "  Скопируй публичный ключ: ~/.ssh/id_1c_agent.pub"
        Write-Info "  Вставь содержимое в: $($cfg.ssh_public_key_file)"
    }

    Write-Info "Запуск: $($cfg.v8path)"
    Write-Info "База:   $($cfg.ib_path)"
    Write-Info "Порт:   $($cfg.agent_port)"

    Start-Process -FilePath $cfg.v8path -ArgumentList ($args -join ' ') -WindowStyle Normal

    Write-Host ""
    Write-Info "Ожидание запуска агента..."
    Start-Sleep -Seconds 5

    $proc = Get-AgentProcess
    if ($proc) {
        Write-Ok "Агент запущен (PID $($proc.Id))"
        Write-Host ""
        Write-Info "Строка подключения с Mac:"
        Write-Host "    ssh -i ~/.ssh/id_1c_agent -p $($cfg.agent_port) `"$($cfg.ib_user)`"@<IP-этой-машины>" -ForegroundColor Yellow
    } else {
        Write-Err "Агент не обнаружен после запуска — проверь логи 1С"
    }
}

function Stop-Agent {
    Write-Header "Остановка агента 1С"
    $proc = Get-AgentProcess
    if (-not $proc) {
        Write-Info "Агент не запущен"
        return
    }
    $proc | Stop-Process -Force
    Write-Ok "Агент остановлен (PID $($proc.Id))"
}

function Publish-IB {
    Write-Header "Публикация ИБ на Apache"

    if (-not $cfg.apache_config_dir) {
        Write-Err "Не задан apache_config_dir в конфиге"
        return
    }
    if (-not (Test-Path $cfg.apache_config_dir)) {
        Write-Err "Каталог Apache не найден: $($cfg.apache_config_dir)"
        return
    }

    $appName = $cfg.web_app_name
    $ibPath  = $cfg.ib_path
    $webDir  = $cfg.web_dir

    # Generate vrd file
    $vrdDir = Join-Path $webDir $appName
    New-Item -ItemType Directory -Force -Path $vrdDir | Out-Null

    $vrdContent = @"
<?xml version="1.0" encoding="UTF-8"?>
<point xmlns="http://v8.1c.ru/8.2/virtual-resource-system"
       xmlns:xs="http://www.w3.org/2001/XMLSchema"
       xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
       base="$ibPath"
       ib="File=&quot;$ibPath&quot;;Usr=&quot;$($cfg.ib_user)&quot;;Pwd=&quot;$($cfg.ib_password)&quot;"
       enable="true">
</point>
"@
    $vrdPath = Join-Path $vrdDir 'default.vrd'
    $vrdContent | Set-Content -Path $vrdPath -Encoding UTF8
    Write-Ok "VRD создан: $vrdPath"

    # Apache config snippet
    $apacheConf = @"
# 1C web application: $appName
Alias /$appName "$vrdDir"
<Directory "$vrdDir">
    Options None
    AllowOverride None
    Order allow,deny
    Allow from all
    Require all granted
    SetHandler 1c-application
    ManagedApplicationDescriptor "$vrdPath"
</Directory>
"@
    $confPath = Join-Path $cfg.apache_config_dir "1c-$appName.conf"
    $apacheConf | Set-Content -Path $confPath -Encoding UTF8
    Write-Ok "Apache конфиг: $confPath"

    # Check Include in httpd.conf
    $httpdConf = Join-Path (Split-Path $cfg.apache_config_dir) '..' 'httpd.conf'
    if (Test-Path $httpdConf) {
        $content = Get-Content $httpdConf -Raw
        $includeLine = "Include conf/extra/1c-$appName.conf"
        if ($content -notlike "*$includeLine*") {
            Add-Content -Path $httpdConf -Value "`n$includeLine"
            Write-Ok "Include добавлен в httpd.conf"
        } else {
            Write-Info "Include уже есть в httpd.conf"
        }
    }

    # Restart Apache
    if ($cfg.apache_exe -and (Test-Path $cfg.apache_exe)) {
        Write-Info "Перезапуск Apache..."
        & $cfg.apache_exe -k restart 2>&1 | Out-Null
        Start-Sleep -Seconds 2
        $apache = Get-Process -Name 'httpd' -ErrorAction SilentlyContinue
        if ($apache) {
            Write-Ok "Apache перезапущен"
            Write-Host ""
            Write-Host "  URL: http://localhost/$appName" -ForegroundColor Yellow
        } else {
            Write-Err "Apache не запустился — проверь конфиг"
        }
    } else {
        Write-Info "Перезапусти Apache вручную: httpd.exe -k restart"
    }
}

function Unpublish-IB {
    Write-Header "Снятие публикации ИБ"
    $appName = $cfg.web_app_name
    $confPath = Join-Path $cfg.apache_config_dir "1c-$appName.conf"

    if (Test-Path $confPath) {
        Remove-Item $confPath -Force
        Write-Ok "Конфиг удалён: $confPath"
    } else {
        Write-Info "Конфиг не найден: $confPath"
    }

    if ($cfg.apache_exe -and (Test-Path $cfg.apache_exe)) {
        & $cfg.apache_exe -k restart 2>&1 | Out-Null
        Write-Ok "Apache перезапущен"
    }
}

function Setup-SshKey {
    Write-Header "Настройка SSH-ключа"
    Write-Info "На Mac выполни:"
    Write-Host ""
    Write-Host "    ssh-keygen -t ed25519 -f ~/.ssh/id_1c_agent -C '1c-agent'" -ForegroundColor Yellow
    Write-Host ""
    Write-Info "Затем скопируй содержимое ~/.ssh/id_1c_agent.pub"
    Write-Info "и вставь в файл на Windows:"
    Write-Host "    $($cfg.ssh_public_key_file)" -ForegroundColor Yellow
    Write-Host ""
    Write-Info "Создать файл authorized_keys сейчас? (вставь публичный ключ)"
    $key = Read-Host "Публичный ключ (или Enter чтобы пропустить)"
    if ($key) {
        $keyDir = Split-Path $cfg.ssh_public_key_file
        New-Item -ItemType Directory -Force -Path $keyDir | Out-Null
        $key | Set-Content -Path $cfg.ssh_public_key_file -Encoding UTF8
        Write-Ok "Ключ сохранён: $($cfg.ssh_public_key_file)"
        Write-Info "Перезапусти агент чтобы ключ применился"
    }
}

# ---------------------------------------------------------------------------
# Menu
# ---------------------------------------------------------------------------

while ($true) {
    Write-Header "Агент 1С — тестовая среда"

    $proc = Get-AgentProcess
    $agentStatus = if ($proc) { "[ЗАПУЩЕН PID $($proc.Id)]" } else { "[остановлен]" }
    $apache = Get-Process -Name 'httpd' -ErrorAction SilentlyContinue
    $apacheStatus = if ($apache) { "[ЗАПУЩЕН]" } else { "[остановлен]" }

    Write-Host ""
    Write-Host "  Агент 1С : $agentStatus" -ForegroundColor $(if ($proc) { 'Green' } else { 'Gray' })
    Write-Host "  Apache   : $apacheStatus" -ForegroundColor $(if ($apache) { 'Green' } else { 'Gray' })
    Write-Host ""
    Write-Host "  1. Запустить агент"
    Write-Host "  2. Остановить агент"
    Write-Host "  3. Статус и строка подключения"
    Write-Host "  4. Опубликовать ИБ на Apache"
    Write-Host "  5. Снять публикацию"
    Write-Host "  6. Настроить SSH-ключ"
    Write-Host "  0. Выход"
    Write-Host ""

    $choice = Read-Host "Выбор"

    switch ($choice) {
        '1' { Start-Agent }
        '2' { Stop-Agent }
        '3' { Show-Status }
        '4' { Publish-IB }
        '5' { Unpublish-IB }
        '6' { Setup-SshKey }
        '0' { break }
        default { Write-Host "  Неверный выбор" -ForegroundColor Yellow }
    }

    if ($choice -eq '0') { break }

    Write-Host ""
    Read-Host "  Нажми Enter для продолжения"
}
