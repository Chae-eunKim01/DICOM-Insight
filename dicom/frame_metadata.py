from pydicom.sequence import Sequence


def _is_sequence_value(value):
    return isinstance(value,(Sequence,list,tuple)) and value and hasattr(value[0],"__iter__")


def _find_keyword_recursive(ds,keyword):
    if ds is None:
        return None
    try:
        if hasattr(ds,keyword):
            value=getattr(ds,keyword,None)
            if value is not None and str(value).strip()!="":
                return value
    except Exception:
        pass
    try:
        elements=list(ds)
    except Exception:
        return None
    for element in elements:
        try:
            if str(getattr(element,"VR",""))!="SQ":
                continue
            value=element.value
            for item in value:
                found=_find_keyword_recursive(item,keyword)
                if found is not None:
                    return found
        except Exception:
            continue
    return None


def frame_value(ds,keyword,frame_index=None,default=None):
    if ds is None:
        return default

    if frame_index is not None:
        try:
            per_frame=getattr(ds,"PerFrameFunctionalGroupsSequence",None)
            if per_frame and 0<=int(frame_index)<len(per_frame):
                found=_find_keyword_recursive(per_frame[int(frame_index)],keyword)
                if found is not None:
                    return found
        except Exception:
            pass

    try:
        shared=getattr(ds,"SharedFunctionalGroupsSequence",None)
        if shared:
            for item in shared:
                found=_find_keyword_recursive(item,keyword)
                if found is not None:
                    return found
    except Exception:
        pass

    try:
        value=getattr(ds,keyword,None)
        if value is not None and str(value).strip()!="":
            return value
    except Exception:
        pass

    return default


def frame_number(ds,keyword,frame_index=None,default=None):
    value=frame_value(ds,keyword,frame_index,default)
    try:
        if hasattr(value,"__iter__") and not isinstance(value,(str,bytes)):
            value=list(value)[0]
        return float(value)
    except Exception:
        return default


def frame_text(ds,keyword,frame_index=None,default=""):
    value=frame_value(ds,keyword,frame_index,default)
    try:
        if value is None:
            return default
        text=str(value)
        return text if text.strip() else default
    except Exception:
        return default


def frame_group_elements(ds,frame_index=None):
    groups=[]
    try:
        shared=getattr(ds,"SharedFunctionalGroupsSequence",None)
        if shared:
            for item in shared:
                groups.append(("Shared",item))
    except Exception:
        pass
    if frame_index is not None:
        try:
            per_frame=getattr(ds,"PerFrameFunctionalGroupsSequence",None)
            if per_frame and 0<=int(frame_index)<len(per_frame):
                groups.append((f"Frame {int(frame_index)+1}",per_frame[int(frame_index)]))
        except Exception:
            pass
    return groups
