import numpy as np

def slice_normal(image_orientation_patient):
    if not image_orientation_patient or len(image_orientation_patient)!=6:
        return None
    row=np.asarray(image_orientation_patient[:3],dtype=float)
    col=np.asarray(image_orientation_patient[3:],dtype=float)
    normal=np.cross(row,col)
    norm=np.linalg.norm(normal)
    if norm==0:
        return None
    return normal/norm

def slice_position(ds):
    iop=getattr(ds,"ImageOrientationPatient",None)
    ipp=getattr(ds,"ImagePositionPatient",None)
    normal=slice_normal(iop)
    if normal is not None and ipp is not None and len(ipp)==3:
        return float(np.dot(np.asarray(ipp,dtype=float),normal))
    instance=getattr(ds,"InstanceNumber",0)
    try:
        return float(instance)
    except Exception:
        return 0.0
