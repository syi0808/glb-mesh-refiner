#!/usr/bin/env python3
"""Optional VTK 9.3+ QEM benchmark. This deliberately does not write a replacement GLB."""
import argparse, json, os, tempfile
from pathlib import Path
import numpy as np
from scipy.spatial import cKDTree
import vtk
from vtk.util.numpy_support import numpy_to_vtk, numpy_to_vtkIdTypeArray, vtk_to_numpy
from validate_glb import parse
from compare_surface import ptri, summary

def load_mesh(path):
    d=parse(path);doc=d['doc'];blob=d['blob'];prim=doc['meshes'][0]['primitives'][0]
    def attr(aid):
        a=doc['accessors'][aid];v=doc['bufferViews'][a['bufferView']];width={'SCALAR':1,'VEC2':2,'VEC3':3}[a['type']];dt={5123:'<u2',5125:'<u4',5126:'<f4'}[a['componentType']];stride=v.get('byteStride',np.dtype(dt).itemsize*width);start=v.get('byteOffset',0)+a.get('byteOffset',0)
        return np.array(np.ndarray((a['count'],width),dtype=dt,buffer=blob,offset=start,strides=(stride,np.dtype(dt).itemsize)),copy=True)
    p=prim['attributes']
    return attr(p['POSITION']).astype(np.float64),attr(p['TEXCOORD_0']).astype(np.float64),attr(p['NORMAL']).astype(np.float64),attr(prim['indices']).astype(np.int64).reshape(-1,3)

def vtk_components(poly):
    f=vtk.vtkPolyDataConnectivityFilter();f.SetInputData(poly);f.SetExtractionModeToAllRegions();f.Update();return int(f.GetNumberOfExtractedRegions())

def points_to_polydata(P,U,N,F):
    vp=vtk.vtkPoints();vp.SetData(numpy_to_vtk(np.ascontiguousarray(P,dtype=np.float32),deep=True))
    cells=np.empty((len(F),4),dtype=np.int64);cells[:,0]=3;cells[:,1:]=F
    ca=vtk.vtkCellArray();ca.SetCells(len(F),numpy_to_vtkIdTypeArray(cells.ravel(),deep=True))
    poly=vtk.vtkPolyData();poly.SetPoints(vp);poly.SetPolys(ca)
    tc=numpy_to_vtk(np.ascontiguousarray(U,dtype=np.float32),deep=True);tc.SetNumberOfComponents(2);tc.SetName('TEXCOORD_0');poly.GetPointData().SetTCoords(tc)
    nm=numpy_to_vtk(np.ascontiguousarray(N,dtype=np.float32),deep=True);nm.SetNumberOfComponents(3);nm.SetName('NORMAL');poly.GetPointData().SetNormals(nm)
    return poly

def surface_direction(SP,SF,TP,TF,k=32):
    src_tri=SP[SF];tgt_tri=TP[TF];samples=np.concatenate([SP,(src_tri[:,0]+src_tri[:,1]+src_tri[:,2])/3],axis=0)
    tree=cKDTree(tgt_tri.mean(axis=1));out=[]
    for st in range(0,len(samples),256):
        pts=samples[st:st+256];_,ids=tree.query(pts,k=min(k,len(tgt_tri)));ids=np.asarray(ids).reshape(len(pts),-1);out.append(ptri(pts,tgt_tri[ids]).min(axis=1))
    return np.concatenate(out)

def comp_stats(P,F):
    poly=points_to_polydata(P,np.zeros((len(P),2)),np.zeros((len(P),3)),F)
    return vtk_components(poly)

def main():
    ap=argparse.ArgumentParser();ap.add_argument('input');ap.add_argument('--target-triangles',type=int,default=4000);ap.add_argument('--report',default='vtk-benchmark.json');ap.add_argument('--log',default='vtk-warnings.log');args=ap.parse_args()
    P,U,N,F=load_mesh(args.input);poly=points_to_polydata(P,U,N,F);before=vtk_components(poly)
    dec=vtk.vtkQuadricDecimation();dec.SetInputData(poly);dec.SetTargetReduction(max(0.,min(.99,1.-args.target_triangles/len(F))))
    dec.AttributeErrorMetricOn();dec.TCoordsAttributeOn();dec.NormalsAttributeOn();dec.MapPointDataOn()
    logpath=Path(args.log);logpath.parent.mkdir(parents=True,exist_ok=True)
    saved=os.dup(2)
    try:
        with logpath.open('wb') as log:
            os.dup2(log.fileno(),2)
            dec.Update()
            os.dup2(saved,2)
    finally:
        os.dup2(saved,2);os.close(saved)
    out=dec.GetOutput();vtkP=vtk_to_numpy(out.GetPoints().GetData()).astype(np.float64);polys=vtk_to_numpy(out.GetPolys().GetData()).reshape(-1,4);vtkF=polys[:,1:].astype(np.int64)
    uv=out.GetPointData().GetTCoords();normal=out.GetPointData().GetNormals();vtkU=vtk_to_numpy(uv).reshape(-1,2) if uv else None;vtkN=vtk_to_numpy(normal).reshape(-1,3) if normal else None
    c_after=vtk_components(out);diag=float(np.linalg.norm(P.max(0)-P.min(0)));a=surface_direction(P,F,vtkP,vtkF);b=surface_direction(vtkP,vtkF,P,F)
    log=logpath.read_text(errors='replace');warnings=sum(1 for line in log.splitlines() if 'WARN' in line or 'ERR|' in line)
    report={'library':'VTK','version':vtk.vtkVersion.GetVTKVersion(),'algorithm':'vtkQuadricDecimation; native VTK implementation via installed Python bindings','source_triangles':int(len(F)),'target_triangles':int(args.target_triangles),'output_triangles':int(len(vtkF)),'source_index_connected_components':before,'output_index_connected_components':c_after,'component_definition':'vtkPolyDataConnectivityFilter shared-point connectivity; not edge-connected components','attributes':{'uv_present':vtkU is not None,'normal_present':vtkN is not None,'uv_count':int(len(vtkU)) if vtkU is not None else 0,'normal_count':int(len(vtkN)) if vtkN is not None else 0,'all_uv_finite':bool(np.isfinite(vtkU).all()) if vtkU is not None else False,'all_normals_finite':bool(np.isfinite(vtkN).all()) if vtkN is not None else False,'uv_min':vtkU.min(0).tolist() if vtkU is not None else None,'uv_max':vtkU.max(0).tolist() if vtkU is not None else None},'vtk_warning_error_line_count':warnings,'warning_log':str(logpath),'surface_distance_method':'vertices + triangle centroids; nearest 32 target triangle centroids; exact point-to-triangle distance','bbox_diagonal':diag,'source_to_vtk':summary(a,diag),'vtk_to_source':summary(b,diag),'production_decision':'benchmark only; not a GLB replacement path (component count changes and warnings require further audit)'}
    Path(args.report).write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2))
if __name__=='__main__':main()
