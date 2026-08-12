import os
from collections import Counter,defaultdict
from PySide6.QtWidgets import QAbstractItemView
from PySide6.QtWidgets import QHeaderView
from pathlib import Path
from PySide6.QtCore import Signal,Qt,QItemSelectionModel
from PySide6.QtGui import QBrush,QColor,QFont
from PySide6.QtWidgets import QTreeWidget,QTreeWidgetItem,QAbstractItemView

ROLE_SERIES_PATHS=Qt.UserRole
ROLE_FILE_PATH=Qt.UserRole+1
ROLE_ITEM_TYPE=Qt.UserRole+2
ROLE_FILES_BUILT=Qt.UserRole+3
ROLE_STUDY_COLOR_INDEX=Qt.UserRole+4
ROLE_PATIENT_LABEL=Qt.UserRole+5
ROLE_SLICE_INDEX=Qt.UserRole+6

DARK_STUDY_COLORS=[
    ("#58a6ff","#9ecbff","#203a55"),
    ("#c084fc","#ddb6ff","#432b55"),
    ("#2dd4bf","#86efe1","#1f4b46"),
    ("#f59e0b","#ffd27a","#59431f"),
    ("#4ade80","#98f0b5","#244b31"),
    ("#fb7185","#ffadba","#552c34"),
    ("#22d3ee","#8be9f7","#1d4650"),
    ("#facc15","#ffe77a","#55491d"),
    ("#818cf8","#b8c0ff","#30365c"),
    ("#a3e635","#c8f178","#3b4d22"),
    ("#f472b6","#f9a8d4","#542943"),
    ("#60a5fa","#a5cffa","#253b58"),
]

LIGHT_STUDY_COLORS=[
    ("#1769aa","#3f84bd","#dceeff"),
    ("#7b2cbf","#9a5bc9","#eedfff"),
    ("#087f73","#329b90","#d9f3ef"),
    ("#a45b00","#c47718","#fff0d1"),
    ("#267a3d","#4a9560","#def2e4"),
    ("#b23a4e","#d05a6d","#ffe2e7"),
    ("#087f8c","#2c9eaa","#d9f4f7"),
    ("#8a6a00","#aa8614","#fff5c7"),
    ("#4f46b5","#6962c7","#e5e4ff"),
    ("#5f7f16","#789b29","#eef7d5"),
    ("#a12f74","#c15391","#fde3f1"),
    ("#2f5f9e","#4f7db6","#e1ebf8"),
]

def _path_key(path):
    return os.path.normcase(os.path.abspath(os.fspath(path)))

