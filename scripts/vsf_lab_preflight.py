"""Read-only VSF lab gate. This does not download, install, compile or run VSF."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys


def inspect(root):
    manifest = json.loads((root / 'lab/source_manifest.json').read_text(encoding='utf-8'))
    issues = []
    checked = 0
    for name, expected in manifest['files'].items():
        path = root / name
        if not path.is_file():
            issues.append('Missing upstream file: ' + name)
            continue
        digest = hashlib.sha256(path.read_bytes().replace(b'\r\n', b'\n')).hexdigest()
        if digest != expected:
            issues.append('Source mismatch: ' + name)
        checked += 1
    patch = root / 'lab/native_stage_profile.patch'
    if hashlib.sha256(patch.read_bytes()).hexdigest() != manifest['profile_patch_sha256']:
        issues.append('Instrumentation patch hash mismatch')
    result = subprocess.run(['git', 'apply', '--check', str(patch)], cwd=root,
                            capture_output=True, text=True)
    if result.returncode:
        issues.append('Patch does not apply: ' + result.stderr.strip())
    lock = json.loads((root / 'lab/deps_lock.json').read_text(encoding='utf-8'))
    unresolved = []
    for name, dependency in lock['dependencies'].items():
        if not dependency.get('archive_url') or not dependency.get('archive_sha256'):
            unresolved.append(name)
    incomplete_environment = [key for key, value in lock['environment_variables'].items() if not value]
    tools = {name: shutil.which(name) for name in ['msbuild', 'cl', 'nvcc', 'cmake']}
    return {
        'scope': 'source/patch/dependency inventory only; NOT a build or speed test',
        'upstream_commit': manifest['upstream_commit'],
        'source_files_checked': checked,
        'source_and_patch_passed': not issues,
        'issues': issues,
        'dependency_lock_status': lock['status'],
        'unresolved_dependencies': unresolved,
        'unconfigured_environment': incomplete_environment,
        'tools_on_path': tools,
        'build_ready': False,
        'build_status': 'NOT_ATTEMPTED',
        'next_gate': 'Resolve dependency archives/hashes and validate exact compiler/SDK/CUDA on runner; then add paired Release x64 build jobs.',
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--root', type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    report = inspect(args.root.resolve())
    encoded = json.dumps(report, indent=2, ensure_ascii=False)
    print(encoded)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(encoded, encoding='utf-8')
    summary = os.environ.get('GITHUB_STEP_SUMMARY')
    if summary:
        with open(summary, 'a', encoding='utf-8') as stream:
            stream.write('## VSF lab: source review only\n\n')
            stream.write(f"Source/patch gate: {'PASS' if report['source_and_patch_passed'] else 'FAIL'}\n\n")
            stream.write('**No VSF build or benchmark was performed. Build readiness: NOT VALIDATED.**\n\n')
            stream.write('Unresolved dependency locks: ' + ', '.join(report['unresolved_dependencies']) + '\n')
    return 0 if report['source_and_patch_passed'] else 1


if __name__ == '__main__':
    sys.exit(main())
