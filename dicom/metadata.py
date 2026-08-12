from dicom.frame_metadata import frame_value,frame_group_elements
IMPORTANT_TAGS=[
    ("(0010,0020)","Patient ID","PatientID"),
    ("(0010,0010)","Patient Name","PatientName"),
    ("(0010,0040)","Patient Sex","PatientSex"),
    ("(0010,1010)","Patient Age","PatientAge"),
    ("(0008,0020)","Study Date","StudyDate"),
    ("(0008,0030)","Study Time","StudyTime"),
    ("(0008,0021)","Series Date","SeriesDate"),
    ("(0008,0031)","Series Time","SeriesTime"),
    ("(0008,0022)","Acquisition Date","AcquisitionDate"),
    ("(0008,0032)","Acquisition Time","AcquisitionTime"),
    ("(0008,1030)","Study Description","StudyDescription"),
    ("(0020,000D)","Study UID","StudyInstanceUID"),
    ("(0008,103E)","Series Description","SeriesDescription"),
    ("(0020,000E)","Series UID","SeriesInstanceUID"),
    ("(0008,0018)","SOP Instance UID","SOPInstanceUID"),
    ("(0008,0060)","Modality","Modality"),
    ("(0008,0070)","Manufacturer","Manufacturer"),
    ("(0020,0011)","Series Number","SeriesNumber"),
    ("(0020,0013)","Instance Number","InstanceNumber"),
    ("(0028,0010)","Rows","Rows"),
    ("(0028,0011)","Columns","Columns"),
    ("(0028,0008)","Number of Frames","NumberOfFrames"),
    ("(0028,0002)","Samples Per Pixel","SamplesPerPixel"),
    ("(0028,0004)","Photometric Interpretation","PhotometricInterpretation"),
    ("(0018,0050)","Slice Thickness","SliceThickness"),
    ("(0018,0088)","Spacing Between Slices","SpacingBetweenSlices"),
    ("(0028,0030)","Pixel Spacing","PixelSpacing"),
    ("(0020,0037)","Image Orientation Patient","ImageOrientationPatient"),
    ("(0020,0032)","Image Position Patient","ImagePositionPatient"),
    ("(0028,1050)","Window Center","WindowCenter"),
    ("(0028,1051)","Window Width","WindowWidth"),
    ("(0028,1053)","Rescale Slope","RescaleSlope"),
    ("(0028,1052)","Rescale Intercept","RescaleIntercept"),
    ("(0002,0010)","Transfer Syntax UID","file_meta.TransferSyntaxUID")
]

def _nested_getattr(obj,path):
    try:
        current=obj
        for part in path.split("."):
            current=getattr(current,part,None)
            if current is None:
                return ""
        return current
    except Exception:
        return "<Invalid>"

def safe_value_to_text(element):
    try:
        if element.tag.group==0x7FE0 and element.tag.element==0x0010:
            try:
                size=len(element.value) if element.value is not None else 0
            except Exception:
                size=0
            return f"<Pixel Data: {size:,} bytes>"

        value=element.value
        if isinstance(value,bytes):
            if len(value)>128:
                return f"<Binary Data: {len(value):,} bytes>"
            try:
                return value.decode("utf-8",errors="replace")
            except Exception:
                return repr(value)

        text=str(value)
        if len(text)>2000:
            return text[:2000]+" ... <truncated>"
        return text
    except Exception as e:
        return f"<Invalid value: {type(e).__name__}>"

def extract_metadata(ds,frame_index=None):
    if ds is None:
        return []

    rows=[]
    for tag_id,label,path in IMPORTANT_TAGS:
        if "." not in path and path!="file_meta.TransferSyntaxUID":
            value=frame_value(ds,path,frame_index,"")
        else:
            value=_nested_getattr(ds,path)
        try:
            value=str(value) if value is not None else ""
        except Exception:
            value="<Invalid>"
        rows.append((tag_id,label,value))
    return rows

def _safe_element_row(element):
    try:
        tag=f"({element.tag.group:04X},{element.tag.element:04X})"
    except Exception:
        tag="(????,????)"

    try:
        keyword=element.keyword or ""
    except Exception:
        keyword=""

    try:
        name=element.name or keyword or "Unknown"
    except Exception:
        name=keyword or "Unknown"

    try:
        vr=str(element.VR or "")
    except Exception:
        vr=""

    value=safe_value_to_text(element)
    return (tag,name,vr,value)

def _append_recursive_rows(rows,ds,prefix=""):
    try:
        elements=list(ds)
    except Exception:
        return
    for element in elements:
        try:
            if str(getattr(element,"VR",""))=="SQ":
                seq_name=getattr(element,"name","") or getattr(element,"keyword","") or "Sequence"
                for i,item in enumerate(element.value):
                    next_prefix=f"{prefix}{seq_name}[{i+1}] > "
                    _append_recursive_rows(rows,item,next_prefix)
                continue
            tag,name,vr,value=_safe_element_row(element)
            if prefix:
                name=prefix+name
            rows.append((tag,name,vr,value))
        except Exception:
            continue


def extract_elements(ds,frame_index=None):
    if ds is None:
        return []

    rows=[]
    try:
        file_meta=getattr(ds,"file_meta",None)
        if file_meta:
            for element in file_meta:
                rows.append(_safe_element_row(element))
    except Exception:
        pass

    # Top-level elements are shown once. Large functional-group sequences are
    # represented by the Shared group + the currently displayed frame only,
    # instead of flattening all frames into thousands of duplicated rows.
    try:
        for element in ds:
            keyword=str(getattr(element,"keyword","") or "")
            if keyword in ("SharedFunctionalGroupsSequence","PerFrameFunctionalGroupsSequence"):
                continue
            if str(getattr(element,"VR",""))=="SQ":
                seq_name=getattr(element,"name","") or keyword or "Sequence"
                for i,item in enumerate(element.value):
                    _append_recursive_rows(rows,item,f"{seq_name}[{i+1}] > ")
            else:
                rows.append(_safe_element_row(element))
    except Exception:
        pass

    for group_name,group_ds in frame_group_elements(ds,frame_index):
        _append_recursive_rows(rows,group_ds,f"{group_name} > ")

    return rows
