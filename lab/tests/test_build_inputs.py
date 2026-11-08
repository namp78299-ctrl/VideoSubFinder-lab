import hashlib
import importlib.util
import io
from pathlib import Path
import struct
import tempfile
import unittest
from unittest.mock import patch
import zipfile

ROOT=Path(__file__).resolve().parents[2]
def module(name):
    spec=importlib.util.spec_from_file_location(name,ROOT/'scripts'/(name+'.py'))
    result=importlib.util.module_from_spec(spec);spec.loader.exec_module(result);return result
fetch=module('fetch_vsf_build_inputs');sdk=module('prepare_ffmpeg_sdk')

class BuildInputTests(unittest.TestCase):
    def test_cache_hit_does_not_open_network(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'cached.zip';p.write_bytes(b'cache')
            with patch.object(fetch.urllib.request,'urlopen',side_effect=AssertionError('network')):
                self.assertEqual(fetch.fetch({'sha256':hashlib.sha256(b'cache').hexdigest()},p),p)
    def test_hash_mismatch_is_not_published(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'candidate.zip'
            with patch.object(fetch.urllib.request,'urlopen',return_value=io.BytesIO(b'bad')):
                with self.assertRaises(ValueError):fetch.fetch({'url':'https://example.invalid/archive','sha256':hashlib.sha256(b'yes').hexdigest(),'bytes':3},p)
            self.assertFalse(p.exists())
    def test_size_overrun_is_not_published(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'candidate.zip'
            with patch.object(fetch.urllib.request,'urlopen',return_value=io.BytesIO(b'too-long')):
                with self.assertRaises(ValueError):fetch.fetch({'url':'https://example.invalid/archive','sha256':'unused','bytes':1},p)
            self.assertFalse(p.exists())
    def test_parent_absolute_and_drive_paths_are_rejected(self):
        for name in ['../outside','/absolute','..\\outside','C:/absolute','x/../../outside']:
            with self.subTest(name=name),tempfile.TemporaryDirectory() as d:
                p=Path(d)/'bad.zip'
                with zipfile.ZipFile(p,'w') as z:z.writestr(name,'payload')
                with self.assertRaises(ValueError):fetch.unpack(p,Path(d)/'out')
    def test_zip_root_is_stripped_without_losing_payload(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'valid.zip'
            with zipfile.ZipFile(p,'w') as z:z.writestr('root/include/example.h','payload')
            fetch.unpack(p,Path(d)/'out',True)
            self.assertEqual((Path(d)/'out/include/example.h').read_text(),'payload')
    def test_non_pe_and_wrong_machine_are_rejected(self):
        invalid=bytearray(128);invalid[:2]=b'MZ';struct.pack_into('<I',invalid,0x3c,64);invalid[64:68]=b'PE\0\0';struct.pack_into('<H',invalid,68,0x14c)
        for blob in [b'',b'not PE',bytes(invalid)]:
            with self.assertRaises((ValueError,struct.error)):sdk.exports(blob)

if __name__=='__main__':unittest.main()
