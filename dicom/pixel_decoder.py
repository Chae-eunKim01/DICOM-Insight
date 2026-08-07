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

def get_default_window(ds,hu):
    width=_first_number(getattr(ds,"WindowWidth",None),DEFAULT_WINDOW_WIDTH)
    level=_first_number(getattr(ds,"WindowCenter",None),DEFAULT_WINDOW_LEVEL)

    if not hasattr(ds,"WindowWidth") or not hasattr(ds,"WindowCenter"):
        finite=np.asarray(hu)[np.isfinite(hu)]
        if finite.size:
            low,high=np.percentile(finite,[1,99])
            width=max(float(high-low),MIN_WINDOW_WIDTH)
            level=float((high+low)/2)

    return width,level

def decode_hu(ds):
    arr=ds.pixel_array

    if is_color_dataset(ds):
        return np.ascontiguousarray(arr)

    arr=arr.astype(np.float32)
    slope=_first_number(getattr(ds,"RescaleSlope",1.0),1.0)
    intercept=_first_number(getattr(ds,"RescaleIntercept",0.0),0.0)
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
