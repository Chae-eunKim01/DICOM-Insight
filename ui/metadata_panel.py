from PySide6.QtWidgets import QHBoxLayout
from PySide6.QtWidgets import QHeaderView
from PySide6.QtWidgets import QAbstractItemView
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QWidget,QVBoxLayout,QHBoxLayout,QTableWidget,QTableWidgetItem,
    QHeaderView,QLineEdit,QCheckBox,QLabel
)
from dicom.metadata import extract_metadata,extract_elements

class MetadataPanel(QWidget):
    def __init__(self,parent=None):
        super().__init__(parent)

        self.current_ds=None
        self._last_mode_all=None

        layout=QVBoxLayout(self)
        layout.setContentsMargins(0,0,0,0)
        layout.setSpacing(6)

        search_row=QHBoxLayout()
        search_row.addWidget(QLabel("Search"))
        self.search=QLineEdit()
        self.search.setPlaceholderText("tag, name, value")
        search_row.addWidget(self.search)
        layout.addLayout(search_row)

        self.show_all=QCheckBox("Show all tags")
        self.tag_count_label=QLabel("Total Tags: 0")
        show_all_row=QHBoxLayout()
        show_all_row.setContentsMargins(0,0,0,0)
        show_all_row.setSpacing(10)
        show_all_row.addWidget(self.show_all)
        show_all_row.addWidget(self.tag_count_label)
        show_all_row.addStretch()
        layout.addLayout(show_all_row)


        self.table=QTableWidget(0,3)
        self.table.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)

        self.table.setTextElideMode(Qt.ElideNone)
        self.table.setVerticalScrollMode(QAbstractItemView.ScrollPerPixel)
        self.table.setHorizontalScrollMode(QAbstractItemView.ScrollPerPixel)
        self.table.verticalScrollBar().setSingleStep(18)
        self.table.horizontalScrollBar().setSingleStep(24)
        self.table.setHorizontalHeaderLabels(["(Group, Element)","Description","Value"])
        header=self.table.horizontalHeader()
        header.setStretchLastSection(False)
        header.setSectionResizeMode(0,QHeaderView.Fixed)
        header.setSectionResizeMode(1,QHeaderView.Fixed)
        header.setSectionResizeMode(2,QHeaderView.Fixed)

        # Header와 row가 정확히 같은 column geometry를 사용
        self.table.setColumnWidth(0,120)
        self.table.setColumnWidth(1,165)
        self.table.setColumnWidth(2,420)

        # Header text도 row text와 동일하게 왼쪽 정렬
        header.setDefaultAlignment(Qt.AlignLeft|Qt.AlignVCenter)
        self.table.verticalHeader().setVisible(False)
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        self.table.setAlternatingRowColors(True)

        layout.addWidget(self.table,1)

        self.search.textChanged.connect(self._filter)
        self.show_all.toggled.connect(self._refresh)

    def _align_row_items(self,row):
        for col in range(self.table.columnCount()):
            item=self.table.item(row,col)
            if item is not None:
                item.setTextAlignment(Qt.AlignLeft|Qt.AlignVCenter)

    def _update_tag_count(self,ds):
        if ds is None:
            count=0
        else:
            try:
                count=sum(1 for _ in ds.iterall())
            except Exception:
                try:
                    count=len(ds)
                except Exception:
                    count=0

        self.tag_count_label.setText(f"Total Tags: {count}")

    def set_dataset(self,ds):
        self._update_tag_count(ds)
        self.current_ds=ds
        self._refresh()

    def _refresh(self):
        try:
            show_all=self.show_all.isChecked()

            if self.current_ds is None:
                rows=[]
            elif show_all:
                rows=[
                    (tag_id,description,value)
                    for tag_id,description,vr,value in extract_elements(self.current_ds)
                ]
            else:
                rows=extract_metadata(self.current_ds)

            # 모드가 같고 행 수가 같으면 기존 QTableWidgetItem을 재사용
            reuse=(
                self._last_mode_all==show_all
                and self.table.rowCount()==len(rows)
            )

            if not reuse:
                self.table.setUpdatesEnabled(False)
                self.table.setRowCount(len(rows))
                for r,row in enumerate(rows):
                    for c,value in enumerate(row):
                        self.table.setItem(r,c,QTableWidgetItem(str(value)))
                self.table.setUpdatesEnabled(True)
            else:
                self.table.setUpdatesEnabled(False)
                for r,row in enumerate(rows):
                    for c,value in enumerate(row):
                        item=self.table.item(r,c)
                        text=str(value)
                        if item is None:
                            self.table.setItem(r,c,QTableWidgetItem(text))
                        elif item.text()!=text:
                            item.setText(text)
                self.table.setUpdatesEnabled(True)

            self._last_mode_all=show_all
            self._filter(self.search.text())

        except Exception as e:
            self.table.setUpdatesEnabled(True)
            self.table.setRowCount(1)
            self.table.setItem(0,0,QTableWidgetItem(""))
            self.table.setItem(0,1,QTableWidgetItem("Metadata read warning"))
            self.table.setItem(0,2,QTableWidgetItem(str(e)))

    def _filter(self,text):
        text=text.strip().lower()

        for row in range(self.table.rowCount()):
            values=[]
            for col in range(self.table.columnCount()):
                item=self.table.item(row,col)
                values.append(item.text().lower() if item else "")

            visible=not text or any(text in value for value in values)
            self.table.setRowHidden(row,not visible)
