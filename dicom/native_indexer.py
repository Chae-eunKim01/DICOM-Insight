import math
import os
import struct
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor

_LONG_VR={b"OB",b"OD",b"OF",b"OL",b"OV",b"OW",b"SQ",b"UC",b"UR",b"UT",b"UN",b"SV",b"UV"}
_TEXT_TAGS={
    (0x0008,0x0005):"specific_character_set",
    (0x0008,0x0020):"study_date",
    (0x0008,0x0030):"study_time",
    (0x0008,0x0060):"modality",
    (0x0008,0x1030):"study_description",
    (0x0008,0x103E):"series_description",
    (0x0010,0x0010):"patient_name",
    (0x0010,0x0020):"patient_id",
    (0x0020,0x000D):"study_uid",
    (0x0020,0x000E):"series_uid",
    (0x0020,0x0011):"series_number",
    (0x0020,0x0013):"instance_number"
}
_ESSENTIAL=("study_uid","series_uid")
_INITIAL_READ=65536
_EXPANDED_READ=262144
_MAX_HEADER_READ=1048576


def _decode(raw,charset=""):
    raw=raw.rstrip(b"\x00 ")
    if not raw:
        return ""
    cs=charset.upper().replace("-","_")
    encodings=[]
    if "IR 149" in cs or "IR_149" in cs:
        encodings.extend(("iso2022_kr","cp949"))
    elif "IR 192" in cs or "UTF" in cs:
        encodings.append("utf-8")
    elif "IR 100" in cs:
        encodings.append("latin1")
    encodings.extend(("utf-8","ascii","latin1"))
    for encoding in encodings:
        try:
            return raw.decode(encoding).strip()
        except Exception:
            pass
    return raw.decode("latin1",errors="replace").strip()


def _transfer_syntax(data):
    if len(data)<132 or data[128:132]!=b"DICM":
        return "",132 if len(data)>=132 else 0
    pattern=b"\x02\x00\x10\x00"
    pos=data.find(pattern,132,min(len(data),8192))
    if pos<0 or pos+8>len(data):
        return "",132
    vr=data[pos+4:pos+6]
    if vr in _LONG_VR:
        if pos+12>len(data):
            return "",132
        length=struct.unpack_from("<I",data,pos+8)[0]
        start=pos+12
    else:
        length=struct.unpack_from("<H",data,pos+6)[0]
        start=pos+8
    end=start+length
    if end>len(data):
        return "",132
    return _decode(data[start:end]),end


def _syntax(data):
    ts,_=_transfer_syntax(data)
    if ts=="1.2.840.10008.1.2":
        return False,"<"
    if ts=="1.2.840.10008.1.2.2":
        return True,">"
    if ts=="1.2.840.10008.1.2.1.99":
        return None,None
    if ts:
        return True,"<"

    # No Part-10 preamble: infer common dataset encodings from the first bytes.
    start=0
    if len(data)>=8:
        vr=data[4:6]
        if vr.isalpha() and vr.isupper():
            return True,"<"
    return False,"<"


def _tag_bytes(tag,endian):
    return struct.pack(endian+"HH",tag[0],tag[1])


def _extract_value(data,pos,explicit,endian):
    if pos<0 or pos+8>len(data):
        return None
    if explicit:
        vr=data[pos+4:pos+6]
        if not (len(vr)==2 and vr.isalpha() and vr.isupper()):
            return None
        if vr in _LONG_VR:
            if pos+12>len(data):
                return None
            length=struct.unpack_from(endian+"I",data,pos+8)[0]
            start=pos+12
        else:
            length=struct.unpack_from(endian+"H",data,pos+6)[0]
            start=pos+8
    else:
        length=struct.unpack_from(endian+"I",data,pos+4)[0]
        start=pos+8
    if length==0xFFFFFFFF or length>65536:
        return None
    end=start+length
    if end>len(data):
        return None
    return data[start:end]


def _find_tag_value(data,tag,explicit,endian,start=0):
    pattern=_tag_bytes(tag,endian)
    pos=data.find(pattern,start)
    while pos>=0:
        raw=_extract_value(data,pos,explicit,endian)
        if raw is not None:
            return raw
        pos=data.find(pattern,pos+1)
    return None


