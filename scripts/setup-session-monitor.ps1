#!/usr/bin/env pwsh
<#
.SYNOPSIS
    Setup and manage the Active Session Monitor for Claude Code

.DESCRIPTION
    This script sets up automated session monitoring that runs in the background,
    creating intelligent checkpoints based on activity, time, idle detection, and context usage.

.PARAMETER Action
    Action to perform: install, uninstall, start, stop, status, logs, test

.PARAMETER Interval
    Check interval in minutes (default: 5)

.PARAMETER TimeHours
    Time trigger threshold in hours (default: 2)

.PARAMETER ActivityFiles
    Activity trigger threshold in files modified (default: 15)

.PARAMETER IdleMinutes
    Idle trigger threshold in minutes (default: 30)

.EXAMPLE
    .\setup-session-monitor.ps1 install
    Install with default settings (check every 5 minutes)

.EXAMPLE
    .\setup-session-monitor.ps1 install -Interval 10
    Install with 10-minute check interval

.EXAMPLE
    .\setup-session-monitor.ps1 status
    Show current status

.EXAMPLE
    .\setup-session-monitor.ps1 logs
    View recent log entries

.EXAMPLE
    .\setup-session-monitor.ps1 test
    Run a single check to test the system
#>

param(
    [Parameter(Position=0)]
    [ValidateSet('install', 'uninstall', 'start', 'stop', 'status', 'logs', 'test', 'help')]
    [string]$Action = 'help',

    [Parameter()]
    [ValidateRange(1, 60)]
    [int]$Interval = 5,

    [Parameter()]
    [ValidateRange(0.5, 24)]
    [double]$TimeHours = 2,

    [Parameter()]
    [ValidateRange(1, 100)]
    [int]$ActivityFiles = 15,

    [Parameter()]
    [ValidateRange(5, 120)]
    [int]$IdleMinutes = 30
)

# Configuration
$TaskName = "ClaudeCode-SessionMonitor"
$ScriptsDir = $PSScriptRoot
$MonitorScript = Join-Path $ScriptsDir "session_monitor.py"
$ClaudeDir = Join-Path $env:USERPROFILE ".claude"
$LogFile = Join-Path $ClaudeDir "session-monitor.log"
$ConfigFile = Join-Path $ClaudeDir "monitor-config.json"

# Colors for output
function Write-Header {
    param([string]$Text)
    Write-Host ""
    Write-Host "=" * 70 -ForegroundColor Cyan
    Write-Host $Text -ForegroundColor Cyan
    Write-Host "=" * 70 -ForegroundColor Cyan
    Write-Host ""
}

function Write-Success {
    param([string]$Text)
    Write-Host "[OK] $Text" -ForegroundColor Green
}

function Write-Error {
    param([string]$Text)
    Write-Host "[ERROR] $Text" -ForegroundColor Red
}

function Write-Info {
    param([string]$Text)
    Write-Host "[INFO] $Text" -ForegroundColor Yellow
}

function Test-IsAdmin {
    $currentUser = [Security.Principal.WindowsIdentity]::GetCurrent()
    $principal = New-Object Security.Principal.WindowsPrincipal($currentUser)
    return $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
}

function Save-Config {
    param(
        [int]$Interval,
        [double]$TimeHours,
        [int]$ActivityFiles,
        [int]$IdleMinutes
    )

    $config = @{
        interval = $Interval
        time_hours = $TimeHours
        activity_files = $ActivityFiles
        idle_minutes = $IdleMinutes
        installed_at = (Get-Date).ToString("yyyy-MM-dd HH:mm:ss")
    }

    $configDir = Split-Path $ConfigFile -Parent
    if (-not (Test-Path $configDir)) {
        New-Item -ItemType Directory -Path $configDir -Force | Out-Null
    }

    $config | ConvertTo-Json | Set-Content $ConfigFile
    Write-Success "Configuration saved to $ConfigFile"
}

function Get-Config {
    if (Test-Path $ConfigFile) {
        return Get-Content $ConfigFile | ConvertFrom-Json
    }
    return $null
}

