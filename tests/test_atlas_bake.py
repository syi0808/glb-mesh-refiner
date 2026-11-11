#!/usr/bin/env python3
"""Synthetic atlas/bake regression: asymmetric colors, orientation, channels, and GLB parity."""
import io, json, math, re, struct, subprocess, tempfile, sys
from pathlib import Path
import numpy as np
from PIL import Image
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tools'))
from validate_glb import parse
from render_compare import load, render

def build(path):
    # Asymmetric 8x8 quadrant texture. North-west, north-east, south-west,
    # south-east are distinct, so a vertical flip or transposition is visible.
    base=Image.new('RGBA',(8,8)); mr=Image.new('RGBA',(8,8))
    colors=[(240,30,20,255),(20,220,40,255),(25,50,235,255),(240,210,20,255)]
    for y in range(8):
        for x in range(8):
            q=(0 if y<4 else 2)+(0 if x<4 else 1);base.putpixel((x,y),colors[q])
            mr.putpixel((x,y),(11+30*q,45+35*q,80+40*q,255))
    imgs=[]
    for im in (base,mr):
        b=io.BytesIO();im.save(b,format='PNG');imgs.append(b.getvalue())
    pos=np.asarray([[-.5,-.5,0],[.5,-.5,0],[.5,.5,0],[-.5,.5,0]],dtype='<f4')
    uv=np.asarray([[0,0],[1,0],[1,1],[0,1]],dtype='<f4');norm=np.asarray([[0,0,1]]*4,dtype='<f4');ix=np.asarray([0,1,2,0,2,3],dtype='<u4')
    blob=bytearray();views=[];acc=[]
    def add(data,count,typ,comp,target=None):
        while len(blob)%4:blob.append(0)
        off=len(blob);blob.extend(data);v={'buffer':0,'byteOffset':off,'byteLength':len(data)}
        if target:v['target']=target
        vi=len(views);views.append(v);a={'bufferView':vi,'componentType':comp,'count':count,'type':typ}
        if typ=='VEC3' and comp==5126:a['min']=pos.min(0).tolist();a['max']=pos.max(0).tolist()
        acc.append(a);return len(acc)-1
    pa=add(pos.tobytes(),4,'VEC3',5126,34962);ua=add(uv.tobytes(),4,'VEC2',5126,34962);na=add(norm.tobytes(),4,'VEC3',5126,34962);ia=add(ix.tobytes(),6,'SCALAR',5125,34963)
    ims=[]
    for x in imgs:
        while len(blob)%4:blob.append(0)
        off=len(blob);blob.extend(x);iv=len(views);views.append({'buffer':0,'byteOffset':off,'byteLength':len(x)});ims.append({'bufferView':iv,'mimeType':'image/png'})
    doc={'asset':{'version':'2.0'},'buffers':[{'byteLength':len(blob)}],'bufferViews':views,'accessors':acc,'images':ims,'textures':[{'source':0},{'source':1}],
         'materials':[{'pbrMetallicRoughness':{'baseColorTexture':{'index':0},'baseColorFactor':[1,1,1,1],'metallicRoughnessTexture':{'index':1},'metallicFactor':1,'roughnessFactor':1},'doubleSided':True}],
         'meshes':[{'primitives':[{'attributes':{'POSITION':pa,'NORMAL':na,'TEXCOORD_0':ua},'indices':ia,'material':0,'mode':4}]}],'nodes':[{'mesh':0}],'scenes':[{'nodes':[0]}],'scene':0}
    js=json.dumps(doc,separators=(',',':')).encode();js+=b' '*((-len(js))%4);bb=bytes(blob);bb+=b'\0'*((-len(bb))%4)
    path.write_bytes(b'glTF'+struct.pack('<II',2,12+8+len(js)+8+len(bb))+struct.pack('<II',len(js),0x4e4f534a)+js+struct.pack('<II',len(bb),0x004e4942)+bb)

def main():
    subprocess.run([str(ROOT/'glb_atlas_bake'),'--self-test'],check=True,capture_output=True,text=True)
    with tempfile.TemporaryDirectory() as d:
        src=Path(d)/'src.glb';out=Path(d)/'out.glb';report=Path(d)/'report.txt';build(src)
        p=subprocess.run([str(ROOT/'glb_atlas_bake'),str(src),str(out),str(report),'2','256','.02','25'],check=True,capture_output=True,text=True)
        a=parse(src);b=parse(out)
        assert b['triangles']==[2],p.stdout
        assert a['doc']['materials']==b['doc']['materials']
        assert len(b['doc']['images'])==2 and b['images']!=a['images']
        decoded_images=[]
        for im in b['doc']['images']:
            v=b['doc']['bufferViews'][im['bufferView']];off=v.get('byteOffset',0);decoded=Image.open(io.BytesIO(b['blob'][off:off+v['byteLength']])).convert('RGBA');assert decoded.size[0]==decoded.size[1] and decoded.width>=128;decoded_images.append(np.asarray(decoded))
        mr=decoded_images[1];assert tuple(mr[:,:,i].min() for i in range(3))==(11,45,80);assert tuple(mr[:,:,i].max() for i in range(3))==(101,150,200), 'MR R/G/B channel values were reordered or altered'
        report_text=report.read_text();assert 'cross_chart_overlap_texels=0' in report_text
        atlas_size=tuple(map(int,re.search(r'atlas_width=(\d+) atlas_height=(\d+)',report_text).groups()))
        assert all(Image.open(io.BytesIO(b['blob'][b['doc']['bufferViews'][im['bufferView']].get('byteOffset',0):b['doc']['bufferViews'][im['bufferView']].get('byteOffset',0)+b['doc']['bufferViews'][im['bufferView']]['byteLength']])).size==atlas_size for im in b['doc']['images']), 'reported atlas dimensions must match embedded bake images'
        assert 'missing_gutter_texels=0' in report_text
        # Independent CPU base-color renderer compares identical geometry with original UV/material appearance.
        ma=load(str(src));mb=load(str(out));ra=render(ma,(0,0,1),np.zeros(3),1.2,size=128,pad=8);rb=render(mb,(0,0,1),np.zeros(3),1.2,size=128,pad=8)
        aa=np.asarray(ra).astype(np.int16);bb=np.asarray(rb).astype(np.int16);mask=np.any(aa<248,axis=2)|np.any(bb<248,axis=2)
        mae=np.abs(aa[mask]-bb[mask]).mean();assert mae<25, f'orientation/texture regression, object-region MAE={mae:.2f}'
        assert 'fallback_direct_uv_samples=' in report.read_text()
        print(f'atlas integration test passed; object-region CPU preview MAE={mae:.2f}; {p.stdout.strip()}')
if __name__=='__main__':main()
