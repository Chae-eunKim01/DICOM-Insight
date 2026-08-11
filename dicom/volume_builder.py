import os
from concurrent.futures import ThreadPoolExecutor
import numpy as np


def _float_list(value,default):
    try:
        return [float(v) for v in value]
    except Exception:
        return list(default)


def _slice_position(ds):
    try:
        ipp=[float(v) for v in ds.ImagePositionPatient]
        iop=[float(v) for v in ds.ImageOrientationPatient]
        row=np.array(iop[:3],dtype=float)
        col=np.array(iop[3:],dtype=float)
        normal=np.cross(row,col)
        return float(np.dot(np.array(ipp,dtype=float),normal))
    except Exception:
        try:
            return float(ds.SliceLocation)
        except Exception:
            try:
                return float(ds.InstanceNumber)
            except Exception:
                return 0.0


def _slice_spacing(sorted_ds):
    if len(sorted_ds)<2:
        try:
            return float(sorted_ds[0].SliceThickness)
        except Exception:
            return 1.0
    positions=[]
    for ds in sorted_ds:
        try:
            positions.append(_slice_position(ds))
        except Exception:
            pass
    if len(positions)>=2:
        diffs=np.diff(sorted(positions))
        diffs=np.abs(diffs[np.abs(diffs)>1e-6])
        if diffs.size:
            return float(np.median(diffs))
    try:
        return float(sorted_ds[0].SpacingBetweenSlices)
    except Exception:
        try:
            return float(sorted_ds[0].SliceThickness)
        except Exception:
            return 1.0


def _patient_axis_metadata(sorted_ds):
    result={
        "superior_at_high_index":True,
        "slice_direction":[0.0,0.0,1.0],
        "row_direction":[1.0,0.0,0.0],
        "column_direction":[0.0,1.0,0.0]
    }
    if not sorted_ds:
        return result
    first=sorted_ds[0]
    try:
        iop=np.asarray([float(v) for v in first.ImageOrientationPatient],dtype=float)
        row=iop[:3]
        col=iop[3:]
        result["row_direction"]=row.tolist()
        result["column_direction"]=col.tolist()
    except Exception:
        row=np.array([1.0,0.0,0.0],dtype=float)
        col=np.array([0.0,1.0,0.0],dtype=float)
    direction=None
    if len(sorted_ds)>=2:
        try:
            p0=np.asarray([float(v) for v in sorted_ds[0].ImagePositionPatient],dtype=float)
            p1=np.asarray([float(v) for v in sorted_ds[-1].ImagePositionPatient],dtype=float)
            delta=p1-p0
            norm=float(np.linalg.norm(delta))
            if norm>1e-6:
                direction=delta/norm
        except Exception:
            direction=None
    if direction is None:
        direction=np.cross(row,col)
        norm=float(np.linalg.norm(direction))
        if norm>1e-6:
            direction=direction/norm
        else:
            direction=np.array([0.0,0.0,1.0],dtype=float)
    result["slice_direction"]=direction.tolist()
    result["superior_at_high_index"]=bool(direction[2]>=0.0)
    return result


def _volume_info(volume,spacing,slice_thickness=None,superior_at_high_index=True,slice_direction=None,row_direction=None,column_direction=None,datasets=None,backend="pydicom"):
    sx,sy,sz=[float(v) for v in spacing]
    if slice_thickness is None:
        slice_thickness=sz
    slice_thickness=float(slice_thickness or sz)
    z=int(volume.shape[0]) if volume.ndim>=3 else 1
    return {
        "volume":np.ascontiguousarray(volume,dtype=np.float32),
        "spacing":(sx,sy,sz),
        "datasets":datasets or [],
        "slice_thickness":slice_thickness,
        "slice_spacing":sz,
        "slice_count":z,
        "low_resolution":slice_thickness>=3.0 or sz>=3.0,
        "superior_at_high_index":bool(superior_at_high_index),
        "slice_direction":slice_direction or [0.0,0.0,1.0],
        "row_direction":row_direction or [1.0,0.0,0.0],
        "column_direction":column_direction or [0.0,1.0,0.0],
        "backend":backend
    }