function Install-SessionMonitor {
    Write-Header "INSTALLING ACTIVE SESSION MONITOR"

    # Check if Python is available
    try {
        $pythonVersion = python --version 2>&1
        Write-Success "Python found: $pythonVersion"
    } catch {
        Write-Error "Python not found! Please install Python 3.8+ first."
        return
    }

    # Check if session_monitor.py exists
    if (-not (Test-Path $MonitorScript)) {
        Write-Error "Session monitor script not found: $MonitorScript"
        return
    }
    Write-Success "Session monitor script found"

    # Check if task already exists
    $existingTask = Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue
    if ($existingTask) {
        Write-Info "Task already exists. Uninstalling first..."
        Uninstall-SessionMonitor
    }

    # Save configuration
    Save-Config -Interval $Interval -TimeHours $TimeHours -ActivityFiles $ActivityFiles -IdleMinutes $IdleMinutes

    # Build command arguments
    $args = @(
        $MonitorScript,
        "--interval", $Interval,
        "--time-hours", $TimeHours,
        "--activity-files", $ActivityFiles,
        "--idle-minutes", $IdleMinutes
    )

    # Create scheduled task action
    $action = New-ScheduledTaskAction `
        -Execute "python" `
        -Argument ($args -join " ") `
        -WorkingDirectory $ScriptsDir

    # Create trigger (start at logon and repeat every X minutes)
    $trigger = New-ScheduledTaskTrigger -AtLogOn

    # Create settings
    $settings = New-ScheduledTaskSettingsSet `
        -AllowStartIfOnBatteries `
        -DontStopIfGoingOnBatteries `
        -StartWhenAvailable `
        -RestartCount 3 `
        -RestartInterval (New-TimeSpan -Minutes 1) `
        -ExecutionTimeLimit (New-TimeSpan -Hours 0)

    # Register the task
    try {
        Register-ScheduledTask `
            -TaskName $TaskName `
            -Action $action `
            -Trigger $trigger `
            -Settings $settings `
            -Description "Active Session Monitor for Claude Code - Creates intelligent checkpoints" `
            -Force | Out-Null

        Write-Success "Scheduled task created successfully"
    } catch {
        Write-Error "Failed to create scheduled task: $_"
        return
    }

    # Start the task
    Write-Info "Starting session monitor..."
    Start-ScheduledTask -TaskName $TaskName

    Write-Header "INSTALLATION COMPLETE"
    Write-Host "Session monitor is now running in the background." -ForegroundColor Green
    Write-Host ""
    Write-Host "Configuration:"
    Write-Host "  Check interval:   $Interval minute(s)"
    Write-Host "  Time trigger:     $TimeHours hour(s)"
    Write-Host "  Activity trigger: $ActivityFiles file(s)"
    Write-Host "  Idle trigger:     $IdleMinutes minute(s)"
    Write-Host ""
    Write-Host "Useful commands:"
    Write-Host "  .\setup-session-monitor.ps1 status   # Check status"
    Write-Host "  .\setup-session-monitor.ps1 logs     # View logs"
    Write-Host "  .\setup-session-monitor.ps1 stop     # Temporarily stop"
    Write-Host "  .\setup-session-monitor.ps1 start    # Resume monitoring"
    Write-Host ""
}

function Uninstall-SessionMonitor {
    Write-Header "UNINSTALLING SESSION MONITOR"

    # Check if task exists
    $task = Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue
    if (-not $task) {
        Write-Info "Session monitor is not installed"
        return
    }

    # Stop and unregister the task
    try {
        Stop-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue
        Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false
        Write-Success "Session monitor uninstalled successfully"
    } catch {
        Write-Error "Failed to uninstall: $_"
        return
    }

    # Optionally remove config
    if (Test-Path $ConfigFile) {
        Write-Info "Configuration file kept at: $ConfigFile"
        Write-Info "To remove: Remove-Item '$ConfigFile'"
    }

    Write-Success "Uninstallation complete"
}

function Start-Monitor {
    Write-Header "STARTING SESSION MONITOR"

    $task = Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue
    if (-not $task) {
        Write-Error "Session monitor is not installed. Run 'install' first."
        return
    }

    Start-ScheduledTask -TaskName $TaskName
    Write-Success "Session monitor started"
    Start-Sleep -Seconds 2
    Show-Status
}

function Stop-Monitor {
    Write-Header "STOPPING SESSION MONITOR"

    $task = Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue
    if (-not $task) {
        Write-Error "Session monitor is not installed"
        return
    }

    Stop-ScheduledTask -TaskName $TaskName
    Write-Success "Session monitor stopped"
}

function Show-Status {
    Write-Header "SESSION MONITOR STATUS"

    # Check if task exists
    $task = Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue
    if (-not $task) {
        Write-Info "Status: NOT INSTALLED"
        Write-Host ""
        Write-Host "To install: .\setup-session-monitor.ps1 install"
        return
    }

    # Get task info
    $taskInfo = Get-ScheduledTaskInfo -TaskName $TaskName

    Write-Host "Status:          " -NoNewline
    if ($task.State -eq "Running") {
        Write-Host "RUNNING" -ForegroundColor Green
    } elseif ($task.State -eq "Ready") {
        Write-Host "READY (will start at next interval)" -ForegroundColor Yellow
    } else {
        Write-Host $task.State -ForegroundColor Red
    }

    Write-Host "Last run time:   $($taskInfo.LastRunTime)"
    Write-Host "Next run time:   $($taskInfo.NextRunTime)"
    Write-Host "Last result:     $($taskInfo.LastTaskResult)"

    # Show configuration
    $config = Get-Config
    if ($config) {
        Write-Host ""
        Write-Host "Configuration:"
        Write-Host "  Check interval:   $($config.interval) minute(s)"
        Write-Host "  Time trigger:     $($config.time_hours) hour(s)"
        Write-Host "  Activity trigger: $($config.activity_files) file(s)"
        Write-Host "  Idle trigger:     $($config.idle_minutes) minute(s)"
        Write-Host "  Installed:        $($config.installed_at)"
    }

    # Show log file location
    Write-Host ""
    Write-Host "Log file: $LogFile"
    if (Test-Path $LogFile) {
        $logSize = (Get-Item $LogFile).Length / 1KB
        Write-Host "Log size: $([math]::Round($logSize, 2)) KB"
    }

    Write-Host ""
}

function Show-Logs {
    Write-Header "SESSION MONITOR LOGS (Last 30 lines)"

    if (-not (Test-Path $LogFile)) {
        Write-Info "No logs yet. The monitor may not have run yet."
        return
    }

    # Show last 30 lines
    Get-Content $LogFile -Tail 30 | ForEach-Object {
        if ($_ -match '\[ERROR\]') {
            Write-Host $_ -ForegroundColor Red
        } elseif ($_ -match '\[WARNING\]') {
            Write-Host $_ -ForegroundColor Yellow
        } elseif ($_ -match 'Checkpoint created successfully') {
            Write-Host $_ -ForegroundColor Green
        } else {
            Write-Host $_
        }
    }

    Write-Host ""
    Write-Host "Full log: $LogFile"
    Write-Host "To follow logs in real-time: Get-Content '$LogFile' -Wait -Tail 10"
    Write-Host ""
}

function Test-Monitor {
    Write-Header "TESTING SESSION MONITOR"

    Write-Info "Running a single check (this may take a few minutes)..."
    Write-Host ""

    # Build command
    $cmd = @(
        $MonitorScript,
        "--once",
        "--time-hours", $TimeHours,
        "--activity-files", $ActivityFiles,
        "--idle-minutes", $IdleMinutes
    )

    # Run the monitor
    try {
        python @cmd
        Write-Host ""
        Write-Success "Test completed! Check the output above for results."
    } catch {
        Write-Error "Test failed: $_"
        return
    }

    Write-Host ""
    Write-Info "To see what was logged: .\setup-session-monitor.ps1 logs"
    Write-Host ""
}

function Show-Help {
    Write-Header "ACTIVE SESSION MONITOR SETUP"

    Write-Host "This tool sets up automated session monitoring for Claude Code."
    Write-Host "The monitor runs in the background and creates intelligent checkpoints"
    Write-Host "based on activity, time, idle detection, and context usage."
    Write-Host ""
    Write-Host "USAGE:"
    Write-Host "  .\setup-session-monitor.ps1 <action> [options]"
    Write-Host ""
    Write-Host "ACTIONS:"
    Write-Host "  install      Install and start the session monitor"
    Write-Host "  uninstall    Remove the session monitor"
    Write-Host "  start        Start the monitor (if stopped)"
    Write-Host "  stop         Stop the monitor (temporarily)"
    Write-Host "  status       Show current status"
    Write-Host "  logs         View recent log entries"
    Write-Host "  test         Run a single check to test the system"
    Write-Host "  help         Show this help message"
    Write-Host ""
    Write-Host "OPTIONS:"
    Write-Host "  -Interval <minutes>       Check interval (default: 5)"
    Write-Host "  -TimeHours <hours>        Time trigger threshold (default: 2)"
    Write-Host "  -ActivityFiles <count>    Activity trigger threshold (default: 15)"
    Write-Host "  -IdleMinutes <minutes>    Idle trigger threshold (default: 30)"
    Write-Host ""
    Write-Host "EXAMPLES:"
    Write-Host "  .\setup-session-monitor.ps1 install"
    Write-Host "      Install with default settings"
    Write-Host ""
    Write-Host "  .\setup-session-monitor.ps1 install -Interval 10 -TimeHours 1"
    Write-Host "      Install with custom settings (check every 10 min, trigger after 1 hour)"
    Write-Host ""
    Write-Host "  .\setup-session-monitor.ps1 test"
    Write-Host "      Test the monitor before installing"
    Write-Host ""
    Write-Host "  .\setup-session-monitor.ps1 logs"
    Write-Host "      View recent activity"
    Write-Host ""
}

# Main execution
switch ($Action) {
    'install' {
        Install-SessionMonitor
    }
    'uninstall' {
        Uninstall-SessionMonitor
    }
    'start' {
        Start-Monitor
    }
    'stop' {
        Stop-Monitor
    }
    'status' {
        Show-Status
    }
    'logs' {
        Show-Logs
    }
    'test' {
        Test-Monitor
    }
    'help' {
        Show-Help
    }
    default {
        Show-Help
    }
}
