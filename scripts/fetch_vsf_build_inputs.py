"""Fetch only locked vendor archives and unpack into a disposable lab root."""
import argparse
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import shutil
import stat
import urllib.request
import zipfile


def fetch(item, target):
    if target.is_file():
        with target.open('rb') as stream:
            if hashlib.file_digest(stream,'sha256').hexdigest()==item['sha256']:
                return target
    partial=target.with_suffix(target.suffix+'.part');target.parent.mkdir(parents=True,exist_ok=True)
    h=hashlib.sha256();size=0
    with urllib.request.urlopen(urllib.request.Request(item['url'],headers={'User-Agent':'VSF610-locked-build'}),timeout=60) as response,partial.open('wb') as out:
        while block:=response.read(1024*1024):
            size+=len(block)
            if size>item['bytes']: raise ValueError('Download exceeds locked size')
            h.update(block);out.write(block)
    if size!=item['bytes'] or h.hexdigest()!=item['sha256']: raise ValueError('Download size/hash mismatch')
    os.replace(partial,target);return target


def unpack(archive,destination,strip_root=False):
    destination.mkdir(parents=True,exist_ok=True)
    with zipfile.ZipFile(archive) as z:
        for info in z.infolist():
            path=PurePosixPath(info.filename)
            if path.is_absolute() or '..' in path.parts or '\\' in info.filename or ':' in info.filename or stat.S_ISLNK(info.external_attr>>16):
                raise ValueError('Unsafe ZIP entry')
            parts=path.parts[1:] if strip_root else path.parts
            if not parts:continue
            target=destination.joinpath(*parts)
            if info.is_dir():target.mkdir(parents=True,exist_ok=True)
            else:
                target.parent.mkdir(parents=True,exist_ok=True)
                with z.open(info) as src,target.open('wb') as out:shutil.copyfileobj(src,out)


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--root',required=True,type=Path);parser.add_argument('--download-only',action='store_true');args=parser.parse_args()
    repo=Path(__file__).resolve().parents[1];lock=json.loads((repo/'lab/deps_lock.json').read_text());root=args.root.resolve();root.mkdir(parents=True,exist_ok=True)
    archives={};items={}
    for name in ['wxwidgets','opencv','cmake_for_opencv','msvc','ffmpeg']:
        d=lock['dependencies'][name];items[name]={'url':d['archive_url'],'sha256':d['archive_sha256'],'bytes':d['bytes']}
    items['ffmpeg_headers']=lock['dependencies']['ffmpeg']['headers']
    items.update({'cuda_'+name:d for name,d in lock['dependencies']['cuda']['components'].items()})
    for name,item in items.items():
        suffix='.exe' if name=='msvc' else '.zip';archives[name]=str(fetch(item,root/'downloads'/(name+suffix)));print('Verified '+name,flush=True)
    if not args.download_only:
        for name,folder,strip in [('wxwidgets','wx',False),('opencv','opencv',True),('cmake_for_opencv','cmake',True),('ffmpeg','official_runtime',False)]:
            unpack(Path(archives[name]),root/folder,strip)
        for name in lock['dependencies']['cuda']['components']:
            unpack(Path(archives['cuda_'+name]),root/'cuda',True)
    (root/'downloads.json').write_text(json.dumps({'archives':archives,'source_lock_sha256':hashlib.sha256((repo/'lab/deps_lock.json').read_bytes()).hexdigest()},indent=2))


if __name__=='__main__': main()
