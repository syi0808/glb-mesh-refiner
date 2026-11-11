#!/usr/bin/env python3
"""Tiny CPU orthographic GLB previewer for this project's single textured mesh input."""
import argparse, json, math, struct
from pathlib import Path
from io import BytesIO
import numpy as np
from PIL import Image, ImageDraw, ImageFont

def load(path):
    b=Path(path).read_bytes()
    if b[:4] != b'glTF' or struct.unpack_from('<I',b,4)[0] != 2 or struct.unpack_from('<I',b,8)[0] != len(b):
        raise ValueError('invalid GLB v2 header/length')
    off=12; doc=None; blob=None
    while off < len(b):
        n,typ=struct.unpack_from('<II',b,off);off+=8;chunk=b[off:off+n];off+=n
        if typ==0x4e4f534a: doc=json.loads(chunk.rstrip(b' \0'))
        elif typ==0x004e4942: blob=chunk
    if doc is None or blob is None: raise ValueError('GLB requires JSON and BIN chunks')
    mesh=doc['meshes'][0]; prim=mesh['primitives'][0]
    def acc(aid):
        a=doc['accessors'][aid];v=doc['bufferViews'][a['bufferView']]
        typ=a['type'];width={'SCALAR':1,'VEC2':2,'VEC3':3,'VEC4':4}[typ]
        ctype=a['componentType'];dt={5121:'u1',5123:'<u2',5125:'<u4',5126:'<f4'}[ctype]
        stride=v.get('byteStride',np.dtype(dt).itemsize*width); start=v.get('byteOffset',0)+a.get('byteOffset',0)
        raw=np.ndarray((a['count'],width),dtype=dt,buffer=blob,offset=start,strides=(stride,np.dtype(dt).itemsize))
        return np.array(raw,copy=True)
    p=prim['attributes'];pos=acc(p['POSITION']).astype(np.float64);uv=acc(p['TEXCOORD_0']).astype(np.float64);n=acc(p['NORMAL']).astype(np.float64);inds=acc(prim['indices']).astype(np.int64).reshape(-1,3)
    # Preserve/read embedded base color image bytes directly from bufferViews.
    info=doc['materials'][prim.get('material',0)]['pbrMetallicRoughness'].get('baseColorTexture',{})
    tex=doc['textures'][info['index']];im=doc['images'][tex['source']];v=doc['bufferViews'][im['bufferView']];st=v.get('byteOffset',0);img=Image.open(BytesIO(blob[st:st+v['byteLength']])).convert('RGBA')
    factor=doc['materials'][prim.get('material',0)].get('pbrMetallicRoughness',{}).get('baseColorFactor',[1,1,1,1])
    return {'pos':pos,'uv':uv,'norm':n,'tri':inds,'tex':np.asarray(img),'factor':np.array(factor[:3]),'tri_count':len(inds),'doc':doc,'blob':blob}

def basis(direction):
    d=np.asarray(direction,dtype=float);d/=np.linalg.norm(d)
    upref=np.array([0.,0.,1.]) if abs(d[1])>0.9 else np.array([0.,1.,0.])
    right=np.cross(upref,d);right/=np.linalg.norm(right)
    up=np.cross(d,right);up/=np.linalg.norm(up)
    return d,right,up

