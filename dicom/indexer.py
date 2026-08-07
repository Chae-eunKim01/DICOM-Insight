import os
import math
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor
import pydicom
import numpy as np

from dicom.index_cache import load_cached,save_cached

INDEX_TAGS=[
    "SpecificCharacterSet",
    "PatientID",
    "PatientName",
    "StudyInstanceUID",
    "StudyDate",
    "StudyDescription",
    "SeriesInstanceUID",
    "SeriesDescription",
    "SeriesNumber",
    "Modality",
    "InstanceNumber",
    "ImagePositionPatient",
    "ImageOrientationPatient"
]

def _text(ds,name,default="Unknown"):
    value=getattr(ds,name,None)
    if value is None or str(value).strip()=="":
        return default
    return str(value)

def _float_list(value):
    try:
        return [float(v) for v in value]
    except Exception:
        return None

def _read_header(path):
    try:
        ds=pydicom.dcmread(
            path,
            stop_before_pixels=True,
            specific_tags=INDEX_TAGS,
            force=False
        )

        patient_id=_text(ds,"PatientID")
        patient_name=_text(ds,"PatientName","")
        study_uid=_text(ds,"StudyInstanceUID")
        series_uid=_text(ds,"SeriesInstanceUID")

        if study_uid=="Unknown" or series_uid=="Unknown":
            return None

        return {
            "path":path,
            "patient_id":patient_id,
            "patient_name":patient_name,
            "study_uid":study_uid,
            "study_date":_text(ds,"StudyDate",""),
            "study_description":_text(ds,"StudyDescription",""),
            "series_uid":series_uid,
            "series_description":_text(ds,"SeriesDescription",""),
            "series_number":_text(ds,"SeriesNumber",""),
            "modality":_text(ds,"Modality",""),
            "instance_number":_text(ds,"InstanceNumber",""),
            "image_position":_float_list(
                getattr(ds,"ImagePositionPatient",None)
            ),
            "image_orientation":_float_list(
                getattr(ds,"ImageOrientationPatient",None)
            )
        }
    except Exception:
        return None

def _number(value,default=float("inf")):
    try:
        return float(value)
    except Exception:
        return default

def _slice_coordinate(item):
    try:
        ipp=np.asarray(item.get("image_position"),dtype=float)
        iop=np.asarray(item.get("image_orientation"),dtype=float)

        if ipp.size>=3 and iop.size>=6:
            row=iop[:3]
            col=iop[3:6]
            normal=np.cross(row,col)
            norm=float(np.linalg.norm(normal))

            if norm>1e-8:
                normal=normal/norm
                return float(np.dot(ipp[:3],normal))
    except Exception:
        pass

    try:
        ipp=item.get("image_position")
        if ipp is not None and len(ipp)>=3:
            return float(ipp[2])
    except Exception:
        pass

    return None

def _file_sort_key(item):
    instance=_number(item.get("instance_number"))

    if math.isfinite(instance):
        return (
            0,
            instance,
            os.path.basename(item["path"]).lower()
        )

    pos=_slice_coordinate(item)

    if pos is not None:
        return (
            1,
            pos,
            os.path.basename(item["path"]).lower()
        )

    return (
        2,
        os.path.basename(item["path"]).lower()
    )


def _default_workers(file_count=0):
    cpu=os.cpu_count() or 4

    # DICOM header read는 대부분 local disk I/O입니다.
    # 너무 많은 thread는 오히려 느려질 수 있어 파일 수에 따라 단계적으로 조절합니다.
    if file_count<300:
        return min(16,max(6,cpu*2))
    if file_count<1500:
        return min(28,max(10,cpu*3))
    return min(36,max(12,cpu*4))


def build_index_fast(
    paths,
    progress_callback=None,
    max_workers=None,
    progress_batch=128
):
    paths=list(dict.fromkeys(os.fspath(p) for p in paths))
    total=len(paths)

    index=defaultdict(lambda:defaultdict(lambda:defaultdict(list)))
    info={}
    series_items=defaultdict(list)

    if total==0:
        return index,info,[]

    cached=load_cached(paths)
    uncached=[p for p in paths if p not in cached]

    items=[]
    items.extend(cached.values())

    completed=len(cached)
    dicom_count=len(cached)

    if progress_callback and completed:
        progress_callback(completed,total,dicom_count)

    newly_read=[]

    if uncached:
        workers=max_workers or _default_workers(len(uncached))

        with ThreadPoolExecutor(max_workers=workers) as executor:
            # map() has substantially less bookkeeping overhead than creating
            # thousands of Future objects and consuming as_completed().
            for item in executor.map(
                _read_header,
                uncached,
                chunksize=16
            ):
                completed+=1

                if item is not None:
                    dicom_count+=1
                    items.append(item)
                    newly_read.append(item)

                if (
                    progress_callback
                    and (
                        completed==total
                        or completed%progress_batch==0
                    )
                ):
                    progress_callback(
                        completed,
                        total,
                        dicom_count
                    )

    # One SQLite transaction, never one DB write per DICOM.
    if newly_read:
        save_cached(newly_read)

    for item in items:
        patient_id=item["patient_id"]
        study_uid=item["study_uid"]
        series_uid=item["series_uid"]

        series_items[
            (patient_id,study_uid,series_uid)
        ].append(item)

        info.setdefault(patient_id,{
            "patient_name":item["patient_name"]
        })
        info.setdefault(study_uid,{
            "study_date":item["study_date"],
            "study_description":item["study_description"]
        })
        info.setdefault(series_uid,{
            "series_description":item["series_description"],
            "modality":item["modality"],
            "series_number":item["series_number"]
        })

    sorted_all_paths=[]

    for (patient_id,study_uid,series_uid),series in series_items.items():
        series.sort(key=_file_sort_key)
        sorted_paths=[item["path"] for item in series]

        index[
            patient_id
        ][
            study_uid
        ][
            series_uid
        ]=sorted_paths

        sorted_all_paths.extend(sorted_paths)

    return index,info,sorted_all_paths