def build_volume(datasets):
    if not datasets:
        raise ValueError("Series is empty.")
    datasets=sorted(datasets,key=_slice_position)
    first=datasets[0]
    patient_axes=_patient_axis_metadata(datasets)
    frames=[]
    for ds in datasets:
        arr=ds.pixel_array
        if arr.ndim!=2:
            raise ValueError("3D reconstruction currently supports single-frame grayscale DICOM only.")
        arr=arr.astype(np.float32,copy=False)
        slope=float(getattr(ds,"RescaleSlope",1.0) or 1.0)
        intercept=float(getattr(ds,"RescaleIntercept",0.0) or 0.0)
        if slope!=1.0 or intercept!=0.0:
            arr=arr*slope+intercept
        frames.append(arr)
    volume=np.stack(frames,axis=0)
    pixel_spacing=_float_list(getattr(first,"PixelSpacing",[1.0,1.0]),[1.0,1.0])
    row_spacing=float(pixel_spacing[0])
    col_spacing=float(pixel_spacing[1])
    slice_spacing=_slice_spacing(datasets)
    try:
        slice_thickness=float(getattr(first,"SliceThickness",slice_spacing) or slice_spacing)
    except Exception:
        slice_thickness=float(slice_spacing)
    return _volume_info(
        volume,(col_spacing,row_spacing,slice_spacing),slice_thickness,
        patient_axes["superior_at_high_index"],patient_axes["slice_direction"],
        patient_axes["row_direction"],patient_axes["column_direction"],datasets,"pydicom"
    )


def _build_volume_simpleitk(paths,progress_callback=None):
    import SimpleITK as sitk
    paths=[str(p) for p in paths]
    if progress_callback:
        progress_callback(0,len(paths))
    reader=sitk.ImageSeriesReader()
    reader.SetFileNames(paths)
    image=reader.Execute()
    volume=sitk.GetArrayFromImage(image)
    if volume.ndim!=3:
        raise ValueError("3D reconstruction currently supports single-frame grayscale DICOM only.")
    spacing=tuple(float(v) for v in image.GetSpacing())
    direction=tuple(float(v) for v in image.GetDirection())
    row=[direction[0],direction[3],direction[6]] if len(direction)>=9 else [1.0,0.0,0.0]
    col=[direction[1],direction[4],direction[7]] if len(direction)>=9 else [0.0,1.0,0.0]
    slc=[direction[2],direction[5],direction[8]] if len(direction)>=9 else [0.0,0.0,1.0]
    if progress_callback:
        progress_callback(len(paths),len(paths))
    return _volume_info(
        volume,spacing,spacing[2],slc[2]>=0.0,slc,row,col,backend="SimpleITK"
    )


def _decode_path(path):
    import pydicom
    ds=pydicom.dcmread(str(path))
    arr=ds.pixel_array
    if arr.ndim!=2:
        raise ValueError("3D reconstruction currently supports single-frame grayscale DICOM only.")
    arr=arr.astype(np.float32,copy=False)
    slope=float(getattr(ds,"RescaleSlope",1.0) or 1.0)
    intercept=float(getattr(ds,"RescaleIntercept",0.0) or 0.0)
    if slope!=1.0 or intercept!=0.0:
        arr=arr*slope+intercept
    try:
        ipp=[float(v) for v in ds.ImagePositionPatient]
    except Exception:
        ipp=None
    try:
        iop=[float(v) for v in ds.ImageOrientationPatient]
    except Exception:
        iop=None
    try:
        pixel_spacing=[float(v) for v in ds.PixelSpacing]
    except Exception:
        pixel_spacing=[1.0,1.0]
    try:
        thickness=float(getattr(ds,"SliceThickness",1.0) or 1.0)
    except Exception:
        thickness=1.0
    try:
        spacing_between=float(getattr(ds,"SpacingBetweenSlices",thickness) or thickness)
    except Exception:
        spacing_between=thickness
    return {
        "arr":arr,"position":_slice_position(ds),"ipp":ipp,"iop":iop,
        "pixel_spacing":pixel_spacing,"slice_thickness":thickness,
        "spacing_between":spacing_between
    }


