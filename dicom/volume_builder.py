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
        iop=np.asarray(
            [float(v) for v in first.ImageOrientationPatient],
            dtype=float
        )
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
            p0=np.asarray(
                [float(v) for v in sorted_ds[0].ImagePositionPatient],
                dtype=float
            )
            p1=np.asarray(
                [float(v) for v in sorted_ds[-1].ImagePositionPatient],
                dtype=float
            )
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

    # DICOM Patient Coordinate System(LPS):
    # +Z = Superior(Head)
    # 따라서 volume index가 증가할수록 +Z로 이동하면
    # high index 쪽이 Head/Superior임.
    result["superior_at_high_index"]=bool(direction[2]>=0.0)

    return result


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

        arr=arr.astype(np.float32)
        slope=float(getattr(ds,"RescaleSlope",1.0) or 1.0)
        intercept=float(getattr(ds,"RescaleIntercept",0.0) or 0.0)
        arr=arr*slope+intercept
        frames.append(arr)

    volume=np.stack(frames,axis=0)

    pixel_spacing=_float_list(
        getattr(first,"PixelSpacing",[1.0,1.0]),
        [1.0,1.0]
    )
    row_spacing=float(pixel_spacing[0])
    col_spacing=float(pixel_spacing[1])
    slice_spacing=_slice_spacing(datasets)

    spacing=(col_spacing,row_spacing,slice_spacing)

    try:
        slice_thickness=float(getattr(first,"SliceThickness",slice_spacing) or slice_spacing)
    except Exception:
        slice_thickness=float(slice_spacing)

    low_resolution=(
        slice_thickness>=3.0
        or slice_spacing>=3.0
    )

    return {
        "volume":np.ascontiguousarray(volume),
        "spacing":spacing,
        "datasets":datasets,
        "slice_thickness":slice_thickness,
        "slice_spacing":slice_spacing,
        "slice_count":len(datasets),
        "low_resolution":low_resolution,
        "superior_at_high_index":patient_axes["superior_at_high_index"],
        "slice_direction":patient_axes["slice_direction"],
        "row_direction":patient_axes["row_direction"],
        "column_direction":patient_axes["column_direction"]
    }


def inspect_series_resolution(datasets):
    if not datasets:
        return {
            "slice_count":0,
            "slice_thickness":0.0,
            "slice_spacing":0.0,
            "low_resolution":False
        }

    sorted_ds=sorted(datasets,key=_slice_position)
    first=sorted_ds[0]
    slice_spacing=_slice_spacing(sorted_ds)

    try:
        slice_thickness=float(getattr(first,"SliceThickness",slice_spacing) or slice_spacing)
    except Exception:
        slice_thickness=float(slice_spacing)

    return {
        "slice_count":len(sorted_ds),
        "slice_thickness":slice_thickness,
        "slice_spacing":slice_spacing,
        "low_resolution":slice_thickness>=3.0 or slice_spacing>=3.0
    }


def resample_volume_isotropic(volume,spacing,target_spacing=1.0):
    try:
        from scipy.ndimage import zoom
    except Exception as e:
        raise RuntimeError(
            "High-quality MPR resampling requires scipy.\n"
            "Install it with: pip install scipy"
        ) from e

    volume=np.asarray(volume,dtype=np.float32)

    sx,sy,sz=[float(v) for v in spacing]
    target=float(target_spacing)

    if target<=0:
        raise ValueError("target_spacing must be > 0")

    # NumPy volume axis order: Z, Y, X
    zoom_factors=(
        sz/target,
        sy/target,
        sx/target
    )

    resampled=zoom(
        volume,
        zoom_factors,
        order=1,
        mode="nearest",
        prefilter=False
    )

    return (
        np.ascontiguousarray(resampled,dtype=np.float32),
        (target,target,target)
    )
