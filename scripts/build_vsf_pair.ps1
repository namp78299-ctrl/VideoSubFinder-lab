param([Parameter(Mandatory=$true)][string]$LabRoot, [switch]$Optimized)
$ErrorActionPreference='Stop'
if ($env:GITHUB_ACTIONS -ne 'true') { throw 'Paired build is restricted to a disposable GitHub runner.' }
$repo=Split-Path $PSScriptRoot -Parent
$state=Get-Content (Join-Path $LabRoot 'toolchain.json') -Raw | ConvertFrom-Json
& (Join-Path $state.vs_root 'Common7/Tools/Launch-VsDevShell.ps1') -Arch amd64 -HostArch amd64 -SkipAutomaticLocation
$env:VCTargetsPath=Join-Path $state.vs_root 'MSBuild/Microsoft/VC/v170/'
$env:CUDA_TOOLKIT_PATH=$state.cuda;$env:CUDA_PATH=$state.cuda;$env:CUDA_PATH_V12_0=$state.cuda
$env:WX_WIDGETS_PATH=$state.wx;$env:OPENCV_BUILD_PATH_X64=$state.opencv;$env:OPENCV_LIBS_VER='470';$env:FFMPEG_PATH_X64=$state.ffmpeg
$env:INCLUDE=(Join-Path $state.wx 'include')+';'+(Join-Path $state.wx 'lib/vc_x64_lib/mswu')+';'+$env:INCLUDE
$env:PATH=(Join-Path $LabRoot 'official_runtime/Release_x64')+';'+(Join-Path $state.ffmpeg 'bin')+';'+$env:PATH
$probe=@'
#include <libavcodec/avcodec.h>
#include <libavdevice/avdevice.h>
#include <libavfilter/avfilter.h>
#include <libavformat/avformat.h>
#include <libavutil/avutil.h>
#include <libswresample/swresample.h>
#include <libswscale/swscale.h>
int main(void) {
 return avcodec_version()!=LIBAVCODEC_VERSION_INT || avdevice_version()!=LIBAVDEVICE_VERSION_INT || avfilter_version()!=LIBAVFILTER_VERSION_INT || avformat_version()!=LIBAVFORMAT_VERSION_INT || avutil_version()!=LIBAVUTIL_VERSION_INT || swresample_version()!=LIBSWRESAMPLE_VERSION_INT || swscale_version()!=LIBSWSCALE_VERSION_INT;
}
'@
$probePath=Join-Path $LabRoot 'sdk_probe.c';$probe | Set-Content -LiteralPath $probePath -Encoding ascii
$probeExe=Join-Path $LabRoot 'sdk_probe.exe'
& cl /nologo /MD ("/I"+(Join-Path $state.ffmpeg 'include')) $probePath ("/Fe:"+$probeExe) /link ("/LIBPATH:"+(Join-Path $state.ffmpeg 'lib')) avcodec.lib avdevice.lib avfilter.lib avformat.lib avutil.lib swresample.lib swscale.lib
if ($LASTEXITCODE -ne 0) { throw 'FFmpeg SDK compile/link probe failed' }
& $probeExe
if ($LASTEXITCODE -ne 0) { throw 'FFmpeg header/runtime versions disagree or DLL load failed' }
$manifest=Get-Content (Join-Path $repo 'lab/source_manifest.json') -Raw | ConvertFrom-Json
$diagnostics=Join-Path $LabRoot 'artifacts/diagnostics';New-Item -ItemType Directory -Force $diagnostics | Out-Null
$results=@()
$variants=if ($Optimized) { @('baseline','optimized') } else { @('baseline','instrumented') }
foreach ($variant in $variants) {
  $tree=Join-Path $LabRoot $variant
  if (Test-Path -LiteralPath $tree) { throw 'Build source tree already exists; use a new lab root' }
  New-Item -ItemType Directory $tree | Out-Null
  foreach ($entry in $manifest.files.PSObject.Properties) {
    $target=Join-Path $tree $entry.Name
    New-Item -ItemType Directory -Force (Split-Path $target -Parent) | Out-Null
    Copy-Item -LiteralPath (Join-Path $repo $entry.Name) -Destination $target
  }
  if ($variant -eq 'instrumented') {
    & git -C $tree init --quiet
    if ($LASTEXITCODE -ne 0) { throw 'Cannot prepare patch area' }
    & git -C $tree apply --check (Join-Path $repo 'lab/native_stage_profile.patch')
    if ($LASTEXITCODE -ne 0) { throw 'Instrumentation patch does not apply' }
    & git -C $tree apply (Join-Path $repo 'lab/native_stage_profile.patch')
    if ($LASTEXITCODE -ne 0) { throw 'Instrumentation patch failed' }
  }
  if ($variant -eq 'optimized') {
    & git -C $tree init --quiet
    if ($LASTEXITCODE -ne 0) { throw 'Cannot prepare optimization patch area' }
    & git -C $tree apply --check (Join-Path $repo 'lab/bgr_optimization.patch')
    if ($LASTEXITCODE -ne 0) { throw 'Optimization patch does not apply' }
    & git -C $tree apply (Join-Path $repo 'lab/bgr_optimization.patch')
    if ($LASTEXITCODE -ne 0) { throw 'Optimization patch failed' }
  }
  $log=Join-Path $LabRoot ($variant+'-build.log');$binlog=Join-Path $LabRoot ($variant+'-build.binlog')
  & msbuild (Join-Path $tree 'Interfaces/VideoSubFinderWXW/VideoSubFinderWXW.sln') -p:Configuration=Release -p:Platform=x64 "-p:WindowsTargetPlatformVersion=$($state.sdk)" "-p:CudaToolkitCustomDir=$($state.cuda)" -m:2 -v:n ("-bl:"+$binlog) 2>&1 | Tee-Object -FilePath $log
  if ($LASTEXITCODE -ne 0) { throw "$variant build failed; output is not accepted" }
  $mainCommand=Get-Content -LiteralPath $log | Where-Object { $_ -match 'cl.exe' -and $_ -match 'VideoSubFinderWXW.cpp' }
  if (-not $mainCommand -or ($mainCommand -join ' ') -notmatch '/O2' -or ($mainCommand -join ' ') -notmatch '/MD' -or ($mainCommand -join ' ') -notmatch '/std:c\+\+17') { throw 'Main Release compiler flags not verified in log' }
  $build=Join-Path $tree 'Build/Release_x64';$exe=Join-Path $build 'VideoSubFinderWXW.exe'
  if (-not (Test-Path -LiteralPath $exe)) { throw 'Expected EXE missing' }
  $package=Join-Path $LabRoot ('package-'+$variant);New-Item -ItemType Directory $package | Out-Null
  Copy-Item -Path (Join-Path $LabRoot 'official_runtime/Release_x64/*') -Destination $package -Recurse
  Copy-Item -Path (Join-Path $build '*') -Destination $package -Recurse -Force
  Copy-Item -Path (Join-Path $state.opencv 'bin/Release/*.dll') -Destination $package -Force
  # Only known release files, source notices and whitelisted diagnostics are published.
  $state | ConvertTo-Json -Depth 6 | Set-Content (Join-Path $package 'build-provenance.json') -Encoding utf8
  Copy-Item -LiteralPath (Join-Path $repo 'lab/deps_lock.json') -Destination $package
  Copy-Item -LiteralPath (Join-Path $repo 'lab/native_stage_profile.patch') -Destination $package
  if ($Optimized) { Copy-Item -LiteralPath (Join-Path $repo 'lab/bgr_optimization.patch') -Destination $package }
  Copy-Item -LiteralPath (Join-Path $state.ffmpeg 'COPYING.GPLv3') -Destination $package
  $sourceUrl='Source: https://git.code.sf.net/p/videosubfinder/src/ci/c3d19abbb4080bb378090d676746751b199b46b1/tree/ ; FFmpeg headers: https://github.com/FFmpeg/FFmpeg/tree/30d432f205538f6ef6c86ed0a90e27cdd735cd2b ; instrument patch and dependency lock included. Build success does not establish native output parity, GPU compatibility, or speed gain.'
  $sourceUrl | Set-Content (Join-Path $package 'SOURCE-NOTICE.txt') -Encoding utf8
  $result=@{variant=$variant;exe_sha256=(Get-FileHash -LiteralPath $exe -Algorithm SHA256).Hash;compile_status='PASSED';sdk_version_probe='PASSED';native_output_parity='NOT_TESTED';gpu_1050ti='NOT_TESTED';speed_gain='NOT_MEASURED';main_command=$mainCommand}
  $result | ConvertTo-Json -Depth 5 | Set-Content (Join-Path $diagnostics ($variant+'.json')) -Encoding utf8
  $results+=$result
  Compress-Archive -Path (Join-Path $package '*') -DestinationPath (Join-Path $LabRoot ('artifacts/'+$variant+'.zip'))
}
$results | ConvertTo-Json -Depth 6 | Set-Content (Join-Path $diagnostics 'pair.json') -Encoding utf8
