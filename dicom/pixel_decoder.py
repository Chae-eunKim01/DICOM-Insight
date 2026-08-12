from dicom.frame_metadata import frame_number
import numpy as np
from utils.constants import DEFAULT_WINDOW_WIDTH,DEFAULT_WINDOW_LEVEL,MIN_WINDOW_WIDTH

def _first_number(value,default):
    try:
        if hasattr(value,"__iter__") and not isinstance(value,(str,bytes)):
            value=list(value)[0]
        return float(value)
    except Exception:
        return float(default)

def is_color_dataset(ds):
    photometric=str(getattr(ds,"PhotometricInterpretation","")).upper()
    samples=int(getattr(ds,"SamplesPerPixel",1) or 1)
    return samples>1 or photometric in {
        "RGB",
        "YBR_FULL",
        "YBR_FULL_422",
        "YBR_PARTIAL_422",
        "PALETTE COLOR"
    }

def get_default_window(ds,hu,frame_index=None):
    width=frame_number(ds,"WindowWidth",frame_index,None)
    level=frame_number(ds,"WindowCenter",frame_index,None)
    has_window=width is not None and level is not None
    if not has_window:
        width=DEFAULT_WINDOW_WIDTH
        level=DEFAULT_WINDOW_LEVEL

    if not has_window:
        finite=np.asarray(hu)[np.isfinite(hu)]
        if finite.size:
            low,high=np.percentile(finite,[1,99])
            width=max(float(high-low),MIN_WINDOW_WIDTH)
            level=float((high+low)/2)

    return width,level

def _decode_pixel_array(ds,frame_index=None):
    if frame_index is None:
        return ds.pixel_array
    try:
        from pydicom.pixels import pixel_array as pydicom_pixel_array
        return pydicom_pixel_array(ds,index=int(frame_index))
    except Exception:
        arr=ds.pixel_array
        frame_count=int(getattr(ds,"NumberOfFrames",1) or 1)
        if frame_count>1 and arr.ndim>=3:
            return arr[int(frame_index)]
        return arr

def decode_hu(ds,frame_index=None):
    arr=_decode_pixel_array(ds,frame_index)

    if is_color_dataset(ds):
        return np.ascontiguousarray(arr)

    arr=arr.astype(np.float32)
    slope=frame_number(ds,"RescaleSlope",frame_index,1.0)
    intercept=frame_number(ds,"RescaleIntercept",frame_index,0.0)
    return arr*slope+intercept

def apply_window(hu,width,level,invert=False):
    width=max(float(width),MIN_WINDOW_WIDTH)
    low=level-width/2.0
    high=level+width/2.0
    img=np.clip(hu,low,high)
    img=(img-low)/(high-low)*255.0
    img=img.astype(np.uint8)

    if invert:
        img=255-img

    return np.ascontiguousarray(img)

def normalize_color(arr):
    arr=np.asarray(arr)

    if arr.ndim==4:
        arr=arr[0]

    if arr.dtype==np.uint8:
        return np.ascontiguousarray(arr)

    arr=arr.astype(np.float32)
    finite=arr[np.isfinite(arr)]

    if finite.size==0:
        return np.zeros(arr.shape,dtype=np.uint8)

    low=float(np.min(finite))
    high=float(np.max(finite))

    if high<=low:
        return np.zeros(arr.shape,dtype=np.uint8)

    arr=(arr-low)/(high-low)*255.0
    return np.ascontiguousarray(np.clip(arr,0,255).astype(np.uint8))
