import importlib
import json
import io
import struct
import zipfile
import zlib
import pytest
from nexus.human_avatar import DEFAULT_RIG, parse_import

def png(w,h):
    def chunk(kind,data):return struct.pack('>I',len(data))+kind+data+struct.pack('>I',zlib.crc32(kind+data)&0xffffffff)
    return b'\x89PNG\r\n\x1a\n'+chunk(b'IHDR',struct.pack('>IIBBBBB',w,h,8,6,0,0,0))+chunk(b'IDAT',zlib.compress((b'\0'+b'\x88\xaa\xcc\xff'*w)*h))+chunk(b'IEND',b'')

@pytest.fixture
def tool():
    return importlib.import_module('make_avatar_pack')

def files(tmp_path,sheet=(192,192)):
    (tmp_path/'p.png').write_bytes(png(64,64));(tmp_path/'e.png').write_bytes(png(*sheet));return tmp_path/'p.png',tmp_path/'e.png',tmp_path/'out.nexus-avatar'

def test_default_pack_has_eight_mouth_shapes_on_a_3x3_sheet(tool,tmp_path):
    p,e,out=files(tmp_path);tool.main([str(p),str(e),str(out)])
    parsed,rig=parse_import(out.read_bytes())
    assert set(parsed)=={'portrait.png','expressions.png'} and rig['grid']==[3,3] and rig['shapes']==list(range(1,9))
    assert [m[0] for m in rig['mouths']]==list(range(1,9)) and rig['eyes']==DEFAULT_RIG['eyes']

def test_three_shapes_on_the_original_grid_keep_the_original_rig(tool,tmp_path):
    p,e,out=files(tmp_path,(128,128));tool.main([str(p),str(e),str(out),'--shapes','1,2,3'])
    assert parse_import(out.read_bytes())[1]==DEFAULT_RIG

def test_custom_shape_order_and_bad_input_do_not_write_a_pack(tool,tmp_path,capsys):
    p,e,out=files(tmp_path);tool.main([str(p),str(e),str(out),'--shapes','3,1,5,2'])
    rig=parse_import(out.read_bytes())[1];assert rig['shapes']==[3,1,5,2] and len(rig['mouths'])==4
    out.unlink()
    with pytest.raises(SystemExit):tool.main([str(p),str(e),str(out),'--shapes','1,1,2'])   # duplicate shape
    with pytest.raises(SystemExit):tool.main([str(p),str(e),str(out),'--grid','2x2'])       # 8 shapes need 9 cells
    with pytest.raises(SystemExit):tool.main([str(p),str(e),str(out),'--shapes','a,b'])
    assert not out.exists()
