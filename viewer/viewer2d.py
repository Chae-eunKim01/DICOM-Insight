import numpy as np
import pydicom
from datetime import datetime
from collections import OrderedDict
from PySide6.QtCore import Qt,Signal,QTimer,QEvent
from PySide6.QtGui import QImage,QPixmap,QPainter,QBrush,QColor,QTransform
from PySide6.QtWidgets import QGraphicsView,QGraphicsScene,QGraphicsPixmapItem,QLabel
from dicom.pixel_decoder import apply_window,get_default_window,decode_hu,is_color_dataset,normalize_color


class HoverPixmapItem(QGraphicsPixmapItem):
    def __init__(self,on_hover=None,on_leave=None,parent=None):
        super().__init__(parent)
        self.on_hover=on_hover
        self.on_leave=on_leave
        self.setAcceptHoverEvents(True)

    def hoverMoveEvent(self,event):
        pos=event.pos()

        if self.on_hover is not None:
            self.on_hover(float(pos.x()),float(pos.y()))

        super().hoverMoveEvent(event)

    def hoverLeaveEvent(self,event):
        if self.on_leave is not None:
            self.on_leave()

        super().hoverLeaveEvent(event)



class DicomViewer2D(QGraphicsView):
    slice_changed=Signal(int,int)
    window_changed=Signal(float,float)
    current_file_changed=Signal(str)

    def __init__(self,parent=None):
        super().__init__(parent)
        self.scene=QGraphicsScene(self)
        self.setScene(self.scene)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.pixmap_item=HoverPixmapItem(
            on_hover=self._on_image_hover,
            on_leave=self._on_image_hover_leave
        )
        self.scene.addItem(self.pixmap_item)

        self.datasets=[]
        self.series_paths=[]
        self.dataset_cache=OrderedDict()
        self.dataset_cache_size=16
        self.index=0
        self.hu=None
        self.hu_cache=OrderedDict()
        self.hu_cache_size=48
        self.window_width=400.0
        self.window_level=40.0
        self.default_window_width=400.0
        self.default_window_level=40.0
        self.rotation_angle=0
        self.flip_horizontal=False
        self.flip_vertical=False
        self.drag_mode_name=None
        self.last_pos=None

        self.setFrameShape(QGraphicsView.NoFrame)
        self.setRenderHint(QPainter.SmoothPixmapTransform,False)
        self.setBackgroundBrush(QBrush(QColor("#000000")))
        self.setTransformationAnchor(QGraphicsView.AnchorUnderMouse)
        self.setResizeAnchor(QGraphicsView.AnchorViewCenter)
        self.setMouseTracking(True)
        self.viewport().setMouseTracking(True)

        self.pixel_probe_text=""

        self.overlay_top_left=QLabel(self.viewport())
        self.overlay_top_right=QLabel(self.viewport())
        self.overlay_bottom_left=QLabel(self.viewport())
        self.overlay_bottom_right=QLabel(self.viewport())
        self.overlay_mid_left=QLabel(self.viewport())
        self.overlay_mid_right=QLabel(self.viewport())

        self._setup_overlay_label(self.overlay_top_left)
        self._setup_overlay_label(self.overlay_top_right)
        self._setup_overlay_label(self.overlay_bottom_left)
        self._setup_overlay_label(self.overlay_bottom_right)
        self._setup_overlay_label(self.overlay_mid_left)
        self._setup_overlay_label(self.overlay_mid_right)

        self.overlay_top_right.setAlignment(Qt.AlignRight|Qt.AlignTop)
        self.overlay_bottom_right.setAlignment(Qt.AlignRight|Qt.AlignBottom)
        self.overlay_mid_left.setAlignment(Qt.AlignLeft|Qt.AlignVCenter)
        self.overlay_mid_right.setAlignment(Qt.AlignRight|Qt.AlignVCenter)

        self._update_overlay_positions()

    def _setup_overlay_label(self,label):
        label.setStyleSheet("""
            QLabel{
                color:white;
                background:transparent;
                font-family:Consolas, "Courier New", monospace;
                font-size:14px;
                font-weight:600;
            }
        """)
        label.setAttribute(Qt.WA_TransparentForMouseEvents,True)
        label.setText("")
        label.show()

    def _safe_text(self,ds,name,default="-"):
        try:
            value=getattr(ds,name,None)
            if value is None or str(value).strip()=="":
                return default
            return str(value)
        except Exception:
            return default

    def _format_study_datetime(self,ds):
        study_date=self._safe_text(ds,"StudyDate","")
        study_time=self._safe_text(ds,"StudyTime","")

        if not study_date:
            return "-"

        try:
            date_obj=datetime.strptime(study_date[:8],"%Y%m%d")
            date_text=date_obj.strftime("%d-%B-%Y")
        except Exception:
            date_text=study_date

        if study_time:
            try:
                clean_time=study_time.split(".")[0].ljust(6,"0")
                time_obj=datetime.strptime(clean_time[:6],"%H%M%S")
                time_text=time_obj.strftime("%H:%M:%S")
            except Exception:
                time_text=study_time
        else:
            time_text=""

        return f"{date_text} {time_text}".strip()

    def _slice_location_text(self,ds):
        value=getattr(ds,"SliceLocation",None)

        if value is not None:
            try:
                return f"{float(value):.2f} mm"
            except Exception:
                return str(value)

        ipp=getattr(ds,"ImagePositionPatient",None)
        if ipp is not None and len(ipp)>=3:
            try:
                return f"{float(ipp[2]):.2f} mm"
            except Exception:
                pass

        return "-"

    def _on_image_hover(self,x,y):
        ds=self.current_dataset()

        if ds is None or self.hu is None:
            return

        ix=int(x)
        iy=int(y)

        arr=np.asarray(self.hu)

        try:
            if is_color_dataset(ds):
                if arr.ndim==4:
                    arr=arr[0]

                if arr.ndim<3:
                    return

                height,width=arr.shape[:2]

                if ix<0 or iy<0 or ix>=width or iy>=height:
                    return

                value=arr[iy,ix]
                value_text=self._format_pixel_value(value)
                text=f"X: {ix}  Y: {iy}  RGB: {value_text}"

            else:
                arr=np.squeeze(arr)

                if arr.ndim!=2:
                    return

                height,width=arr.shape

                if ix<0 or iy<0 or ix>=width or iy>=height:
                    return

                hu=float(arr[iy,ix])

                if abs(hu-round(hu))<0.05:
                    hu_text=str(int(round(hu)))
                else:
                    hu_text=f"{hu:.1f}"

                text=f"X: {ix}  Y: {iy}  HU: {hu_text}"

            if text!=self.pixel_probe_text:
                self.pixel_probe_text=text
                self._update_overlays()

        except Exception:
            pass

    def _on_image_hover_leave(self):
        if self.pixel_probe_text:
            self.pixel_probe_text=""
            self._update_overlays()

    def _format_pixel_value(self,value):
        try:
            if np.isscalar(value):
                value=float(value)
                if abs(value-round(value))<1e-6:
                    return str(int(round(value)))
                return f"{value:.2f}"

            arr=np.asarray(value).reshape(-1)
            if arr.size>=3:
                vals=[]
                for v in arr[:3]:
                    fv=float(v)
                    if abs(fv-round(fv))<1e-6:
                        vals.append(str(int(round(fv))))
                    else:
                        vals.append(f"{fv:.2f}")
                return f"({', '.join(vals)})"

            return str(value)
        except Exception:
            return "-"

    def _update_pixel_probe(self,viewport_pos):
        ds=self.current_dataset()

        if ds is None or self.hu is None:
            self.pixel_probe_text=""
            self._update_overlays()
            return

        try:
            if hasattr(viewport_pos,"toPoint"):
                viewport_point=viewport_pos.toPoint()
            else:
                viewport_point=viewport_pos

            scene_point=self.mapToScene(viewport_point)
            image_point=self.pixmap_item.mapFromScene(scene_point)

            x=int(image_point.x())
            y=int(image_point.y())

            pixmap=self.pixmap_item.pixmap()
            width=pixmap.width()
            height=pixmap.height()

            if x<0 or y<0 or x>=width or y>=height:
                if self.pixel_probe_text:
                    self.pixel_probe_text=""
                    self._update_overlays()
                return

            arr=np.asarray(self.hu)

            if is_color_dataset(ds):
                if arr.ndim==4:
                    arr=arr[0]

                if arr.ndim<3:
                    return

                value=arr[y,x]
                value_text=self._format_pixel_value(value)
                text=f"X: {x}  Y: {y}  RGB: {value_text}"

            else:
                if arr.ndim>2:
                    arr=np.squeeze(arr)

                if arr.ndim!=2:
                    return

                hu=float(arr[y,x])

                if abs(hu-round(hu))<0.05:
                    hu_text=str(int(round(hu)))
                else:
                    hu_text=f"{hu:.1f}"

                text=f"X: {x}  Y: {y}  HU: {hu_text}"

            if text!=self.pixel_probe_text:
                self.pixel_probe_text=text
                self._update_overlays()

        except Exception:
            if self.pixel_probe_text:
                self.pixel_probe_text=""
                self._update_overlays()


    def _update_overlays(self):
        ds=self.current_dataset()

        if ds is None:
            self.overlay_top_left.setText("")
            self.overlay_top_right.setText("")
            self.overlay_bottom_left.setText("")
            self.overlay_bottom_right.setText("")
            self.overlay_mid_left.setText("")
            self.overlay_mid_right.setText("")
            return

        study_desc=self._safe_text(ds,"StudyDescription")
        series_desc=self._safe_text(ds,"SeriesDescription")
        study_datetime=self._format_study_datetime(ds)
        manufacturer=self._safe_text(ds,"Manufacturer")

        slice_thickness=self._safe_text(ds,"SliceThickness")
        try:
            slice_thickness=f"{float(slice_thickness):.2f} mm"
        except Exception:
            if slice_thickness!="-":
                slice_thickness=f"{slice_thickness} mm"

        slice_location=self._slice_location_text(ds)

        self.overlay_top_left.setText(
            f"{study_desc}\n"
            f"{series_desc}"
        )

        self.overlay_top_right.setText(
            f"{manufacturer}\n"
            f"{study_datetime}"
        )

        self.overlay_bottom_left.setText(
            f"ST: {slice_thickness}\n"
            f"SL: {slice_location}\n"
            f"Images: {self.index+1}/{len(self.series_paths)}"
        )

        if is_color_dataset(ds):
            lines=[]
            if self.pixel_probe_text:
                lines.append(self.pixel_probe_text)
            lines.append("RGB")
            self.overlay_bottom_right.setText("\n".join(lines))
        else:
            lines=[]
            if self.pixel_probe_text:
                lines.append(self.pixel_probe_text)
            lines.append(
                f"WL: {self.window_level:.0f}  "
                f"WW: {self.window_width:.0f}"
            )
            self.overlay_bottom_right.setText("\n".join(lines))

        self.overlay_mid_left.setText("R")
        self.overlay_mid_right.setText("L")

        self.overlay_top_left.adjustSize()
        self.overlay_top_right.adjustSize()
        self.overlay_bottom_left.adjustSize()
        self.overlay_bottom_right.adjustSize()
        self.overlay_mid_left.adjustSize()
        self.overlay_mid_right.adjustSize()
        self._update_overlay_positions()

    def _update_overlay_positions(self):
        margin=10
        side_margin=14
        viewport=self.viewport()
        width=viewport.width()
        height=viewport.height()
        mid_y=height//2

        self.overlay_top_left.move(margin,margin)

        self.overlay_top_right.adjustSize()
        self.overlay_top_right.move(
            max(margin,width-self.overlay_top_right.width()-margin),
            margin
        )

        self.overlay_bottom_left.adjustSize()
        self.overlay_bottom_left.move(
            margin,
            max(margin,height-self.overlay_bottom_left.height()-margin)
        )

        self.overlay_bottom_right.adjustSize()
        self.overlay_bottom_right.move(
            max(margin,width-self.overlay_bottom_right.width()-margin),
            max(margin,height-self.overlay_bottom_right.height()-margin)
        )

        self.overlay_mid_left.adjustSize()
        self.overlay_mid_left.move(
            side_margin,
            max(margin,mid_y-self.overlay_mid_left.height()//2)
        )

        self.overlay_mid_right.adjustSize()
        self.overlay_mid_right.move(
            max(side_margin,width-self.overlay_mid_right.width()-side_margin),
            max(margin,mid_y-self.overlay_mid_right.height()//2)
        )

    def resizeEvent(self,event):
        super().resizeEvent(event)
        self._update_overlay_positions()

    def clear_viewer(self):
        self.datasets=[]
        self.series_paths=[]
        self.dataset_cache.clear()
        self.index=0
        self.hu=None
        self.hu_cache.clear()
        self.pixmap_item.setPixmap(QPixmap())
        self.scene.setSceneRect(self.pixmap_item.sceneBoundingRect())
        self._update_overlays()

    def _cache_dataset(self,index,ds):
        if index in self.dataset_cache:
            self.dataset_cache.pop(index)

        self.dataset_cache[index]=ds

        while len(self.dataset_cache)>self.dataset_cache_size:
            self.dataset_cache.popitem(last=False)

    def _read_dataset_at(self,index):
        if index<0 or index>=len(self.series_paths):
            return None

        if index in self.dataset_cache:
            ds=self.dataset_cache.pop(index)
            self.dataset_cache[index]=ds
            return ds

        path=self.series_paths[index]

        try:
            ds=pydicom.dcmread(
                str(path),
                defer_size=4096
            )
            ds.filename=str(path)
        except Exception:
            return None

        self._cache_dataset(index,ds)
        return ds

    def set_series_paths(self,paths,start_index=0):
        self.datasets=[]
        self.series_paths=[str(path) for path in paths]
        self.dataset_cache.clear()
        self.hu_cache.clear()
        self.hu=None

        if not self.series_paths:
            self.clear_viewer()
            return

        self.index=max(
            0,
            min(int(start_index),len(self.series_paths)-1)
        )

        self.rotation_angle=0
        self.flip_horizontal=False
        self.flip_vertical=False
        self.pixmap_item.setTransform(QTransform())

        self._load_current(reset_window=True)
        QTimer.singleShot(0,self.fit_image)

    def set_series(self,datasets,start_index=0):
        # Backward-compatible path for callers that already have all datasets.
        self.datasets=list(datasets)

        self.series_paths=[
            str(getattr(ds,"filename",""))
            for ds in self.datasets
        ]

        self.dataset_cache.clear()
        self.hu_cache.clear()
        self.hu=None

        for idx,ds in enumerate(self.datasets):
            if idx>=self.dataset_cache_size:
                break
            self._cache_dataset(idx,ds)

        if not self.series_paths:
            self.clear_viewer()
            return

        self.index=max(
            0,
            min(int(start_index),len(self.series_paths)-1)
        )

        self.rotation_angle=0
        self.flip_horizontal=False
        self.flip_vertical=False
        self.pixmap_item.setTransform(QTransform())

        self._load_current(reset_window=True)
        QTimer.singleShot(0,self.fit_image)

    def current_dataset(self):
        if not self.series_paths:
            return None

        return self._read_dataset_at(self.index)

    def _get_cached_hu(self,index,ds):
        if index in self.hu_cache:
            hu=self.hu_cache.pop(index)
            self.hu_cache[index]=hu
            return hu

        hu=decode_hu(ds)
        self.hu_cache[index]=hu

        while len(self.hu_cache)>self.hu_cache_size:
            self.hu_cache.popitem(last=False)

        return hu

    def _load_current(self,reset_window=False):
        ds=self.current_dataset()
        if ds is None:
            return
        self.hu=self._get_cached_hu(self.index,ds)

        if reset_window and not is_color_dataset(ds):
            self.window_width,self.window_level=get_default_window(ds,self.hu)
            self.default_window_width=self.window_width
            self.default_window_level=self.window_level

        self._render()
        self._update_overlays()
        self.slice_changed.emit(self.index+1,len(self.series_paths))

        filename=getattr(ds,"filename","")
        if filename:
            self.current_file_changed.emit(str(filename))

    def _render(self):
        ds=self.current_dataset()

        if ds is None or self.hu is None:
            return

        if is_color_dataset(ds):
            img=normalize_color(self.hu)

            if img.ndim==4:
                img=img[0]

            if img.ndim!=3 or img.shape[-1]<3:
                return

            img=np.ascontiguousarray(img[...,:3])
            h,w,_=img.shape
            qimg=QImage(
                img.data,
                w,
                h,
                img.strides[0],
                QImage.Format_RGB888
            ).copy()

        else:
            invert=str(
                getattr(ds,"PhotometricInterpretation","")
            ).upper()=="MONOCHROME1"

            img=apply_window(
                self.hu,
                self.window_width,
                self.window_level,
                invert
            )

            h,w=img.shape[:2]
            qimg=QImage(
                img.data,
                w,
                h,
                img.strides[0],
                QImage.Format_Grayscale8
            ).copy()

        self.pixmap_item.setPixmap(QPixmap.fromImage(qimg))
        self.scene.setSceneRect(self.pixmap_item.sceneBoundingRect())

        if not is_color_dataset(ds):
            self.window_changed.emit(
                self.window_width,
                self.window_level
            )

        self._update_overlays()

    def reset_window(self):
        if self.hu is None:
            return
        self.window_width=self.default_window_width
        self.window_level=self.default_window_level
        self._render()

    def set_slice(self,index):
        if not self.series_paths:
            return
        self.index=max(0,min(index,len(self.series_paths)-1))
        self._load_current(reset_window=False)

    def wheelEvent(self,event):
        if not self.series_paths:
            return super().wheelEvent(event)
        delta=event.angleDelta().y()
        if delta>0:
            self.set_slice(self.index-1)
        elif delta<0:
            self.set_slice(self.index+1)

    def mousePressEvent(self,event):
        self.last_pos=event.position()
        if event.button()==Qt.LeftButton:
            self.drag_mode_name="window"
        elif event.button()==Qt.RightButton:
            self.drag_mode_name="zoom"
        elif event.button()==Qt.MiddleButton:
            self.drag_mode_name="pan"
            self.setCursor(Qt.ClosedHandCursor)
        super().mousePressEvent(event)



    def mouseMoveEvent(self,event):
        if self.last_pos is None:
            return super().mouseMoveEvent(event)
        pos=event.position()
        dx=pos.x()-self.last_pos.x()
        dy=pos.y()-self.last_pos.y()

        if (
            self.drag_mode_name=="window"
            and self.hu is not None
            and not is_color_dataset(self.current_dataset())
        ):
            self.window_width=max(1.0,self.window_width+dx*2.0)
            self.window_level=self.window_level+dy*2.0
            self._render()
        elif self.drag_mode_name=="zoom":
            factor=max(0.1,min(1.0+(-dy*0.01),10.0))
            self.scale(factor,factor)
        elif self.drag_mode_name=="pan":
            self.horizontalScrollBar().setValue(self.horizontalScrollBar().value()-int(dx))
            self.verticalScrollBar().setValue(self.verticalScrollBar().value()-int(dy))

        self.last_pos=pos
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self,event):
        self.drag_mode_name=None
        self.last_pos=None
        self.unsetCursor()
        super().mouseReleaseEvent(event)

    def mouseDoubleClickEvent(self,event):
        self.fit_image()
        super().mouseDoubleClickEvent(event)

    def leaveEvent(self,event):
        if self.pixel_probe_text:
            self.pixel_probe_text=""
            self._update_overlays()
        super().leaveEvent(event)


    def _apply_orientation_transform(self,fit=True):
        transform=QTransform()

        if self.flip_horizontal:
            transform.scale(-1,1)

        if self.flip_vertical:
            transform.scale(1,-1)

        if self.rotation_angle:
            transform.rotate(self.rotation_angle)

        self.pixmap_item.setTransform(transform)
        self.scene.setSceneRect(self.pixmap_item.sceneBoundingRect())

        if fit:
            QTimer.singleShot(0,self.fit_image)

    def flip_image_horizontal(self):
        self.flip_horizontal=not self.flip_horizontal
        self._apply_orientation_transform()

    def flip_image_vertical(self):
        self.flip_vertical=not self.flip_vertical
        self._apply_orientation_transform()

    def rotate_image_left(self):
        self.rotation_angle=(self.rotation_angle-90)%360
        self._apply_orientation_transform()

    def rotate_image_right(self):
        self.rotation_angle=(self.rotation_angle+90)%360
        self._apply_orientation_transform()

    def restore_orientation(self):
        self.rotation_angle=0
        self.flip_horizontal=False
        self.flip_vertical=False
        self.pixmap_item.setTransform(QTransform())
        self.scene.setSceneRect(self.pixmap_item.sceneBoundingRect())
        QTimer.singleShot(0,self.fit_image)

    def reset_view(self):
        ds=self.current_dataset()

        if ds is None:
            return

        # Window Level / Width 초기화
        if not is_color_dataset(ds):
            self.window_width=float(self.default_window_width)
            self.window_level=float(self.default_window_level)

        # Rotate / Flip 초기화
        self.rotation_angle=0
        self.flip_horizontal=False
        self.flip_vertical=False
        self.pixmap_item.setTransform(QTransform())

        # Zoom / Pan 초기화
        self.resetTransform()
        self.scene.setSceneRect(self.pixmap_item.sceneBoundingRect())

        # 초기 Window로 다시 Rendering
        self._render()

        # 화면 중앙 Fit
        QTimer.singleShot(0,self.fit_image)

    def fit_image(self):
        if self.pixmap_item.pixmap().isNull():
            return
        self.resetTransform()
        self.fitInView(self.pixmap_item,Qt.KeepAspectRatio)

    def set_window_preset(self,width=None,level=None,full_dynamic=False):
        ds=self.current_dataset()

        if ds is None or self.hu is None:
            return

        if is_color_dataset(ds):
            return

        if full_dynamic:
            finite=self.hu[np.isfinite(self.hu)]
            if finite.size==0:
                return

            low=float(np.min(finite))
            high=float(np.max(finite))
            self.window_width=max(1.0,high-low)
            self.window_level=(high+low)/2.0

        elif width is not None and level is not None:
            self.window_width=max(1.0,float(width))
            self.window_level=float(level)

        else:
            self.reset_window_level()
            return

        self._render()

    def reset_window_level(self):
        if not self.series_paths:
            return
        self._load_current(reset_window=True)