def _build_volume_parallel(paths,progress_callback=None,max_workers=None):
    paths=list(paths)
    if not paths:
        raise ValueError("Series is empty.")
    if max_workers is None:
        cpu=os.cpu_count() or 4
        max_workers=min(12,max(4,cpu))
    items=[]
    total=len(paths)
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        for completed,item in enumerate(executor.map(_decode_path,paths,chunksize=4),1):
            items.append(item)
            if progress_callback and (completed==total or completed%16==0):
                progress_callback(completed,total)
    items.sort(key=lambda item:item["position"])
    shape=items[0]["arr"].shape
    if any(item["arr"].shape!=shape for item in items):
        raise ValueError("All slices must have the same matrix size for 3D reconstruction.")
    volume=np.stack([item["arr"] for item in items],axis=0)
    first=items[0]
    positions=np.asarray([item["position"] for item in items],dtype=float)
    diffs=np.abs(np.diff(positions))
    diffs=diffs[diffs>1e-6]
    slice_spacing=float(np.median(diffs)) if diffs.size else float(first["spacing_between"])
    iop=first["iop"] or [1.0,0.0,0.0,0.0,1.0,0.0]
    row=np.asarray(iop[:3],dtype=float)
    col=np.asarray(iop[3:],dtype=float)
    direction=np.cross(row,col)
    if len(items)>=2 and items[0]["ipp"] is not None and items[-1]["ipp"] is not None:
        delta=np.asarray(items[-1]["ipp"],dtype=float)-np.asarray(items[0]["ipp"],dtype=float)
        norm=float(np.linalg.norm(delta))
        if norm>1e-6:
            direction=delta/norm
    ps=first["pixel_spacing"]
    return _volume_info(
        volume,(float(ps[1]),float(ps[0]),slice_spacing),first["slice_thickness"],
        direction[2]>=0.0,direction.tolist(),row.tolist(),col.tolist(),backend="Parallel pydicom"
    )


def build_volume_from_paths(paths,progress_callback=None,max_workers=None):
    paths=list(paths)
    if not paths:
        raise ValueError("Series is empty.")
    try:
        return _build_volume_simpleitk(paths,progress_callback)
    except Exception:
        return _build_volume_parallel(paths,progress_callback,max_workers)


def inspect_series_resolution(datasets):
    if isinstance(datasets,dict) and "volume" in datasets:
        return {
            "slice_count":int(datasets.get("slice_count",0)),
            "slice_thickness":float(datasets.get("slice_thickness",0.0)),
            "slice_spacing":float(datasets.get("slice_spacing",0.0)),
            "low_resolution":bool(datasets.get("low_resolution",False))
        }
    if not datasets:
        return {"slice_count":0,"slice_thickness":0.0,"slice_spacing":0.0,"low_resolution":False}
    sorted_ds=sorted(datasets,key=_slice_position)
    first=sorted_ds[0]
    slice_spacing=_slice_spacing(sorted_ds)
    try:
        slice_thickness=float(getattr(first,"SliceThickness",slice_spacing) or slice_spacing)
    except Exception:
        slice_thickness=float(slice_spacing)
    return {
        "slice_count":len(sorted_ds),"slice_thickness":slice_thickness,
        "slice_spacing":slice_spacing,"low_resolution":slice_thickness>=3.0 or slice_spacing>=3.0
    }


def resample_volume_isotropic(volume,spacing,target_spacing=1.0):
    try:
        from scipy.ndimage import zoom
    except Exception as e:
        raise RuntimeError("High-quality MPR resampling requires scipy.\nInstall it with: pip install scipy") from e
    volume=np.asarray(volume,dtype=np.float32)
    sx,sy,sz=[float(v) for v in spacing]
    target=float(target_spacing)
    if target<=0:
        raise ValueError("target_spacing must be > 0")
    zoom_factors=(sz/target,sy/target,sx/target)
    resampled=zoom(volume,zoom_factors,order=1,mode="nearest",prefilter=False)
    return np.ascontiguousarray(resampled,dtype=np.float32),(target,target,target)
