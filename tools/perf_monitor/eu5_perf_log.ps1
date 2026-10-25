<#
.SYNOPSIS
  Samples EU5 process and system resource usage into a CSV while the game runs.

.DESCRIPTION
  Uses only CIM/WMI classes (names are not localized, so it works on Chinese
  Windows where Get-Counter paths would be translated). Output goes to
  data\perf_logs\eu5_perf_<timestamp>.csv plus a .txt sidecar with hardware info.

  Key columns:
    eu5_cpu_cores          CPU used by eu5.exe in "cores" (1.00 = one core fully busy)
    max_core_pct           busiest single logical core; ~100 means a single-thread bottleneck
    eu5_working_set_mb     eu5.exe RAM actually resident in physical memory
    eu5_private_mb         eu5.exe committed private memory (resident + paged out)
    sys_committed_mb       total committed memory for the whole system
    hard_page_reads_per_s  page reads from disk per second (sustained high = thrashing)
    pagefile_used_mb       current pagefile usage

.EXAMPLE
  powershell -ExecutionPolicy Bypass -File tools\perf_monitor\eu5_perf_log.ps1
.EXAMPLE
  powershell -ExecutionPolicy Bypass -File tools\perf_monitor\eu5_perf_log.ps1 -IntervalSeconds 10 -DurationMinutes 60
#>
param(
    [int]$IntervalSeconds = 5,
    [double]$DurationMinutes = 0,   # 0 = run until Ctrl+C or the game exits
    [string]$ProcessName = "eu5",
    [string]$OutDir = ""
)

$ErrorActionPreference = "Stop"

if (-not $OutDir) {
    $repoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
    $OutDir = Join-Path $repoRoot "data\perf_logs"
}
New-Item -ItemType Directory -Force -Path $OutDir | Out-Null
$stamp = Get-Date -Format "yyyyMMdd_HHmmss"
$csvPath = Join-Path $OutDir "eu5_perf_$stamp.csv"
$infoPath = Join-Path $OutDir "eu5_perf_$stamp.txt"

# ---- static hardware info -------------------------------------------------
$cs = Get-CimInstance Win32_ComputerSystem
$cpu = Get-CimInstance Win32_Processor | Select-Object -First 1
$board = Get-CimInstance Win32_BaseBoard
$dimms = Get-CimInstance Win32_PhysicalMemory
$pf = Get-CimInstance Win32_PageFileUsage
$disks = Get-CimInstance Win32_DiskDrive
$logical = [int]$cs.NumberOfLogicalProcessors

$info = @()
$info += "Sampled at: $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')"
$info += "CPU: $($cpu.Name.Trim()) | cores=$($cpu.NumberOfCores) logical=$logical maxMHz=$($cpu.MaxClockSpeed)"
$info += "Board: $($board.Manufacturer) $($board.Product)"
$info += "RAM total MB: $([math]::Round($cs.TotalPhysicalMemory / 1MB))"
foreach ($d in $dimms) {
    $info += "DIMM: slot=$($d.DeviceLocator) sizeGB=$([math]::Round($d.Capacity / 1GB)) speed=$($d.Speed) configured=$($d.ConfiguredClockSpeed) maker=$($d.Manufacturer) part=$($d.PartNumber)"
}
foreach ($p in $pf) {
    $info += "Pagefile: $($p.Name) allocatedMB=$($p.AllocatedBaseSize) peakMB=$($p.PeakUsage)"
}
foreach ($k in $disks) {
    $info += "Disk: $($k.Model) sizeGB=$([math]::Round($k.Size / 1GB)) interface=$($k.InterfaceType)"
}
$info | Set-Content -Path $infoPath -Encoding UTF8
$info | ForEach-Object { Write-Host $_ }

# ---- wait for the game ----------------------------------------------------
Write-Host ""
Write-Host "Waiting for process '$ProcessName'..."
$proc = $null
while (-not $proc) {
    $proc = Get-Process -Name $ProcessName -ErrorAction SilentlyContinue | Select-Object -First 1
    if (-not $proc) { Start-Sleep -Seconds 2 }
}
$procId = $proc.Id
Write-Host "Found $ProcessName (PID $procId). Logging every $IntervalSeconds s to:"
Write-Host "  $csvPath"
Write-Host "Press Ctrl+C to stop."
Write-Host ""

