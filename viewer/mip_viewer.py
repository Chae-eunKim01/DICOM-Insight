import numpy as np

def full_mip(volume,axis=0):
    if volume is None:
        raise ValueError("Volume is None")
    return np.max(volume,axis=axis)

def slab_mip(volume,center,half_slices,axis=0):
    if axis!=0:
        volume=np.moveaxis(volume,axis,0)
    start=max(0,int(center-half_slices))
    end=min(volume.shape[0],int(center+half_slices+1))
    return np.max(volume[start:end],axis=0)
