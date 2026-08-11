import os
from pathlib import Path
from time import perf_counter
from PySide6.QtCore import QObject,Signal,Slot

from dicom.scanner import iter_candidate_files
from dicom.indexer import build_index_fast

class ImportWorker(QObject):
    scan_progress=Signal(int)
    indexing_started=Signal(int)
    index_progress=Signal(int,int,int)
    finished=Signal(object,object,object,str,object)
    failed=Signal(str)

    def __init__(self,items,parent=None):
        super().__init__(parent)
        self.items=[os.fspath(item) for item in items]

    @Slot()
    def run(self):
        started=perf_counter()
        try:
            candidate_files=[]
            seen=set()
            preview_path=""
            scan_started=perf_counter()

            for item in self.items:
                path=Path(item)
                if path.is_dir():
                    iterator=iter_candidate_files(str(path))
                elif path.is_file():
                    iterator=(str(path),)
                else:
                    continue

                for candidate in iterator:
                    candidate=os.fspath(candidate)
                    if candidate in seen:
                        continue
                    seen.add(candidate)
                    candidate_files.append(candidate)
                    count=len(candidate_files)
                    if count==1 or count%512==0:
                        self.scan_progress.emit(count)


            scan_elapsed=perf_counter()-scan_started
            self.scan_progress.emit(len(candidate_files))

            if not candidate_files:
                metrics={"scan":scan_elapsed,"index":0.0,"total":perf_counter()-started}
                self.finished.emit({}, {}, [], preview_path,metrics)
                return

            self.indexing_started.emit(len(candidate_files))
            index_started=perf_counter()

            def progress(current,total,dicom_count):
                self.index_progress.emit(current,total,dicom_count)

            index,info,files=build_index_fast(candidate_files,progress_callback=progress,progress_batch=2048)
            if files:
                preview_path=files[0]
            index_elapsed=perf_counter()-index_started
            metrics={"scan":scan_elapsed,"index":index_elapsed,"total":perf_counter()-started}
            self.finished.emit(index,info,files,preview_path,metrics)

        except Exception as exc:
            self.failed.emit(str(exc))