# Prime WMI formatted counters (first read of rate counters is often 0).
$null = Get-CimInstance Win32_PerfFormattedData_PerfOS_Memory
$null = Get-CimInstance Win32_PerfFormattedData_PerfOS_Processor
$null = Get-CimInstance Win32_PerfFormattedData_PerfDisk_PhysicalDisk -Filter "Name='_Total'"
$null = Get-CimInstance Win32_PerfFormattedData_PerfProc_Process -Filter "IDProcess=$procId"

$start = Get-Date
$prevCpu = $proc.TotalProcessorTime
$prevTime = Get-Date
Start-Sleep -Seconds $IntervalSeconds

try {
    while ($true) {
        $proc.Refresh()
        if ($proc.HasExited) { Write-Host "Game exited."; break }

        $now = Get-Date
        $cpuNow = $proc.TotalProcessorTime
        $wall = ($now - $prevTime).TotalSeconds
        $cores = if ($wall -gt 0) { ($cpuNow - $prevCpu).TotalSeconds / $wall } else { 0 }
        $prevCpu = $cpuNow
        $prevTime = $now

        $mem = Get-CimInstance Win32_PerfFormattedData_PerfOS_Memory
        $procs = Get-CimInstance Win32_PerfFormattedData_PerfOS_Processor
        $totalCpu = ($procs | Where-Object { $_.Name -eq "_Total" }).PercentProcessorTime
        $maxCore = ($procs | Where-Object { $_.Name -ne "_Total" } |
                    Measure-Object -Property PercentProcessorTime -Maximum).Maximum
        $disk = Get-CimInstance Win32_PerfFormattedData_PerfDisk_PhysicalDisk -Filter "Name='_Total'"
        $pp = Get-CimInstance Win32_PerfFormattedData_PerfProc_Process -Filter "IDProcess=$procId"
        $pfUsed = (Get-CimInstance Win32_PageFileUsage | Measure-Object -Property CurrentUsage -Sum).Sum
        $procFaults = ""
        if ($pp) { $procFaults = $pp.PageFaultsPersec }

        $row = [pscustomobject]@{
            time                  = $now.ToString("yyyy-MM-dd HH:mm:ss")
            elapsed_min           = [math]::Round(($now - $start).TotalMinutes, 2)
            eu5_cpu_cores         = [math]::Round($cores, 2)
            eu5_cpu_pct_of_all    = [math]::Round(100 * $cores / $logical, 1)
            max_core_pct          = $maxCore
            total_cpu_pct         = $totalCpu
            eu5_working_set_mb    = [math]::Round($proc.WorkingSet64 / 1MB)
            eu5_private_mb        = [math]::Round($proc.PrivateMemorySize64 / 1MB)
            eu5_threads           = $proc.Threads.Count
            eu5_page_faults_per_s = $procFaults
            sys_available_mb      = $mem.AvailableMBytes
            sys_committed_mb      = [math]::Round($mem.CommittedBytes / 1MB)
            sys_commit_limit_mb   = [math]::Round($mem.CommitLimit / 1MB)
            pagefile_used_mb      = $pfUsed
            hard_page_reads_per_s = $mem.PageReadsPersec
            pages_input_per_s     = $mem.PagesInputPersec
            disk_busy_pct         = [math]::Max(0, 100 - [int]$disk.PercentIdleTime)
            disk_read_mb_s        = [math]::Round($disk.DiskReadBytesPersec / 1MB, 1)
        }
        $row | Export-Csv -Path $csvPath -NoTypeInformation -Append -Encoding UTF8

        Write-Host ("{0}  cpu={1,5:N2} cores  maxcore={2,3}%  ws={3,6} MB  private={4,6} MB  avail={5,5} MB  pagefile={6,5} MB  hardreads/s={7,5}  disk={8,3}%" -f `
            $row.time, $row.eu5_cpu_cores, $row.max_core_pct, $row.eu5_working_set_mb, $row.eu5_private_mb,
            $row.sys_available_mb, $row.pagefile_used_mb, $row.hard_page_reads_per_s, $row.disk_busy_pct)

        if ($DurationMinutes -gt 0 -and ($now - $start).TotalMinutes -ge $DurationMinutes) { break }
        Start-Sleep -Seconds $IntervalSeconds
    }
}
finally {
    Write-Host ""
    Write-Host "Saved: $csvPath"
    Write-Host "Info:  $infoPath"
}
