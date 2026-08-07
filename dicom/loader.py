import os
from concurrent.futures import ThreadPoolExecutor
import pydicom
from utils.geometry import slice_position

def _read_dataset(path):
    try:
        # PixelData is normally by far the largest element.
        # Defer it until viewer.pixel_array is actually requested.
        ds=pydicom.dcmread(
            str(path),
            defer_size=4096
        )
        ds.filename=str(path)
        return ds
    except Exception:
        return None

def load_series(
    paths,
    progress_callback=None,
    max_workers=None,
    progress_batch=16
):
    paths=list(paths)
    total=len(paths)

    if not paths:
        return []

    if max_workers is None:
        cpu=os.cpu_count() or 4
        max_workers=min(16,max(4,cpu*2))

    datasets=[]
    completed=0

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        for ds in executor.map(
            _read_dataset,
            paths,
            chunksize=8
        ):
            completed+=1

            if ds is not None:
                datasets.append(ds)

            if (
                progress_callback
                and (
                    completed==total
                    or completed%progress_batch==0
                )
            ):
                progress_callback(completed,total)

    datasets.sort(key=slice_position)
    return datasets
