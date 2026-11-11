#!/usr/bin/env python3
"""Independently compare the serialized GLB with its source and retained-face provenance."""
import argparse,json
from collections import Counter
from pathlib import Path
import numpy as np
from validate_glb import parse

def mesh(path):
    m=parse(path);p=m['doc']['meshes'][0]['primitives'][0]
    return (m['decoded'][p['attributes']['POSITION']].astype(float),m['decoded'][p['attributes']['TEXCOORD_0']].astype(float),m['decoded'][p['attributes']['NORMAL']].astype(float),m['decoded'][p['indices']].reshape(-1,3),m)
def metric(p,u):
    E=(p[1:]-p[0]).T;U=(u[1:]-u[0]).T;det=np.linalg.det(U)
    if abs(det)<1e-15:return None
    J=E@np.linalg.inv(U);G=J.T@J
    if np.linalg.det(G)<=1e-14*G[0,0]*G[1,1]:return None
    return G
def evaluate(source,output,provenance):
    sp,su,sn,st,sa=mesh(source);p,u,n,t,oa=mesh(output)
    ids=np.genfromtxt(provenance,delimiter=',',skip_header=1,dtype=int).reshape(-1,2)
    assert len(ids)==len(t) and np.array_equal(ids[:,0],np.arange(len(t)))
    lo=[];hi=[];density=[];cosines=[];flip=0;unchanged_undefined=0;undefined=0
    for (oi,si),tr in zip(ids,t):
        pp,uu=p[tr],u[tr];sp0,su0=sp[st[si]],su[st[si]]
        uv_before=np.linalg.det((su0[1:]-su0[0]).T);uv_after=np.linalg.det((uu[1:]-uu[0]).T)
        if uv_before*uv_after<0:flip+=1
        cr0=np.cross(sp0[1]-sp0[0],sp0[2]-sp0[0]);cr=np.cross(pp[1]-pp[0],pp[2]-pp[0])
        if np.linalg.norm(cr0)>2e-20 and np.linalg.norm(cr)>0:cosines.append(float(cr0@cr/np.linalg.norm(cr0)/np.linalg.norm(cr)))
        G0,G1=metric(sp0,su0),metric(pp,uu)
        if G0 is None:
            undefined+=1
            if np.array_equal(pp,sp0) and np.array_equal(uu,su0):unchanged_undefined+=1
            continue
        if G1 is None:lo.append(0);hi.append(float('inf'));continue
        C=np.linalg.inv(np.linalg.cholesky(G0));ev=np.linalg.eigvalsh(C@G1@C.T)
        if ev.min()<=0:lo.append(0);hi.append(float('inf'));continue
        lo.append(float(np.sqrt(ev[0])));hi.append(float(np.sqrt(ev[1])))
        density.append(float(abs(uv_after/uv_before)*np.linalg.norm(cr0)/np.linalg.norm(cr)))
    edges=Counter(tuple(sorted((int(tr[i]),int(tr[(i+1)%3])))) for tr in t for i in range(3))
    faces=Counter(tuple(sorted(map(int,tr))) for tr in t)
    cr=np.cross(p[t[:,1]]-p[t[:,0]],p[t[:,2]]-p[t[:,0]]);avg=n[t].mean(1)
    return {'triangles':len(t),'vertices':len(p),'uv_orientation_reversals':flip,'geometric_normal_over_90_deg':int(sum(c<0 for c in cosines)),'geometric_normal_over_60_deg':int(sum(c<.5-1e-7 for c in cosines)),'min_source_normal_cosine':min(cosines),'shading_normal_opposition':int(np.sum(np.einsum('ij,ij->i',cr,avg)<-1e-15)),'relative_directional_stretch_min':min(lo),'relative_directional_stretch_max':max(hi),'relative_uv_density_min':min(density),'relative_uv_density_max':max(density),'undefined_source_mapping_faces_retained':undefined,'undefined_mapping_faces_unchanged':unchanged_undefined,'nonmanifold_index_edges':sum(v>2 for v in edges.values()),'duplicate_index_faces':sum(v>1 for v in faces.values()),'image_bytes_equal':sa['images']==oa['images'],'materials_equal':sa['doc']['materials']==oa['doc']['materials']}
if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('source');ap.add_argument('output');ap.add_argument('provenance');args=ap.parse_args();print(json.dumps(evaluate(args.source,args.output,args.provenance),indent=2))
