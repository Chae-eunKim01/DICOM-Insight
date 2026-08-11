import os
from pathlib import Path
from time import perf_counter
from PySide6.QtCore import Qt,QSettings,QTimer,QThread
from PySide6.QtGui import QAction,QActionGroup,QShortcut,QKeySequence
from PySide6.QtWidgets import (
    QApplication,QMainWindow,QFileDialog,QSplitter,QWidget,QVBoxLayout,QHBoxLayout,
    QLabel,QStatusBar,QMessageBox,QPushButton,QCheckBox,QFrame,QMenu,QProgressBar,QDialog,QDialogButtonBox,QFormLayout,QDoubleSpinBox,QScrollBar
)
from ui.series_tree import SeriesTree
from ui.metadata_panel import MetadataPanel
from ui.theme import LIGHT_STYLE,DARK_STYLE
from viewer.viewer2d import DicomViewer2D
from viewer.viewer3d import Viewer3DDialog
from dicom.volume_builder import inspect_series_resolution,build_volume_from_paths
from dicom.import_worker import ImportWorker
from dicom.loader import load_series

def _path_key(path):
    return os.path.normcase(os.path.abspath(os.fspath(path)))
from dicom.pixel_decoder import is_color_dataset
from utils.constants import APP_NAME

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle(APP_NAME)
        self.resize(1500,900)
        self.setAcceptDrops(True)

        self.current_paths=[]
        self.current_folder=""
        self.settings=QSettings("PythonDICOMViewer","PythonDICOMViewer")
        self.progress_started_at=None
        self._last_progress_ui_at=0.0
        self._pending_slice_index=None
        self._import_thread=None
        self._import_worker=None
        self._import_preview_path=""

        self.slice_scroll_timer=QTimer(self)
        self.slice_scroll_timer.setSingleShot(True)
        self.slice_scroll_timer.setInterval(35)
        self.slice_scroll_timer.timeout.connect(
            self._apply_pending_slice_scroll
        )

        self._build_ui()
        self._create_menu()
        self._connect_signals()
        self._setup_slice_shortcuts()
        self._load_theme()

    def _build_ui(self):
        container=QWidget()
        root_layout=QVBoxLayout(container)
        root_layout.setContentsMargins(8,8,8,8)
        root_layout.setSpacing(6)

        top_buttons=QHBoxLayout()
        self.open_dicom_btn=QPushButton("Open DICOM")
        self.open_folder_btn=QPushButton("Open Folder")
        self.view_btn=QPushButton("View")
        self.reset_wl_btn=QPushButton("Reset View")

        top_buttons.addWidget(self.open_dicom_btn)
        top_buttons.addWidget(self.open_folder_btn)
        top_buttons.addWidget(self.view_btn)
        top_buttons.addWidget(self.reset_wl_btn)
        top_buttons.addStretch()
        root_layout.addLayout(top_buttons)

        self.path_label=QLabel("Drag && Drop DICOM file(s) or folder here")
        self.path_label.setTextInteractionFlags(Qt.TextSelectableByMouse)
        root_layout.addWidget(self.path_label)

        self.progress_text=QLabel("")
        self.progress_text.setVisible(False)
        root_layout.addWidget(self.progress_text)

        self.progress_bar=QProgressBar()
        self.progress_bar.setRange(0,100)
        self.progress_bar.setValue(0)
        self.progress_bar.setTextVisible(False)
        self.progress_bar.setFixedHeight(18)
        self.progress_bar.setVisible(False)
        root_layout.addWidget(self.progress_bar)


        line=QFrame()
        line.setFrameShape(QFrame.HLine)
        line.setFrameShadow(QFrame.Sunken)
        root_layout.addWidget(line)

        self.series_tree=SeriesTree()
        self.viewer=DicomViewer2D()

        self.slice_scroll=QScrollBar(Qt.Vertical)
        self.slice_scroll.setRange(0,0)
        self.slice_scroll.setSingleStep(1)
        self.slice_scroll.setPageStep(10)
        self.slice_scroll.setTracking(True)
        self.slice_scroll.setToolTip("Series Slice")
        self.slice_scroll.setFixedWidth(10)

        self.metadata=MetadataPanel()

        left=QWidget()
        left_layout=QVBoxLayout(left)
        left_layout.setContentsMargins(4,4,4,4)
        left_layout.setSpacing(5)

        self.left_title=QLabel("DICOM Tree")
        self.left_title.setStyleSheet("font-size:18px;")
        left_layout.addWidget(self.left_title)

        self.expand_all_checkbox=QCheckBox("Expand all by default")
        self.expand_all_checkbox.setChecked(False)
        left_layout.addWidget(self.expand_all_checkbox)

        self.file_count_label=QLabel("0 DICOM files")
        left_layout.addWidget(self.file_count_label)
        left_layout.addWidget(self.series_tree)

        right=QWidget()
        right_layout=QVBoxLayout(right)
        right_layout.setContentsMargins(6,4,4,4)
        right_layout.setSpacing(5)

        self.right_title=QLabel("DICOM Tags")
        self.right_title.setStyleSheet("font-size:18px;")
        right_layout.addWidget(self.right_title)
        right_layout.addWidget(self.metadata)

        viewer_container=QWidget()
        viewer_layout=QHBoxLayout(viewer_container)
        viewer_layout.setContentsMargins(0,0,0,0)
        viewer_layout.setSpacing(0)
        viewer_layout.addWidget(self.viewer,1)
        viewer_layout.addWidget(self.slice_scroll)

        splitter=QSplitter(Qt.Horizontal)
        splitter.addWidget(left)
        splitter.addWidget(viewer_container)
        splitter.addWidget(right)
        splitter.setSizes([440,820,330])

        root_layout.addWidget(splitter,1)
        self.setCentralWidget(container)

        status=QStatusBar()
        self.slice_label=QLabel("Slice: -")
        status.addPermanentWidget(self.slice_label)
        self.setStatusBar(status)

    def _create_menu(self):
        self.view_menu=QMenu(self)
        self.view_menu.setMinimumWidth(180)
        theme_menu=self.view_menu.addMenu("Theme")
        theme_menu.setMinimumWidth(150)

        self.light_action=QAction("Light",self)
        self.light_action.setCheckable(True)
        self.dark_action=QAction("Dark",self)
        self.dark_action.setCheckable(True)

        group=QActionGroup(self)
        group.setExclusive(True)
        group.addAction(self.light_action)
        group.addAction(self.dark_action)

        theme_menu.addAction(self.light_action)
        theme_menu.addAction(self.dark_action)

        self.view_menu.addSeparator()
        preset_menu=self.view_menu.addMenu("Window Preset")
        preset_menu.setMinimumWidth(190)

        self.window_presets=[
            ("Default","0",None,None,False),
            ("Full Dynamic","1",None,None,True),
            ("Skull","2",95,25,False),
            ("Lung","3",1600,-400,False),
            ("Abdomen","4",400,10,False),
            ("Mediastinum","5",400,10,False),
            ("Bone","6",2500,300,False),
            ("Spine","7",300,20,False),
            ("Postmyelo","8",1000,200,False),
            ("Felsenbein","9",4000,500,False)
        ]

        for name,shortcut,width,level,full_dynamic in self.window_presets:
            action=QAction(name,self)
            action.setShortcut(shortcut)
            action.setShortcutVisibleInContextMenu(True)
            action.triggered.connect(
                lambda checked=False,n=name,w=width,l=level,f=full_dynamic:
                self.apply_window_preset(n,w,l,f)
            )
            preset_menu.addAction(action)

        preset_menu.addSeparator()
        edit_windowing_action=QAction("Edit Windowing...",self)
        edit_windowing_action.triggered.connect(self.open_edit_windowing)
        preset_menu.addAction(edit_windowing_action)

        self.view_menu.addSeparator()
        rotate_menu=self.view_menu.addMenu("Rotate")
        rotate_menu.setMinimumWidth(190)

        flip_horizontal_action=QAction("Flip Horizontal",self)
        flip_horizontal_action.triggered.connect(
            self.viewer.flip_image_horizontal
        )
        rotate_menu.addAction(flip_horizontal_action)

        flip_vertical_action=QAction("Flip Vertical",self)
        flip_vertical_action.triggered.connect(
            self.viewer.flip_image_vertical
        )
        rotate_menu.addAction(flip_vertical_action)

        rotate_menu.addSeparator()

        rotate_left_action=QAction("Rotate 90 Left",self)
        rotate_left_action.triggered.connect(
            self.viewer.rotate_image_left
        )
        rotate_menu.addAction(rotate_left_action)

        rotate_right_action=QAction("Rotate 90 Right",self)
        rotate_right_action.triggered.connect(
            self.viewer.rotate_image_right
        )
        rotate_menu.addAction(rotate_right_action)

        rotate_menu.addSeparator()

        restore_orientation_action=QAction("Restore Orientation",self)
        restore_orientation_action.triggered.connect(
            self.viewer.restore_orientation
        )
        rotate_menu.addAction(restore_orientation_action)

        self.view_menu.addSeparator()
        menu_3d=self.view_menu.addMenu("3D")
        menu_3d.setMinimumWidth(190)

        mpr_action=QAction("MPR",self)
        mpr_action.triggered.connect(
            lambda:self.open_3d_viewer("MPR")
        )
        menu_3d.addAction(mpr_action)

        mip_action=QAction("MIP",self)
        mip_action.triggered.connect(
            lambda:self.open_3d_viewer("MIP")
        )
        menu_3d.addAction(mip_action)

        volume_action=QAction("Volume Rendering",self)
        volume_action.triggered.connect(
            lambda:self.open_3d_viewer("Volume Rendering")
        )
        menu_3d.addAction(volume_action)

        self.view_btn.setMenu(self.view_menu)

        self.light_action.triggered.connect(lambda:self.apply_theme("light"))
        self.dark_action.triggered.connect(lambda:self.apply_theme("dark"))

    def _connect_signals(self):
        self.open_dicom_btn.clicked.connect(self.open_dicom)
        self.open_folder_btn.clicked.connect(self.open_folder)
        self.reset_wl_btn.clicked.connect(self.viewer.reset_view)

        self.series_tree.series_selected.connect(self.load_series)
        self.series_tree.file_selected.connect(self._on_tree_file_selected)
        self.viewer.slice_changed.connect(self._on_slice_changed)
        self.slice_scroll.valueChanged.connect(
            self._on_slice_scroll_changed
        )
        self.slice_scroll.sliderReleased.connect(
            self._apply_pending_slice_scroll
        )
        self.viewer.window_changed.connect(self._on_window_changed)
        self.viewer.current_file_changed.connect(
            self.series_tree.select_file_path
        )

    def _setup_slice_shortcuts(self):
        self.slice_up_shortcut=QShortcut(QKeySequence(Qt.Key_Up),self)
        self.slice_down_shortcut=QShortcut(QKeySequence(Qt.Key_Down),self)
        self.slice_up_shortcut.setContext(Qt.WindowShortcut)
        self.slice_down_shortcut.setContext(Qt.WindowShortcut)
        self.slice_up_shortcut.activated.connect(lambda:self._change_slice_by_keyboard(-1))
        self.slice_down_shortcut.activated.connect(lambda:self._change_slice_by_keyboard(1))

    def _change_slice_by_keyboard(self,step):
        if not self.viewer.series_paths:
            return
        target=self.viewer.index+int(step)
        target=max(0,min(target,len(self.viewer.series_paths)-1))
        if target!=self.viewer.index:
            self.viewer.set_slice(target)

    def _load_theme(self):
        theme=self.settings.value("theme","light")
        if theme not in ("light","dark"):
            theme="light"
        self.apply_theme(theme,save=False)

    def apply_theme(self,theme,save=True):
        if theme=="dark":
            self.setStyleSheet(DARK_STYLE)
            self.dark_action.setChecked(True)
            self.light_action.setChecked(False)
            self.viewer.setBackgroundBrush(Qt.black)
        else:
            self.setStyleSheet(LIGHT_STYLE)
            self.light_action.setChecked(True)
            self.dark_action.setChecked(False)
            self.viewer.setBackgroundBrush(Qt.black)

        self.left_title.setStyleSheet("font-size:18px;")
        self.right_title.setStyleSheet("font-size:18px;")
        self.series_tree.set_theme(theme)

        if save:
            self.settings.setValue("theme",theme)

    def _start_progress(self,text):
        self.progress_started_at=perf_counter()
        self._last_progress_ui_at=0.0
        self.progress_text.setText(text)
        self.progress_text.setVisible(True)
        self.progress_bar.setValue(0)
        self.progress_bar.setVisible(True)
        QApplication.processEvents()

    def _format_eta(self,current,total):
        if not self.progress_started_at or current<=0 or total<=0:
            return "--"
        elapsed=perf_counter()-self.progress_started_at
        rate=current/elapsed if elapsed>0 else 0
        remaining=(total-current)/rate if rate>0 else 0
        if remaining<60:
            return f"{remaining:.0f}s"
        minutes=int(remaining//60)
        seconds=int(remaining%60)
        return f"{minutes}m {seconds:02d}s"

    def _update_progress(self,current,total,text,extra=""):
        now=perf_counter()

        # QApplication.processEvents() for every DICOM can dominate the
        # import time. Refresh at most ~12 times per second, except at 100%.
        if (
            current<total
            and self._last_progress_ui_at
            and now-self._last_progress_ui_at<0.12
        ):
            return

        self._last_progress_ui_at=now

        if total<=0:
            percent=0
        else:
            percent=int(current/total*100)

        eta=self._format_eta(current,total)
        suffix=f" | {extra}" if extra else ""

        self.progress_text.setText(
            f"{text} {current} / {total} | "
            f"{percent}%{suffix} | ETA {eta}"
        )
        self.progress_bar.setValue(percent)

        QApplication.processEvents()

    def _finish_progress(self,text="Ready"):
        self.progress_bar.setValue(100)
        self.progress_text.setText(text)
        QApplication.processEvents()

        # 완료 표시를 잠시 남긴 뒤 일반 화면으로 복귀
        self.progress_bar.setVisible(False)
        self.progress_text.setVisible(False)
        self.progress_started_at=None

    def open_edit_windowing(self):
        ds=self.viewer.current_dataset()

        if ds is None:
            self.statusBar().showMessage("No DICOM image loaded",3000)
            return

        dialog=QDialog(self)
        dialog.setWindowTitle("Edit Windowing")
        dialog.setModal(True)
        dialog.setMinimumWidth(280)

        layout=QFormLayout(dialog)

        level_spin=QDoubleSpinBox()
        level_spin.setRange(-100000.0,100000.0)
        level_spin.setDecimals(1)
        level_spin.setSingleStep(1.0)
        level_spin.setValue(float(self.viewer.window_level))

        width_spin=QDoubleSpinBox()
        width_spin.setRange(1.0,200000.0)
        width_spin.setDecimals(1)
        width_spin.setSingleStep(1.0)
        width_spin.setValue(float(self.viewer.window_width))

        layout.addRow("Window Level:",level_spin)
        layout.addRow("Window Width:",width_spin)

        buttons=QDialogButtonBox(
            QDialogButtonBox.Ok|QDialogButtonBox.Cancel
        )
        buttons.accepted.connect(dialog.accept)
        buttons.rejected.connect(dialog.reject)
        layout.addRow(buttons)

        if dialog.exec()==QDialog.Accepted:
            self.viewer.set_window_preset(
                width=width_spin.value(),
                level=level_spin.value()
            )
            self.statusBar().showMessage(
                f"Custom Window: WL {level_spin.value():.1f} / "
                f"WW {width_spin.value():.1f}",
                3000
            )

    def apply_window_preset(self,name,width,level,full_dynamic=False):
        ds=self.viewer.current_dataset()

        if ds is None:
            self.statusBar().showMessage("No DICOM image loaded",3000)
            return

        if name=="Default":
            self.viewer.reset_window_level()
        else:
            self.viewer.set_window_preset(
                width=width,
                level=level,
                full_dynamic=full_dynamic
            )

        self.statusBar().showMessage(
            f"Window Preset: {name}",
            2500
        )

    def open_3d_viewer(self,mode):
        paths=list(getattr(self.viewer,"series_paths",[]) or [])
        if not paths:
            QMessageBox.information(self,"3D Viewer","먼저 DICOM Series를 불러와 주세요.")
            return

        cache_key=tuple(paths)
        volume_info=getattr(self,"_volume_cache_info",None)
        if getattr(self,"_volume_cache_key",None)!=cache_key:
            volume_info=None

        if volume_info is None:
            self._start_progress("Preparing 3D")
            started=perf_counter()

            def load_cb(current,total):
                self._update_progress(current,total,"Preparing 3D",f"{current} / {total}")

            try:
                volume_info=build_volume_from_paths(paths,progress_callback=load_cb)
            except Exception as e:
                self._finish_progress()
                QMessageBox.critical(self,"3D Viewer Error",str(e))
                return

            elapsed=perf_counter()-started
            self._volume_cache_key=cache_key
            self._volume_cache_info=volume_info
            self._finish_progress()
            backend=volume_info.get("backend","3D")
            self.statusBar().showMessage(
                f"3D volume ready | {len(paths)} slices | {elapsed:.2f}s | {backend}",
                7000
            )

        resolution=inspect_series_resolution(volume_info)
        low_resolution=resolution["low_resolution"]

        if low_resolution:
            st=resolution["slice_thickness"]
            zs=resolution["slice_spacing"]
            count=resolution["slice_count"]
            message=QMessageBox(self)
            message.setIcon(QMessageBox.Warning)
            message.setWindowTitle("Low-resolution 3D source")
            message.setText("현재 Series는 Slice 간격이 두꺼워 고품질 3D 재구성에 제한이 있습니다.")
            message.setInformativeText(
                f"Images: {count}\nSlice Thickness: {st:.2f} mm\nZ Spacing: {zs:.2f} mm\n\n"
                "MPR / MIP / Volume Rendering은 가능하지만 Coronal, Sagittal 및 3D 표면에서 "
                "계단 현상이나 뭉개짐이 보일 수 있습니다.\n\nLow-resolution mode로 계속 여시겠습니까?"
            )
            continue_btn=message.addButton("Open Low-resolution 3D",QMessageBox.AcceptRole)
            message.addButton(QMessageBox.Cancel)
            message.exec()
            if message.clickedButton() is not continue_btn:
                return

        try:
            dialog=Viewer3DDialog(
                datasets=None,parent=self,mode=mode,low_resolution=low_resolution,volume_info=volume_info
            )
            dialog.exec()
        except Exception as e:
            QMessageBox.critical(self,"3D Viewer Error",str(e))

    def open_dicom(self):
        files,_=QFileDialog.getOpenFileNames(
            self,
            "Open DICOM",
            "",
            "DICOM Files (*.dcm *.dicom);;All Files (*.*)"
        )
        if files:
            self.import_paths(files)

    def open_folder(self):
        folder=QFileDialog.getExistingDirectory(self,"Open DICOM Folder")
        if folder:
            self.import_paths([folder])

    def import_paths(self,items):
        if self._import_thread is not None and self._import_thread.isRunning():
            self.statusBar().showMessage("DICOM import is already running",3000)
            return

        items=[str(item) for item in items if str(item)]
        if not items:
            return

        if len(items)==1:
            self.path_label.setText(items[0])
        else:
            self.path_label.setText(f"{len(items)} items dropped / selected")

        self._import_preview_path=""
        self.progress_started_at=perf_counter()
        self.progress_text.setText("Scanning files...")
        self.progress_text.setVisible(True)
        self.progress_bar.setRange(0,0)
        self.progress_bar.setVisible(True)
        QApplication.processEvents()

        thread=QThread(self)
        worker=ImportWorker(items)
        worker.moveToThread(thread)

        thread.started.connect(worker.run)
        worker.scan_progress.connect(self._on_import_scan_progress)
        worker.indexing_started.connect(self._on_import_indexing_started)
        worker.index_progress.connect(self._on_import_index_progress)
        worker.finished.connect(self._on_import_finished)
        worker.failed.connect(self._on_import_failed)
        worker.finished.connect(thread.quit)
        worker.failed.connect(thread.quit)
        worker.finished.connect(worker.deleteLater)
        worker.failed.connect(worker.deleteLater)
        thread.finished.connect(self._on_import_thread_finished)
        thread.finished.connect(thread.deleteLater)

        self._import_thread=thread
        self._import_worker=worker
        thread.start()

    def _on_import_scan_progress(self,count):
        self.progress_text.setText(f"Scanning files... {count}")

    def _on_import_indexing_started(self,total):
        self.progress_started_at=perf_counter()
        self._last_progress_ui_at=0.0
        self.progress_bar.setRange(0,100)
        self.progress_bar.setValue(0)
        self.progress_text.setText(f"Scanning & Indexing 0 / {total} | 0%")

    def _on_import_index_progress(self,current,total,dicom_count):
        self._update_progress(
            current,
            total,
            "Scanning & Indexing",
            f"{dicom_count} DICOM"
        )

    def _series_containing_path(self,index,target_path):
        if not target_path:
            return None

        target=_path_key(target_path)

        for studies in index.values():
            for series_map in studies.values():
                for paths in series_map.values():
                    for path in paths:
                        if _path_key(path)==target:
                            return paths
        return None

    def _on_import_finished(self,index,info,files,preview_path,metrics):
        if not files or not index:
            self._finish_progress()
            QMessageBox.information(
                self,
                "DICOM",
                "유효한 DICOM 파일을 찾지 못했습니다."
            )
            return

        self.current_paths=list(files)
        ui_start=perf_counter()

        self.series_tree.setUpdatesEnabled(False)
        try:
            self.series_tree.populate(index,info)
            if self.expand_all_checkbox.isChecked():
                self.series_tree.expandToDepth(2)
            else:
                self.series_tree.expandToDepth(1)
        finally:
            self.series_tree.setUpdatesEnabled(True)

        tree_time=perf_counter()-ui_start
        self.file_count_label.setText(f"{len(files)} DICOM files")

        try:
            scan_time=float(metrics.get("scan",0.0))
            index_time=float(metrics.get("index",0.0))
            total_time=float(metrics.get("total",0.0))
        except Exception:
            pass

        first_load_start=perf_counter()
        first_series=self._series_containing_path(
            index,
            preview_path
        )
        if first_series is None:
            first_series=self.series_tree.select_first_series()

        if first_series:
            self.load_series(
                first_series,
                start_file_path=preview_path
            )
            self.series_tree.expand_series_by_paths(first_series)
            first_image_time=perf_counter()-first_load_start
            ui_time=perf_counter()-ui_start
            try:
                self.statusBar().showMessage(
                    f"Ready {len(files)} DICOM | Scan {scan_time:.2f}s | Index {index_time:.2f}s | Tree {tree_time:.2f}s | First image {first_image_time:.2f}s | UI {ui_time:.2f}s",
                    10000
                )
            except Exception:
                pass
        else:
            self._finish_progress("Ready")

    def _on_import_failed(self,message):
        self._finish_progress()
        QMessageBox.critical(self,"DICOM Import Error",message)

    def _on_import_thread_finished(self):
        self._import_thread=None
        self._import_worker=None


    def load_series(self,paths,start_file_path=None):
        paths=[str(path) for path in paths]

        if not paths:
            return

        self.series_tree.set_active_series_by_paths(paths)

        start_index=0

        if start_file_path:
            target=_path_key(start_file_path)

            for idx,path in enumerate(paths):
                if _path_key(path)==target:
                    start_index=idx
                    break

        try:
            # Lazy mode:
            # Series 전체를 dcmread하지 않고 현재 Slice 한 장만 즉시 읽는다.
            self.viewer.set_series_paths(
                paths,
                start_index=start_index
            )

            self.metadata.set_dataset(
                self.viewer.current_dataset()
            )

            self._update_path_from_current()

            self.statusBar().showMessage(
                f"Ready {len(paths)} slices (lazy loading)",
                3000
            )

            # 일반 Series 이동에서는 Rendering progress를 띄우지 않는다.
            self._finish_progress()

        except Exception as e:
            self._finish_progress()
            QMessageBox.critical(
                self,
                "DICOM Load Error",
                str(e)
            )

    def _on_tree_file_selected(self,paths,file_path):
        if not file_path:
            return

        paths=[str(path) for path in paths]
        loaded_paths=list(
            getattr(self.viewer,"series_paths",[]) or []
        )

        def norm(value):
            try:
                return str(Path(value).resolve()).lower()
            except Exception:
                return str(value).lower()

        target=norm(file_path)

        if loaded_paths and [norm(p) for p in loaded_paths]==[norm(p) for p in paths]:
            normalized=[norm(p) for p in loaded_paths]

            if target in normalized:
                self.series_tree.set_active_series_by_paths(paths)
                self.viewer.set_slice(normalized.index(target))
                return

        self.load_series(
            paths,
            start_file_path=file_path
        )

    def _on_slice_scroll_changed(self,value):
        if not getattr(self.viewer,"series_paths",None):
            return

        self._pending_slice_index=int(value)

        # Drag 중 모든 중간 slice를 전부 decode하지 않고,
        # 마지막 위치를 약 35ms 단위로 반영한다.
        self.slice_scroll_timer.start()

    def _apply_pending_slice_scroll(self):
        if self._pending_slice_index is None:
            return

        index=int(self._pending_slice_index)
        self._pending_slice_index=None

        if (
            getattr(self.viewer,"series_paths",None)
            and index!=self.viewer.index
        ):
            self.viewer.set_slice(index)

    def reset_window_level(self):
        if hasattr(self.viewer,"reset_window_level"):
            self.viewer.reset_window_level()
        elif hasattr(self.viewer,"_load_current"):
            self.viewer._load_current(reset_window=True)

    def show_about(self):
        QMessageBox.information(
            self,
            "About",
            "Python DICOM Viewer\n\n"
            "Drag && Drop 지원\n"
            "Light / Dark Theme 지원\n"
            "Progress 표시 지원\n"
            "PySide6 + pydicom 기반"
        )

    def _update_path_from_current(self):
        ds=self.viewer.current_dataset()
        filename=getattr(ds,"filename","") if ds is not None else ""
        if filename:
            self.path_label.setText(str(filename))

    def _on_slice_changed(self,current,total):
        self.slice_label.setText(f"Slice: {current}/{total}")
        try:
            self.metadata.set_dataset(self.viewer.current_dataset())
        except Exception:
            pass
        self._update_path_from_current()
        self.slice_scroll.blockSignals(True)
        try:
            self.slice_scroll.setRange(0,max(0,total-1))
            self.slice_scroll.setPageStep(
                max(1,min(25,total//10 if total>10 else 1))
            )
            self.slice_scroll.setValue(max(0,current-1))
            self.slice_scroll.setEnabled(total>1)
        finally:
            self.slice_scroll.blockSignals(False)

    def _on_window_changed(self,width,level):
        pass

    def dragEnterEvent(self,event):
        mime=event.mimeData()
        if mime.hasUrls():
            local_paths=[
                url.toLocalFile()
                for url in mime.urls()
                if url.isLocalFile()
            ]
            if local_paths:
                event.acceptProposedAction()
                return
        event.ignore()

    def dragMoveEvent(self,event):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
        else:
            event.ignore()

    def dropEvent(self,event):
        mime=event.mimeData()
        if not mime.hasUrls():
            event.ignore()
            return

        paths=[
            url.toLocalFile()
            for url in mime.urls()
            if url.isLocalFile()
        ]

        if not paths:
            event.ignore()
            return

        event.acceptProposedAction()
        self.import_paths(paths)