def render(m, direction, center, scale, size=520, pad=22):
    pos=m['pos'];uv=m['uv'];normals=m['norm'];tex=m['tex'];tris=m['tri'];
    d,right,up=basis(direction)
    xy=np.column_stack(((pos-center)@right,(pos-center)@up));dep=(pos-center)@d
    s=(size-2*pad)/scale; sx=xy[:,0]*s+size/2; sy=size/2-xy[:,1]*s
    zbuf=np.full((size,size),-1e30,dtype=np.float64); col=np.zeros((size,size,3),dtype=np.uint8)
    light=np.array([-.38,.81,.45]);light/=np.linalg.norm(light)
    th,tw=tex.shape[:2]
    for tri in tris:
        ids=tri; x=sx[ids]; y=sy[ids]
        area=(x[1]-x[0])*(y[2]-y[0])-(y[1]-y[0])*(x[2]-x[0])
        if abs(area)<1e-9:continue
        x0=max(0,int(math.floor(x.min())));x1=min(size-1,int(math.ceil(x.max())))
        y0=max(0,int(math.floor(y.min())));y1=min(size-1,int(math.ceil(y.max())))
        if x1<x0 or y1<y0:continue
        yy,xx=np.mgrid[y0:y1+1,x0:x1+1];px=xx+.5;py=yy+.5
        w0=((x[1]-px)*(y[2]-py)-(y[1]-py)*(x[2]-px))/area
        w1=((x[2]-px)*(y[0]-py)-(y[2]-py)*(x[0]-px))/area
        w2=1.-w0-w1
        inside=(w0>=-1e-7)&(w1>=-1e-7)&(w2>=-1e-7)
        if not inside.any():continue
        z=w0*dep[ids[0]]+w1*dep[ids[1]]+w2*dep[ids[2]]
        ztile=zbuf[y0:y1+1,x0:x1+1];mask=inside&(z>ztile)
        if not mask.any():continue
        u=w0*uv[ids[0],0]+w1*uv[ids[1],0]+w2*uv[ids[2],0]
        v=w0*uv[ids[0],1]+w1*uv[ids[1],1]+w2*uv[ids[2],1]
        # glTF TEXCOORD_0 and image-origin conventions must be interpreted consistently; this path samples PNG pixels without a V inversion.
        tx=np.floor(np.mod(u,1.)*tw).astype(np.int32)%tw;ty=np.floor(np.mod(v,1.)*th).astype(np.int32)%th
        base=tex[ty,tx,:3].astype(np.float64)*m['factor'][None,None,:]
        nn=w0[...,None]*normals[ids[0]]+w1[...,None]*normals[ids[1]]+w2[...,None]*normals[ids[2]]
        nl=np.linalg.norm(nn,axis=2);nn=nn/np.maximum(nl[...,None],1e-12)
        shade=.52+.48*np.abs(nn@light)
        pix=np.clip(base*shade[...,None],0,255).astype(np.uint8)
        ztile[mask]=z[mask]; ct=col[y0:y1+1,x0:x1+1];ct[mask]=pix[mask]
    rgb=np.full((size,size,3),248,dtype=np.uint8);mask=zbuf>-1e29;rgb[mask]=col[mask]
    return Image.fromarray(rgb,'RGB')

def main():
    ap=argparse.ArgumentParser();ap.add_argument('source');ap.add_argument('output');ap.add_argument('png');ap.add_argument('--size',type=int,default=520);args=ap.parse_args()
    a=load(args.source);b=load(args.output);lo=a['pos'].min(0);hi=a['pos'].max(0);center=(lo+hi)/2
    views=[('Front',(0,0,1)),('Back',(0,0,-1)),('Left',(-1,0,0)),('Right',(1,0,0)),('Top',(0,1,0)),('Bottom',(0,-1,0))]
    canvas=Image.new('RGB',(1860,1280),(241,244,248));draw=ImageDraw.Draw(canvas)
    try: font=ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf',24);small=ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf',17)
    except OSError: font=ImageFont.load_default();small=font
    draw.text((32,10),f"GLB comparison: source {a['tri_count']:,} triangles  →  refined {b['tri_count']:,} triangles",fill=(26,36,52),font=font)
    draw.text((34,40),"CPU base-color preview · glTF V coordinates applied without inversion · not a full PBR render",fill=(75,86,102),font=small)
    width,height=600,610;size=args.size
    for k,(name,direction) in enumerate(views):
        col=k%3;row=k//3;x0=20+col*610;y0=70+row*600
        draw.rounded_rectangle((x0,y0,x0+590,y0+590),radius=14,fill='white',outline=(208,216,228),width=2)
        draw.text((x0+18,y0+12),name,fill=(35,49,70),font=font)
        d,right,up=basis(direction); ext=(hi-lo);span=max(np.dot(np.abs(right),ext),np.dot(np.abs(up),ext))*1.15
        imA=render(a,direction,center,span,size=size,pad=28);imB=render(b,direction,center,span,size=size,pad=28)
        thumb=size//2
        imA=imA.resize((thumb,thumb),Image.Resampling.LANCZOS);imB=imB.resize((thumb,thumb),Image.Resampling.LANCZOS)
        xx=x0+26;yy=y0+58
        canvas.paste(imA,(xx,yy));canvas.paste(imB,(xx+thumb+14,yy))
        draw.text((xx+4,yy+thumb+6),f"Source · {a['tri_count']:,} tris",fill=(56,66,80),font=small)
        draw.text((xx+thumb+18,yy+thumb+6),f"Refined · {b['tri_count']:,} tris",fill=(56,66,80),font=small)
    canvas.save(args.png,optimize=True)
    print(f"saved {args.png} size={canvas.size} source={a['tri_count']} refined={b['tri_count']}")
if __name__=='__main__':main()
