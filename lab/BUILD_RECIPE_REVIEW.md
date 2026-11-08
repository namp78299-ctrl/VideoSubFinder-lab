# Experimental paired build: review record

This is a new experimental recipe, not proof of reproducing the historical release build.

## Pinned inputs

- Microsoft fixed BuildTools17.4.4 bootstrapper: SHA256 recorded; Authenticode Microsoft signature verified. Installer payload catalog and actual MSVC14.34 / selected SDK10.0.22000.0 still need runner verification. The exact SDK used for the old EXE is unknown.
- wxWidgets3.2.1 and OpenCV4.7.0 source ZIPs: official downloads, locally calculated SHA256 and sizes. OpenCV auxiliary downloads retain the pinned URLs/hashes embedded in the source; actual download cache must be audited after provisioning.
- CMake3.25.2 portable ZIP: publisher SHA256 file, signature not verified.
- CUDA12.0Update1: NVIDIA manifest hashes for nvcc, cudart, CCCL, NPP and VS integration. Assembled under runner temp; no installer on the operator machine. Compiler version is checked before use.
- Official VSF6.10 release ZIP: SHA256 recorded. Its EXE matches installed EXE SHA256 exactly. No application or operator data is uploaded.

## FFmpeg SDK exception

The old BtbN SDK link returns404. The recipe instead uses the original seven runtime DLLs from official VSF release, the exact FFmpeg source commit advertised by runtime (30d432f205538f6ef6c86ed0a90e27cdd735cd2b), derived DEF/import libraries via MSVC LIB, and a documented AMD64 avconfig.h.

This is NOT the recovered original SDK archive. Before VSF build, a C program must compile/link against all seven import libraries, load the DLLs and compare runtime version integers with headers. Failure blocks the pair build. This probe alone does not establish complete struct ABI or video output parity.

Local validation: 1,220 export names/addresses from seven DLLs matched the Windows loader without executing DLL code. Three malformed/wrong-architecture inputs were rejected. DLL DATA entries are classified using executable section flags. Actual LIB compilation and native parity are still pending.

## Runner steps

1. Source/patch gate; exact download hash and byte-size verification.
2. Install pinned BuildTools on disposable GitHub runner only; verify compiler, SDK and nvcc. Build wxWidgets and OpenCV once for both variants.
3. Generate FFmpeg import libraries; run C compile/link/load/version probe.
4. Build separate baseline/instrumented source trees, Release/x64, same toolchain and dependencies. Check actual main compiler command for /O2,/MD,/std:c++17; retain console diagnostics.
5. Package successful output with provenance/lock/source notices. Only binaries and whitelisted JSON diagnostics are uploaded, not general environment dumps or MSBuild binlogs.
6. Download pair to a separate local lab, compare baseline to installed EXE, compare instrumented on/off, test GPU/cancel/retry and measure stages. CI compile success never means QA or speed gain.

The manual build workflow is registered on the dedicated lab fork for an initial experimental compile test. Current tests verify Python/PowerShell syntax, archive/download gates and source/patch identity; they are not a successful build. No SDK was installed on the operator machine.