def _parse_buffer(data,path):
    explicit,endian=_syntax(data)
    if explicit is None:
        return None

    # For Part-10 files, avoid matching group-0002 values by starting after the preamble.
    search_start=132 if len(data)>=132 and data[128:132]==b"DICM" else 0
    raw={}
    for tag,key in _TEXT_TAGS.items():
        value=_find_tag_value(data,tag,explicit,endian,search_start)
        if value is not None:
            raw[key]=value

    charset=_decode(raw.get("specific_character_set",b""))
    values={key:_decode(value,charset) for key,value in raw.items() if key!="specific_character_set"}
    if not all(values.get(key) for key in _ESSENTIAL):
        return None

    return {
        "path":path,
        "patient_id":values.get("patient_id") or "Unknown",
        "patient_name":values.get("patient_name","") or "",
        "study_uid":values.get("study_uid") or "Unknown",
        "study_date":values.get("study_date","") or "",
        "study_time":values.get("study_time","") or "",
        "study_description":values.get("study_description","") or "",
        "series_uid":values.get("series_uid") or "Unknown",
        "series_description":values.get("series_description","") or "",
        "series_number":values.get("series_number","") or "",
        "modality":values.get("modality","") or "",
        "instance_number":values.get("instance_number","") or "",
        "image_position":None,
        "image_orientation":None
    }


def read_native_header(path):
    try:
        with open(path,"rb") as handle:
            data=handle.read(_INITIAL_READ)
            item=_parse_buffer(data,path)
            if item is not None:
                return item

            # Some vendors place long private/sequence metadata before the UIDs.
            # Expand only for those exceptional files instead of penalizing every file.
            for target in (_EXPANDED_READ,_MAX_HEADER_READ):
                if len(data)>=target:
                    continue
                more=handle.read(target-len(data))
                if not more:
                    break
                data+=more
                item=_parse_buffer(data,path)
                if item is not None:
                    return item
    except OSError:
        return None
    return None


def _number(value,default=float("inf")):
    try:
        return float(value)
    except Exception:
        return default


def _file_sort_key(item):
    instance=_number(item.get("instance_number"))
    if math.isfinite(instance):
        return (0,instance,os.path.basename(item["path"]).lower())
    return (1,os.path.basename(item["path"]).lower())


def _worker_count(file_count):
    cpu=os.cpu_count() or 4
    if file_count<128:
        return min(4,max(2,cpu))
    if file_count<1000:
        return min(8,max(4,cpu))
    return min(12,max(6,cpu))


def build_native_index(paths,progress_callback=None,progress_batch=1024,max_workers=None):
    paths=list(dict.fromkeys(os.fspath(path) for path in paths))
    total=len(paths)
    index=defaultdict(lambda:defaultdict(lambda:defaultdict(list)))
    info={}
    if not total:
        return index,info,[]

    series_items=defaultdict(list)
    dicom_count=0
    workers=max_workers or _worker_count(total)

    def accept(item):
        nonlocal dicom_count
        if item is None:
            return
        dicom_count+=1
        patient_id=item["patient_id"]
        study_uid=item["study_uid"]
        series_uid=item["series_uid"]
        series_items[(patient_id,study_uid,series_uid)].append(item)
        info.setdefault(patient_id,{"patient_name":item["patient_name"]})
        info.setdefault(study_uid,{"study_date":item["study_date"],"study_description":item["study_description"]})
        info.setdefault(series_uid,{"series_description":item["series_description"],"modality":item["modality"],"series_number":item["series_number"]})

    if workers<=1:
        for completed,path in enumerate(paths,1):
            accept(read_native_header(path))
            if progress_callback and (completed==total or completed%progress_batch==0):
                progress_callback(completed,total,dicom_count)
    else:
        with ThreadPoolExecutor(max_workers=workers,thread_name_prefix="DICOMNativeIndex") as executor:
            for completed,item in enumerate(executor.map(read_native_header,paths,chunksize=64),1):
                accept(item)
                if progress_callback and (completed==total or completed%progress_batch==0):
                    progress_callback(completed,total,dicom_count)

    sorted_all_paths=[]
    for (patient_id,study_uid,series_uid),series in series_items.items():
        series.sort(key=_file_sort_key)
        sorted_paths=[item["path"] for item in series]
        index[patient_id][study_uid][series_uid]=sorted_paths
        sorted_all_paths.extend(sorted_paths)

    return index,info,sorted_all_paths
