from dicom.native_indexer import build_native_index,read_native_header


def build_index_fast(paths,progress_callback=None,max_workers=None,progress_batch=1024,source_map=None):
    return build_native_index(
        paths,
        progress_callback=progress_callback,
        max_workers=max_workers,
        progress_batch=progress_batch,
        source_map=source_map
    )


def read_header_fast(path):
    return read_native_header(path)
