#!/usr/bin/env python3
"""Approximate symmetric surface deviation using nearest-centroid candidates and point-triangle distance."""
import argparse, json
import numpy as np
from scipy.spatial import cKDTree
from validate_glb import parse

def mesh(path):
    m=parse(path);d=m['doc'];b=m['blob'];pr=d['meshes'][0]['primitives'][0]
    def acc(i):
        a=d['accessors'][i];v=d['bufferViews'][a['bufferView']];w={'SCALAR':1,'VEC2':2,'VEC3':3,'VEC4':4}[a['type']];dt={5121:'u1',5123:'<u2',5125:'<u4',5126:'<f4'}[a['componentType']];st=v.get('byteStride',np.dtype(dt).itemsize*w);off=v.get('byteOffset',0)+a.get('byteOffset',0)
        return np.array(np.ndarray((a['count'],w),dtype=dt,buffer=b,offset=off,strides=(st,np.dtype(dt).itemsize)),copy=True)
    P=acc(pr['attributes']['POSITION']).astype(float);F=acc(pr['indices']).astype(np.int64).ravel().reshape(-1,3)
    return P,F

def sample(P,F):
    tri=P[F]; return np.concatenate([P,(tri[:,0]+tri[:,1]+tri[:,2])/3],axis=0),tri

def ptri(P,T):
    # P [batch,3], T [batch,K,3,3]
    a=T[:,:,0,:];b=T[:,:,1,:];c=T[:,:,2,:];ab=b-a;ac=c-a;ap=P[:,None,:]-a
    n=np.cross(ab,ac);nn=np.linalg.norm(n,axis=2);nh=n/np.maximum(nn[:,:,None],1e-30)
    plane=np.sum(ap*nh,axis=2);proj=ap-plane[:,:,None]*nh
    v0=ab;v1=ac;v2=proj
    d00=np.sum(v0*v0,axis=2);d01=np.sum(v0*v1,axis=2);d11=np.sum(v1*v1,axis=2);d20=np.sum(v2*v0,axis=2);d21=np.sum(v2*v1,axis=2)
    den=np.maximum(d00*d11-d01*d01,1e-30);v=(d11*d20-d01*d21)/den;w=(d00*d21-d01*d20)/den
    inside=(v>=0)&(w>=0)&(v+w<=1)&(nn>1e-20)
    def segdist(q,x,y):
        e=y-x;u=np.sum((q-x)*e,axis=2)/np.maximum(np.sum(e*e,axis=2),1e-30);u=np.clip(u,0,1);r=q-(x+u[:,:,None]*e);return np.sum(r*r,axis=2)
    d=minseg=np.minimum(np.minimum(segdist(P[:,None,:],a,b),segdist(P[:,None,:],b,c)),segdist(P[:,None,:],c,a))
    d=np.where(inside,plane*plane,minseg);return np.sqrt(np.maximum(d,0))

def direction(source_path,target_path,k=32):
    P,F=mesh(source_path);Q,G=mesh(target_path);samples,tri=sample(P,F);tgt=Q[G];cent=tgt.mean(axis=1);tree=cKDTree(cent);out=[]
    for start in range(0,len(samples),256):
        pts=samples[start:start+256];_,ids=tree.query(pts,k=min(k,len(cent)));ids=np.asarray(ids);ids=ids.reshape((len(pts),-1));cand=tgt[ids];dist=ptri(pts,cand);out.append(dist.min(axis=1))
    return np.concatenate(out)

def summary(a,diag):return {'mean':float(a.mean()),'p95':float(np.quantile(a,.95)),'p99':float(np.quantile(a,.99)),'max':float(a.max()),'p99_over_bbox_diagonal':float(np.quantile(a,.99)/diag),'max_over_bbox_diagonal':float(a.max()/diag)}

def main():
    ap=argparse.ArgumentParser();ap.add_argument('source');ap.add_argument('output');args=ap.parse_args()
    P,F=mesh(args.source);Q,G=mesh(args.output);diag=float(np.linalg.norm(P.max(0)-P.min(0)))
    a=direction(args.source,args.output);b=direction(args.output,args.source)
    print(json.dumps({'sampling':'source vertices + face centroids and reverse; nearest 32 target-face centroids, exact point-to-triangle distance','bbox_diagonal':diag,'source_to_output':summary(a,diag),'output_to_source':summary(b,diag)},indent=2))
if __name__=='__main__':main()
