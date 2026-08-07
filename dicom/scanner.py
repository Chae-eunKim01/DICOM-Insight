import os

# DICOM 폴더 안에 같이 존재할 수 있는 명백한 비-DICOM 파일만 제외합니다.
# 확장자가 없거나 알 수 없는 파일은 DICOM일 수 있으므로 그대로 Indexer로 보냅니다.
_SKIP_EXTENSIONS={
    ".jpg",".jpeg",".png",".gif",".bmp",".webp",".tif",".tiff",
    ".txt",".csv",".tsv",".xlsx",".xls",".doc",".docx",".pdf",
    ".json",".xml",".html",".htm",".log",".ini",".yaml",".yml",
    ".zip",".7z",".rar",".tar",".gz",
    ".exe",".dll",".bat",".cmd",".ps1",
    ".py",".pyc",".pyd",
    ".mp4",".avi",".mov",".mkv",".wmv",
    ".nii",".nrrd",".mha",".mhd"
}

def _is_candidate_filename(name):
    lower=name.lower()

    # 흔한 시스템/메타파일은 바로 제외
    if lower in {
        "thumbs.db",
        "desktop.ini",
        ".ds_store"
    }:
        return False

    _,ext=os.path.splitext(lower)

    if ext in _SKIP_EXTENSIONS:
        return False

    return True

def list_candidate_files(folder):
    result=[]
    append=result.append
    stack=[os.fspath(folder)]
    stack_append=stack.append
    stack_pop=stack.pop

    while stack:
        current=stack_pop()

        try:
            with os.scandir(current) as entries:
                for entry in entries:
                    try:
                        if entry.is_dir(follow_symlinks=False):
                            stack_append(entry.path)
                            continue

                        if not entry.is_file(follow_symlinks=False):
                            continue

                        if not _is_candidate_filename(entry.name):
                            continue

                        append(entry.path)

                    except OSError:
                        continue

        except OSError:
            continue

    return result
