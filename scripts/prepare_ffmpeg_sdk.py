"""Lab SDK experiment: exact upstream FFmpeg headers plus import DEFs for original VSF DLLs.
Does not compile FFmpeg or execute DLL code. lib.exe is optional and must come from the pinned MSVC environment.
"""
import argparse
import hashlib
import json
from pathlib import Path, PurePosixPath
import re
import struct
import subprocess
import zipfile

LIBRARIES = {'avcodec':59,'avdevice':59,'avfilter':8,'avformat':59,'avutil':57,'swresample':4,'swscale':6}


def exports(blob):
    if blob[:2] != b'MZ': raise ValueError('Not a PE file')
    pe = struct.unpack_from('<I',blob,0x3c)[0]
    if blob[pe:pe+4] != b'PE\0\0': raise ValueError('Invalid PE signature')
    machine, sections = struct.unpack_from('<HH',blob,pe+4)
    if machine != 0x8664: raise ValueError('Only AMD64 DLLs supported')
    optional_size = struct.unpack_from('<H',blob,pe+20)[0]; optional = pe+24
    if struct.unpack_from('<H',blob,optional)[0] != 0x20b: raise ValueError('Not PE32+')
    export_rva,export_size = struct.unpack_from('<II',blob,optional+112)
    segments=[]
    for i in range(sections):
        start=optional+optional_size+i*40
        virtual_size,rva,raw_size,offset=struct.unpack_from('<IIII',blob,start+8)
        flags=struct.unpack_from('<I',blob,start+36)[0]
        segments.append((rva,max(virtual_size,raw_size),offset,raw_size,flags))
    def mapped(rva):
        for start,size,offset,raw_size,flags in segments:
            if start<=rva<start+size:
                delta=rva-start
                if delta>=raw_size: raise ValueError('RVA is not file backed')
                return offset+delta,flags
        raise ValueError('Unmapped RVA')
    def string(rva):
        pos,_=mapped(rva);end=blob.index(b'\0',pos)
        return blob[pos:end].decode('ascii')
    pos,_=mapped(export_rva)
    values=struct.unpack_from('<IIHHIIIIIII',blob,pos)
    base,nfunc,nname,func_table,name_table,ordinal_table=values[5:]
    if nfunc != nname: raise ValueError('Ordinal-only exports require separate review')
    fpos,_=mapped(func_table);npos,_=mapped(name_table);opos,_=mapped(ordinal_table)
    result=[]
    for i in range(nname):
        name=string(struct.unpack_from('<I',blob,npos+4*i)[0])
        if not re.fullmatch(r'[A-Za-z_][A-Za-z0-9_]*',name): raise ValueError('Unexpected C export name')
        index=struct.unpack_from('<H',blob,opos+2*i)[0]
        if index>=nfunc: raise ValueError('Invalid export ordinal')
        rva=struct.unpack_from('<I',blob,fpos+4*index)[0]
        if export_rva<=rva<export_rva+export_size: raise ValueError('Forwarded export requires review')
        _,flags=mapped(rva)
        result.append({'name':name,'ordinal':base+index,'rva':rva,'data':not bool(flags&0x20000000)})
    if len({x['name'] for x in result}) != len(result): raise ValueError('Duplicate export')
    return result


def prepare(runtime_zip, source_zip, output, lib_tool=None):
    if output.exists(): raise ValueError('Use a new empty SDK path')
    (output/'bin').mkdir(parents=True);(output/'include').mkdir();(output/'lib').mkdir()
    report={'strategy':'original official VSF DLLs + exact FFmpeg commit headers + derived MSVC import libraries',
            'abi_status':'UNVERIFIED until compile/link/load/parity tests pass','libraries':{}}
    with zipfile.ZipFile(runtime_zip) as package:
        for name,major in LIBRARIES.items():
            filename=f'{name}-{major}.dll';entry='Release_x64/'+filename
            blob=package.read(entry);rows=exports(blob)
            (output/'bin'/filename).write_bytes(blob)
            lines=['LIBRARY '+filename,'EXPORTS']
            lines += [f"  {x['name']} @{x['ordinal']}"+(' DATA' if x['data'] else '') for x in rows]
            definition=output/'lib'/(name+'.def');definition.write_text('\n'.join(lines)+'\n',encoding='ascii')
            report['libraries'][name]={'dll_sha256':hashlib.sha256(blob).hexdigest(),'exports':len(rows),'data_exports':sum(x['data'] for x in rows),'import_library_built':False}
            if lib_tool:
                subprocess.run([str(lib_tool),'/nologo','/machine:x64','/def:'+str(definition),'/out:'+str(output/'lib'/(name+'.lib'))],check=True)
                report['libraries'][name]['import_library_built']=True
    with zipfile.ZipFile(source_zip) as source:
        prefix=source.namelist()[0].split('/')[0]+'/'
        for entry in source.namelist():
            relative=entry.removeprefix(prefix);path=PurePosixPath(relative)
            if '..' in path.parts or path.is_absolute(): raise ValueError('Unsafe archive path')
            if len(path.parts)>1 and path.parts[0] in ['lib'+n for n in LIBRARIES] and path.suffix=='.h':
                target=output/'include'/relative;target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(source.read(entry))
        for filename in ['COPYING.GPLv3','COPYING.LGPLv2.1','LICENSE.md']:
            entry=prefix+filename
            if entry in source.namelist():(output/filename).write_bytes(source.read(entry))
    # configure HAVE_LIST_PUB contains only these two target-specific values.
    # AMD64 Windows little endian and unaligned access; this SDK strategy still needs ABI validation.
    (output/'include/libavutil/avconfig.h').write_text('#ifndef AVUTIL_AVCONFIG_H\n#define AVUTIL_AVCONFIG_H\n#define AV_HAVE_BIGENDIAN 0\n#define AV_HAVE_FAST_UNALIGNED 1\n#endif\n',encoding='ascii')
    (output/'sdk_provenance.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
    return report


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--runtime-zip',required=True,type=Path);parser.add_argument('--source-zip',required=True,type=Path);parser.add_argument('--output',required=True,type=Path);parser.add_argument('--lib-tool',type=Path)
    args=parser.parse_args();print(json.dumps(prepare(args.runtime_zip,args.source_zip,args.output,args.lib_tool),indent=2))