class SeriesTree(QTreeWidget):
    series_selected=Signal(list)
    file_selected=Signal(list,int)

    def __init__(self,parent=None):
        super().__init__(parent)
        self.setHeaderHidden(True)
        self.header().setStretchLastSection(False)
        self.header().setSectionResizeMode(QHeaderView.Interactive)
        self.setColumnWidth(0,520)
        self.setUniformRowHeights(True)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.setTextElideMode(Qt.ElideNone)
        self.setVerticalScrollMode(QAbstractItemView.ScrollPerPixel)
        self.setHorizontalScrollMode(QAbstractItemView.ScrollPerPixel)
        self.verticalScrollBar().setSingleStep(18)
        self.horizontalScrollBar().setSingleStep(24)
        self.setSelectionMode(QAbstractItemView.SingleSelection)
        self.active_series_item=None
        self.file_item_map={}
        self.theme="dark" if self.palette().window().color().lightness()<128 else "light"
        self.itemClicked.connect(self._on_item_clicked)
        self.itemDoubleClicked.connect(self._on_item_clicked)
        self.itemExpanded.connect(self._on_item_expanded)

    def set_theme(self,theme):
        self.theme="dark" if theme=="dark" else "light"
        self._refresh_group_colors()

    def _palette_for_index(self,color_index):
        colors=DARK_STUDY_COLORS if self.theme=="dark" else LIGHT_STUDY_COLORS
        return colors[int(color_index)%len(colors)]

    def _set_patient_style(self,item):
        font=item.font(0)
        font.setBold(True)
        item.setFont(0,font)
        item.setForeground(0,QBrush(QColor("#f2f2f2" if self.theme=="dark" else "#222222")))
        item.setBackground(0,QBrush())

    def _set_study_style(self,item):
        color_index=item.data(0,ROLE_STUDY_COLOR_INDEX) or 0
        study_color,_,_=self._palette_for_index(color_index)
        font=item.font(0)
        font.setBold(True)
        item.setFont(0,font)
        item.setForeground(0,QBrush(QColor(study_color)))
        item.setBackground(0,QBrush())

    def _set_series_style(self,item,active=False):
        color_index=item.data(0,ROLE_STUDY_COLOR_INDEX) or 0
        _,series_color,active_bg=self._palette_for_index(color_index)
        font=item.font(0)
        font.setBold(bool(active))
        item.setFont(0,font)
        item.setForeground(0,QBrush(QColor(series_color)))
        item.setBackground(0,QBrush(QColor(active_bg)) if active else QBrush())

    def _set_active_series_item(self,item):
        if self.active_series_item is item:
            if item is not None:
                self._set_series_style(item,True)
            return
        if self.active_series_item is not None:
            self._set_series_style(self.active_series_item,False)
        self.active_series_item=item
        if item is not None:
            self._set_series_style(item,True)

    def _study_series_items(self,study_item):
        stack=[study_item]
        while stack:
            parent=stack.pop()
            for i in range(parent.childCount()-1,-1,-1):
                child=parent.child(i)
                child_type=child.data(0,ROLE_ITEM_TYPE)
                if child_type=="series":
                    yield child
                elif child_type in ("folder_group","series_group"):
                    stack.append(child)

    def _set_group_style(self,item):
        color_index=item.data(0,ROLE_STUDY_COLOR_INDEX) or 0
        _,series_color,_=self._palette_for_index(color_index)
        font=item.font(0)
        font.setBold(True)
        item.setFont(0,font)
        item.setForeground(0,QBrush(QColor(series_color)))
        item.setBackground(0,QBrush())

    def _refresh_group_colors(self):
        root=self.invisibleRootItem()
        for i in range(root.childCount()):
            patient=root.child(i)
            self._set_patient_style(patient)
            for j in range(patient.childCount()):
                study=patient.child(j)
                self._set_study_style(study)
                stack=[study]
                while stack:
                    parent=stack.pop()
                    for k in range(parent.childCount()):
                        child=parent.child(k)
                        child_type=child.data(0,ROLE_ITEM_TYPE)
                        if child_type=="series":
                            self._set_series_style(child,child is self.active_series_item)
                        elif child_type in ("folder_group","series_group"):
                            self._set_group_style(child)
                            stack.append(child)

    def populate(self,index,info):
        self.clear()
        self.active_series_item=None
        self.file_item_map={}

        patient_entries=[]
        for patient_id,studies in index.items():
            patient_name=info.get(patient_id,{}).get("patient_name","")
            patient_text=patient_id if not patient_name else f"{patient_id} ({patient_name})"
            patient_entries.append((patient_id,studies,patient_text))

        for patient_index,(patient_id,studies,patient_text) in enumerate(patient_entries,1):
            patient_label=f"[Patient {patient_index}]"
            patient_text=f"{patient_label} {patient_text}"

            patient_item=QTreeWidgetItem([patient_text])
            patient_item.setData(0,ROLE_PATIENT_LABEL,patient_label)
            patient_item.setData(0,ROLE_ITEM_TYPE,"patient")
            self.addTopLevelItem(patient_item)
            self._set_patient_style(patient_item)

            for study_color_index,(study_uid,series_map) in enumerate(studies.items()):
                study_info=info.get(study_uid,{})
                date=study_info.get("study_date","")
                desc=study_info.get("study_description","")
                study_text=" - ".join(v for v in [date,desc] if v) or study_uid
                study_item=QTreeWidgetItem([study_text])
                study_item.setData(0,ROLE_ITEM_TYPE,"study")
                study_item.setData(0,ROLE_STUDY_COLOR_INDEX,study_color_index)
                patient_item.addChild(study_item)
                self._set_study_style(study_item)

                series_entries=[]
                for series_key,paths in series_map.items():
                    series_info=info.get(series_key,{})
                    series_entries.append((series_key,paths,series_info))

                def add_series_item(parent_item,series_key,paths,series_info):
                    number=series_info.get("series_number","")
                    desc=series_info.get("series_description","")
                    modality=series_info.get("modality","")
                    multi_frame_file=series_info.get("multi_frame_file","")
                    number_of_frames=int(series_info.get("number_of_frames",1) or 1)

                    label_parts=[]
                    if number:
                        label_parts.append(f"Series {number}")
                    elif modality:
                        label_parts.append(f"Series {modality}")
                    else:
                        label_parts.append("Series")

                    label_parts.append(desc if desc else "Unknown Series")
                    if multi_frame_file:
                        label_parts.append(multi_frame_file)
                        series_text=" - ".join(label_parts)+f" ({number_of_frames} frames)"
                    else:
                        series_text=" - ".join(label_parts)+f" ({len(paths)} slices)"

                    series_item=QTreeWidgetItem([series_text])
                    series_item.setData(0,ROLE_SERIES_PATHS,paths)
                    series_item.setData(0,ROLE_ITEM_TYPE,"series")
                    series_item.setData(0,ROLE_STUDY_COLOR_INDEX,study_color_index)
                    parent_item.addChild(series_item)
                    self._set_series_style(series_item,False)
                    series_item.setData(0,ROLE_FILES_BUILT,False)
                    if paths:
                        placeholder=QTreeWidgetItem([""])
                        placeholder.setData(0,ROLE_ITEM_TYPE,"placeholder")
                        series_item.addChild(placeholder)
                    return series_item

                def make_group(parent_item,text,item_type):
                    item=QTreeWidgetItem([text])
                    item.setData(0,ROLE_ITEM_TYPE,item_type)
                    item.setData(0,ROLE_STUDY_COLOR_INDEX,study_color_index)
                    parent_item.addChild(item)
                    self._set_group_style(item)
                    return item

                # Separate ordinary single-frame Series from multi-frame files.
                single_entries=[]
                multi_by_uid=defaultdict(list)
                for series_key,paths,series_info in series_entries:
                    raw_uid=str(series_info.get("series_uid",series_key))
                    if series_info.get("multi_frame_file",""):
                        multi_by_uid[raw_uid].append((series_key,paths,series_info))
                    else:
                        single_entries.append((series_key,paths,series_info))

                # Single-frame: normally keep the simple Study -> Series layout.
                # Only when the SAME SeriesInstanceUID exists in different folders
                # do we insert Folder nodes for that conflicting Series UID.
                single_by_uid=defaultdict(list)
                for entry in single_entries:
                    raw_uid=str(entry[2].get("series_uid",entry[0]))
                    single_by_uid[raw_uid].append(entry)

                for raw_uid,entries in single_by_uid.items():
                    folders={str(e[2].get("source_root","") or "") for e in entries}
                    if len(folders)<=1:
                        for series_key,paths,series_info in entries:
                            add_series_item(study_item,series_key,paths,series_info)
                        continue

                    # UID collision across physical folders: show only the needed
                    # folder layer instead of adding Folder nodes to every Series.
                    by_folder=defaultdict(list)
                    for entry in entries:
                        by_folder[str(entry[2].get("source_root","") or "")].append(entry)
                    used_names=defaultdict(int)
                    for source_root,folder_series in by_folder.items():
                        folder_name=Path(source_root).name if source_root else "Unknown Folder"
                        used_names[folder_name]+=1
                        suffix=f" [{used_names[folder_name]}]" if used_names[folder_name]>1 else ""
                        folder_item=make_group(study_item,f"Folder - {folder_name}{suffix}","folder_group")
                        if source_root:
                            folder_item.setToolTip(0,source_root)
                        for series_key,paths,series_info in folder_series:
                            add_series_item(folder_item,series_key,paths,series_info)

                # Multi-frame: keep a compact Series group. Each physical DICOM
                # remains its own 81-frame (etc.) viewer Series. If those files are
                # themselves split across folders, add Folder nodes only inside the
                # multi-frame Series group.
                for raw_uid,entries in multi_by_uid.items():
                    if not entries:
                        continue
                    _,_,first_info=entries[0]
                    number=first_info.get("series_number","")
                    desc=first_info.get("series_description","")
                    modality=first_info.get("modality","")
                    if number:
                        group_label=f"Series {number}"
                    elif modality:
                        group_label=f"Series {modality}"
                    else:
                        group_label="Series"
                    group_label+=" - "+(desc if desc else "Unknown Series")
                    if len(entries)>1:
                        group_label+=f" ({len(entries)} files)"

                    if len(entries)==1:
                        series_key,paths,series_info=entries[0]
                        add_series_item(study_item,series_key,paths,series_info)
                        continue

                    group_item=make_group(study_item,group_label,"series_group")
                    by_folder=defaultdict(list)
                    for entry in entries:
                        by_folder[str(entry[2].get("source_root","") or "")].append(entry)

                    if len(by_folder)<=1:
                        for series_key,paths,series_info in entries:
                            add_series_item(group_item,series_key,paths,series_info)
                    else:
                        used_names=defaultdict(int)
                        for source_root,folder_series in by_folder.items():
                            folder_name=Path(source_root).name if source_root else "Unknown Folder"
                            used_names[folder_name]+=1
                            suffix=f" [{used_names[folder_name]}]" if used_names[folder_name]>1 else ""
                            folder_item=make_group(group_item,f"Folder - {folder_name}{suffix}","folder_group")
                            if source_root:
                                folder_item.setToolTip(0,source_root)
                            for series_key,paths,series_info in folder_series:
                                add_series_item(folder_item,series_key,paths,series_info)

    def _ensure_file_items(self,series_item):
        if series_item is None:
            return

        if series_item.data(0,ROLE_FILES_BUILT):
            return

        paths=series_item.data(0,ROLE_SERIES_PATHS) or []

        series_item.takeChildren()

        path_counts=Counter(str(path) for path in paths)
        path_seen=defaultdict(int)
        self.setUpdatesEnabled(False)
        try:
            for idx,path in enumerate(paths,1):
                path=str(path)
                path_seen[path]+=1
                frame_count=path_counts[path]
                if frame_count>1:
                    label=f"#{idx} - {Path(path).name} [Frame {path_seen[path]}/{frame_count}]"
                else:
                    label=f"#{idx} - {Path(path).name}"
                file_item=QTreeWidgetItem([label])
                file_item.setData(0,ROLE_SERIES_PATHS,paths)
                file_item.setData(0,ROLE_FILE_PATH,path)
                file_item.setData(0,ROLE_SLICE_INDEX,idx-1)
                file_item.setData(0,ROLE_ITEM_TYPE,"file")
                series_item.addChild(file_item)
                self.file_item_map[(_path_key(path),idx-1)]=file_item
        finally:
            series_item.setData(0,ROLE_FILES_BUILT,True)
            self.setUpdatesEnabled(True)

    def _on_item_expanded(self,item):
        if item.data(0,ROLE_ITEM_TYPE)=="series":
            self._ensure_file_items(item)

    def _series_item_from_item(self,item):
        if item is None:
            return None

        item_type=item.data(0,ROLE_ITEM_TYPE)

        if item_type=="series":
            return item

        if item_type=="file":
            return item.parent()

        return None

    def _on_item_clicked(self,item,column=0):
        series_item=self._series_item_from_item(item)
        if series_item is None:
            return

        self._set_active_series_item(series_item)
        paths=series_item.data(0,ROLE_SERIES_PATHS)

        if not paths:
            return

        item_type=item.data(0,ROLE_ITEM_TYPE)

        if item_type=="file":
            slice_index=item.data(0,ROLE_SLICE_INDEX)
            if slice_index is not None:
                self.file_selected.emit(paths,int(slice_index))
            return

        self.series_selected.emit(paths)

    def select_first_series(self):
        root=self.invisibleRootItem()

        for i in range(root.childCount()):
            patient=root.child(i)

            for j in range(patient.childCount()):
                study=patient.child(j)

                for series in self._study_series_items(study):
                    paths=series.data(0,ROLE_SERIES_PATHS)
                    if paths:
                        self._set_active_series_item(series)
                        self.setCurrentItem(series)
                        return paths

        return None

    def set_active_series_by_paths(self,paths):
        if not paths:
            return

        target=list(paths)
        root=self.invisibleRootItem()

        for i in range(root.childCount()):
            patient=root.child(i)

            for j in range(patient.childCount()):
                study=patient.child(j)

                for series in self._study_series_items(study):
                    series_paths=series.data(0,ROLE_SERIES_PATHS)
                    if series_paths and list(series_paths)==target:
                        self._set_active_series_item(series)
                        return

    def expand_series_by_paths(self,paths):
        if not paths:
            return

        target=list(paths)
        root=self.invisibleRootItem()

        for i in range(root.childCount()):
            patient=root.child(i)

            for j in range(patient.childCount()):
                study=patient.child(j)

                for series in self._study_series_items(study):
                    series_paths=series.data(0,ROLE_SERIES_PATHS)
                    if not series_paths or list(series_paths)!=target:
                        continue
                    self._ensure_file_items(series)
                    patient.setExpanded(True)
                    study.setExpanded(True)
                    parent=series.parent()
                    while parent is not None and parent is not study:
                        if parent.data(0,ROLE_ITEM_TYPE) in ("folder_group","series_group"):
                            parent.setExpanded(True)
                        parent=parent.parent()
                    series.setExpanded(True)
                    return

    def get_overlay_context_by_paths(self,paths):
        if not paths:
            return {}

        target=list(paths)
        root=self.invisibleRootItem()

        for i in range(root.childCount()):
            patient=root.child(i)
            patient_label=patient.data(0,ROLE_PATIENT_LABEL) or patient.text(0)

            for j in range(patient.childCount()):
                study=patient.child(j)
                color_index=study.data(0,ROLE_STUDY_COLOR_INDEX) or 0
                study_color,series_color,_=self._palette_for_index(color_index)

                for series in self._study_series_items(study):
                    series_paths=series.data(0,ROLE_SERIES_PATHS)
                    if series_paths and list(series_paths)==target:
                        return {
                            "patient_label":str(patient_label),
                            "study_color":study_color,
                            "series_color":series_color,
                        }

        return {}

    def _clear_slice_highlight(self,series):
        if series is None:
            return

        for i in range(series.childCount()):
            item=series.child(i)
            font=item.font(0)
            font.setBold(False)
            item.setFont(0,font)
            item.setForeground(0,QBrush())
            item.setBackground(0,QBrush())

    def select_slice(self,index):
        series=self.active_series_item
        if series is None or not series.data(0,ROLE_FILES_BUILT):
            return
        if index<0 or index>=series.childCount():
            return
        matched_item=series.child(index)
        self._set_active_series_item(series)
        self._clear_slice_highlight(series)
        font=matched_item.font(0)
        font.setBold(True)
        matched_item.setFont(0,font)
        self.blockSignals(True)
        try:
            self.clearSelection()
            model_index=self.indexFromItem(matched_item)
            self.selectionModel().setCurrentIndex(
                model_index,QItemSelectionModel.ClearAndSelect|QItemSelectionModel.Rows
            )
            self.setCurrentItem(matched_item)
            matched_item.setSelected(True)
            parent=matched_item.parent()
            while parent is not None:
                if not parent.isExpanded():
                    parent.setExpanded(True)
                parent=parent.parent()
            rect=self.visualItemRect(matched_item)
            viewport_rect=self.viewport().rect()
            if not viewport_rect.contains(rect.topLeft()) or not viewport_rect.contains(rect.bottomRight()):
                self.scrollToItem(matched_item,QAbstractItemView.PositionAtCenter)
        finally:
            self.blockSignals(False)

    def select_file_path(self,file_path):
        if not file_path:
            return

        target=_path_key(file_path)
        matched_item=self.file_item_map.get(target)

        if matched_item is None:
            return

        matched_series=matched_item.parent()
        self._set_active_series_item(matched_series)

        # 이전 Bold 제거: 현재 series의 자식만 확인하므로 매우 가벼움
        self._clear_slice_highlight(matched_series)

        font=matched_item.font(0)
        font.setBold(True)
        matched_item.setFont(0,font)

        self.blockSignals(True)
        self.clearSelection()

        index=self.indexFromItem(matched_item)
        self.selectionModel().setCurrentIndex(
            index,
            QItemSelectionModel.ClearAndSelect|QItemSelectionModel.Rows
        )
        self.setCurrentItem(matched_item)
        matched_item.setSelected(True)

        parent=matched_item.parent()
        while parent is not None:
            if not parent.isExpanded():
                parent.setExpanded(True)
            parent=parent.parent()

        # 현재 항목이 화면 밖에 있을 때만 스크롤
        rect=self.visualItemRect(matched_item)
        viewport_rect=self.viewport().rect()
        if not viewport_rect.contains(rect.topLeft()) or not viewport_rect.contains(rect.bottomRight()):
            self.scrollToItem(
                matched_item,
                QAbstractItemView.PositionAtCenter
            )

        self.blockSignals(False)
