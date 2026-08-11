import os
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
    file_selected=Signal(list,str)

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

    def _refresh_group_colors(self):
        root=self.invisibleRootItem()
        for i in range(root.childCount()):
            patient=root.child(i)
            self._set_patient_style(patient)
            for j in range(patient.childCount()):
                study=patient.child(j)
                self._set_study_style(study)
                for k in range(study.childCount()):
                    series=study.child(k)
                    if series.data(0,ROLE_ITEM_TYPE)=="series":
                        self._set_series_style(series,series is self.active_series_item)

    def populate(self,index,info):
        self.clear()
        self.active_series_item=None
        self.file_item_map={}

        for patient_id,studies in index.items():
            patient_name=info.get(patient_id,{}).get("patient_name","")
            patient_text=patient_id if not patient_name else f"{patient_id} ({patient_name})"
            patient_item=QTreeWidgetItem([patient_text])
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

                for series_uid,paths in series_map.items():
                    series_info=info.get(series_uid,{})
                    number=series_info.get("series_number","")
                    desc=series_info.get("series_description","")
                    modality=series_info.get("modality","")

                    label_parts=[]
                    if number:
                        label_parts.append(f"Series {number}")
                    elif modality:
                        label_parts.append(f"Series {modality}")
                    else:
                        label_parts.append("Series")

                    label_parts.append(desc if desc else "Unknown Series")
                    series_text=" - ".join(label_parts)+f" ({len(paths)} slices)"

                    series_item=QTreeWidgetItem([series_text])
                    series_item.setData(0,ROLE_SERIES_PATHS,paths)
                    series_item.setData(0,ROLE_ITEM_TYPE,"series")
                    series_item.setData(0,ROLE_STUDY_COLOR_INDEX,study_color_index)
                    study_item.addChild(series_item)
                    self._set_series_style(series_item,False)

                    series_item.setData(0,ROLE_FILES_BUILT,False)

                    # Thousands of file QTreeWidgetItems are expensive.
                    # Build children only when this Series is opened/selected.
                    if paths:
                        placeholder=QTreeWidgetItem([""])
                        placeholder.setData(0,ROLE_ITEM_TYPE,"placeholder")
                        series_item.addChild(placeholder)

    def _ensure_file_items(self,series_item):
        if series_item is None:
            return

        if series_item.data(0,ROLE_FILES_BUILT):
            return

        paths=series_item.data(0,ROLE_SERIES_PATHS) or []

        series_item.takeChildren()

        self.setUpdatesEnabled(False)
        try:
            for idx,path in enumerate(paths,1):
                file_item=QTreeWidgetItem(
                    [f"#{idx} - {Path(path).name}"]
                )
                file_item.setData(0,ROLE_SERIES_PATHS,paths)
                file_item.setData(0,ROLE_FILE_PATH,path)
                file_item.setData(0,ROLE_ITEM_TYPE,"file")
                series_item.addChild(file_item)

                self.file_item_map[_path_key(path)]=file_item
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
            file_path=item.data(0,ROLE_FILE_PATH)
            if file_path:
                self.file_selected.emit(paths,str(file_path))
            return

        self.series_selected.emit(paths)

    def select_first_series(self):
        root=self.invisibleRootItem()

        for i in range(root.childCount()):
            patient=root.child(i)

            for j in range(patient.childCount()):
                study=patient.child(j)

                for k in range(study.childCount()):
                    series=study.child(k)
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

                for k in range(study.childCount()):
                    series=study.child(k)
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

                for k in range(study.childCount()):
                    series=study.child(k)
                    series_paths=series.data(0,ROLE_SERIES_PATHS)

                    if not series_paths or list(series_paths)!=target:
                        continue

                    self._ensure_file_items(series)
                    patient.setExpanded(True)
                    study.setExpanded(True)
                    series.setExpanded(True)
                    return

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

        file_item=series.child(index)
        file_path=file_item.data(0,ROLE_FILE_PATH)

        if file_path:
            self.select_file_path(file_path)

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
