import struct

_LONG_VR={b"OB",b"OD",b"OF",b"OL",b"OV",b"OW",b"SQ",b"UC",b"UR",b"UT",b"UN",b"SV",b"UV"}
_WANTED={
    (0x0008,0x0005):"specific_character_set",
    (0x0008,0x0020):"study_date",
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
_ESSENTIAL={"study_uid","series_uid"}


def _clean_text(value,charset=""):
    value=value.rstrip(b"\x00 ")
    if not value:
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
            return value.decode(encoding).strip()
        except Exception:
            continue
    return value.decode("latin1",errors="replace").strip()


def _float_list(text):
    try:
        return [float(v) for v in text.split("\\")]
    except Exception:
        return None


def _parse_element_header(data,offset,explicit,endian):
    if offset+8>len(data):
        return None
    group,element=struct.unpack_from(endian+"HH",data,offset)
    if explicit:
        vr=data[offset+4:offset+6]
        if vr in _LONG_VR:
            if offset+12>len(data):
                return None
            length=struct.unpack_from(endian+"I",data,offset+8)[0]
            return group,element,vr,length,offset+12
        length=struct.unpack_from(endian+"H",data,offset+6)[0]
        return group,element,vr,length,offset+8
    length=struct.unpack_from(endian+"I",data,offset+4)[0]
    return group,element,b"",length,offset+8


def _meta_transfer_syntax(data):
    offset=132
    transfer_syntax=""
    while offset+8<=len(data):
        parsed=_parse_element_header(data,offset,True,"<")
        if parsed is None:
            return "",offset
        group,element,vr,length,value_offset=parsed
        if group!=0x0002:
            return transfer_syntax,offset
        if length==0xFFFFFFFF or value_offset+length>len(data):
            return "",offset
        if element==0x0010:
            transfer_syntax=_clean_text(data[value_offset:value_offset+length])
        offset=value_offset+length
    return transfer_syntax,offset


def read_fast_header(path,read_size=16384):
    try:
        with open(path,"rb",buffering=0) as handle:
            data=handle.read(read_size)
    except OSError:
        return None

    if len(data)<140 or data[128:132]!=b"DICM":
        return None

    transfer_syntax,offset=_meta_transfer_syntax(data)
    if not transfer_syntax:
        return None

    if transfer_syntax=="1.2.840.10008.1.2":
        explicit=False
        endian="<"
    elif transfer_syntax=="1.2.840.10008.1.2.2":
        explicit=True
        endian=">"
    elif transfer_syntax=="1.2.840.10008.1.2.1.99":
        return None
    else:
        explicit=True
        endian="<"

    values={}
    raw_values={}
    charset=""

    while offset+8<=len(data):
        parsed=_parse_element_header(data,offset,explicit,endian)
        if parsed is None:
            return None
        group,element,vr,length,value_offset=parsed

        if group==0x7FE0 and element==0x0010:
            break
        if length==0xFFFFFFFF:
            return None
        end=value_offset+length
        if end>len(data):
            return None

        key=_WANTED.get((group,element))
        if key:
            raw=data[value_offset:end]
            raw_values[key]=raw
            if key=="specific_character_set":
                charset=_clean_text(raw)
                values[key]=charset
            elif key in ("image_position","image_orientation"):
                values[key]=_float_list(_clean_text(raw,charset))
            else:
                values[key]=_clean_text(raw,charset)

        offset=end

        # Tree/index 생성에는 0020,0013(Instance Number)까지만 필요합니다.
        # Image Position/Orientation은 실제 Series/MPR 로딩 시 읽으므로 Import 단계에서 건너뜁니다.
        if _ESSENTIAL.issubset(values) and (group>0x0020 or (group==0x0020 and element>=0x0013)):
            break

    if not _ESSENTIAL.issubset(values):
        return None

    if charset:
        for key,raw in raw_values.items():
            if key not in ("specific_character_set","image_position","image_orientation"):
                values[key]=_clean_text(raw,charset)

    return {
        "path":path,
        "patient_id":values.get("patient_id") or "Unknown",
        "patient_name":values.get("patient_name","") or "",
        "study_uid":values.get("study_uid") or "Unknown",
        "study_date":values.get("study_date","") or "",
        "study_description":values.get("study_description","") or "",
        "series_uid":values.get("series_uid") or "Unknown",
        "series_description":values.get("series_description","") or "",
        "series_number":values.get("series_number","") or "",
        "modality":values.get("modality","") or "",
        "instance_number":values.get("instance_number","") or "",
        "image_position":None,
        "image_orientation":None
    }
