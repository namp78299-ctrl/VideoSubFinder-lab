param([Parameter(Mandatory=$true)][string]$LabRoot)
$ErrorActionPreference='Stop'
if ($env:GITHUB_ACTIONS -ne 'true') { throw 'Toolchain installation is restricted to a disposable GitHub runner.' }
$repo=Split-Path $PSScriptRoot -Parent
$lock=Get-Content (Join-Path $repo 'lab/deps_lock.json') -Raw | ConvertFrom-Json
python (Join-Path $PSScriptRoot 'fetch_vsf_build_inputs.py') --root $LabRoot
if ($LASTEXITCODE -ne 0) { throw 'Locked input verification failed' }
$downloads=Get-Content (Join-Path $LabRoot 'downloads.json') -Raw | ConvertFrom-Json
$vsRoot=Join-Path $LabRoot 'vs'
$installer=$downloads.archives.msvc
$signature=Get-AuthenticodeSignature -LiteralPath $installer
if ($signature.Status -ne 'Valid' -or $signature.SignerCertificate.Subject -notmatch 'Microsoft Corporation') { throw 'Invalid Microsoft installer signature' }
if ((Get-Item -LiteralPath $installer).VersionInfo.ProductVersion -ne '17.4.4') { throw 'Unexpected VS bootstrapper version' }
$installArgs=@('--quiet','--wait','--norestart','--nocache','--installPath',('"'+$vsRoot+'"'),'--add','Microsoft.VisualStudio.Workload.VCTools','--add','Microsoft.VisualStudio.Component.VC.Tools.x86.x64','--add','Microsoft.VisualStudio.Component.Windows11SDK.22000')
$process=Start-Process -FilePath $installer -ArgumentList $installArgs -Wait -PassThru -WindowStyle Hidden
if ($process.ExitCode -notin @(0,3010)) { throw "BuildTools install failed: $($process.ExitCode)" }
$devShell=Join-Path $vsRoot 'Common7/Tools/Launch-VsDevShell.ps1'
if (-not (Test-Path -LiteralPath $devShell)) { throw 'Pinned compiler installation missing' }
& $devShell -Arch amd64 -HostArch amd64 -SkipAutomaticLocation
$cl=(Get-Command cl.exe -ErrorAction Stop).Source
if ($cl -notlike "$vsRoot*") { throw 'Compiler resolved outside pinned VS instance' }
$clVersion=(Get-Item -LiteralPath $cl).VersionInfo.FileVersion
if ($clVersion -notlike '19.34.*') { throw "CUDA12.0 compiler compatibility not validated: $clVersion" }
$sdk='10.0.22000.0'
if (-not (Test-Path -LiteralPath (Join-Path ${env:ProgramFiles(x86)} "Windows Kits/10/Include/$sdk/um/Windows.h"))) { throw 'Selected SDK missing' }
$env:CUDA_TOOLKIT_PATH=Join-Path $LabRoot 'cuda';$env:CUDA_PATH=$env:CUDA_TOOLKIT_PATH;$env:CUDA_PATH_V12_0=$env:CUDA_TOOLKIT_PATH
$nvcc=Join-Path $env:CUDA_TOOLKIT_PATH 'bin/nvcc.exe'
$nvccInfo=& $nvcc --version
if ($LASTEXITCODE -ne 0 -or ($nvccInfo -join ' ') -notmatch 'V12.0.140') { throw 'Unexpected nvcc version' }
$env:VCTargetsPath=Join-Path $vsRoot 'MSBuild/Microsoft/VC/v170/'
$vcBuild=Join-Path $env:VCTargetsPath 'BuildCustomizations'
if (-not (Test-Path -LiteralPath $vcBuild)) { throw 'VCTargetsPath not configured' }
Copy-Item -Path (Join-Path $env:CUDA_TOOLKIT_PATH 'visual_studio_integration/MSBuildExtensions/*') -Destination $vcBuild
$env:WX_WIDGETS_PATH=Join-Path $LabRoot 'wx'
$env:OPENCV_BUILD_PATH_X64=Join-Path $LabRoot 'opencv-build'
$env:OPENCV_LIBS_VER='470'
$env:FFMPEG_PATH_X64=Join-Path $LabRoot 'ffmpeg-sdk'
$env:PATH=(Join-Path $LabRoot 'cmake/bin')+';'+(Join-Path $env:CUDA_TOOLKIT_PATH 'bin')+';'+$env:PATH
$env:INCLUDE=(Join-Path $env:WX_WIDGETS_PATH 'include')+';'+(Join-Path $env:WX_WIDGETS_PATH 'lib/vc_x64_lib/mswu')+';'+$env:INCLUDE
$wxSolution=Join-Path $env:WX_WIDGETS_PATH 'build/msw/wx_vc17.sln'
& msbuild $wxSolution -p:Configuration=Release -p:Platform=x64 -p:WindowsTargetPlatformVersion=$sdk -m:2 -v:n ("-bl:"+(Join-Path $LabRoot 'wx-build.binlog'))
if ($LASTEXITCODE -ne 0) { throw 'wxWidgets build failed' }
& cmake -S (Join-Path $LabRoot 'opencv') -B $env:OPENCV_BUILD_PATH_X64 -G 'Visual Studio 17 2022' -A x64 -T 'v143,version=14.34' "-DCMAKE_GENERATOR_INSTANCE=$vsRoot" "-DCMAKE_SYSTEM_VERSION=$sdk" -DBUILD_opencv_world=ON -DBUILD_TESTS=OFF -DBUILD_PERF_TESTS=OFF -DBUILD_EXAMPLES=OFF
if ($LASTEXITCODE -ne 0) { throw 'OpenCV configure failed' }
& cmake --build $env:OPENCV_BUILD_PATH_X64 --config Release --target INSTALL --parallel 2
if ($LASTEXITCODE -ne 0) { throw 'OpenCV build failed' }
python (Join-Path $PSScriptRoot 'prepare_ffmpeg_sdk.py') --runtime-zip $downloads.archives.ffmpeg --source-zip $downloads.archives.ffmpeg_headers --output $env:FFMPEG_PATH_X64 --lib-tool (Get-Command lib.exe).Source
if ($LASTEXITCODE -ne 0) { throw 'FFmpeg SDK experiment failed' }
$state=@{vs_root=$vsRoot;cl=$cl;cl_version=$clVersion;sdk=$sdk;cuda=$env:CUDA_TOOLKIT_PATH;wx=$env:WX_WIDGETS_PATH;opencv=$env:OPENCV_BUILD_PATH_X64;ffmpeg=$env:FFMPEG_PATH_X64;cmake=(Join-Path $LabRoot 'cmake/bin/cmake.exe');nvcc=($nvccInfo -join "`n");build_provenance='Experimental paired build; not byte-identical release reproduction'}
$state | ConvertTo-Json -Depth 6 | Set-Content (Join-Path $LabRoot 'toolchain.json') -Encoding utf8
