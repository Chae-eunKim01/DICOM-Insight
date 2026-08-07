import numpy as np
from PySide6.QtCore import Qt,QRectF,Signal
from PySide6.QtGui import QImage,QPainter,QPen,QPixmap,QFont
from PySide6.QtWidgets import QWidget,QHBoxLayout,QVBoxLayout,QLabel,QComboBox,QPushButton,QMessageBox

from dicom.volume_builder import resample_volume_isotropic

AXIS_COLORS={
    "sagittal":Qt.green,
    "coronal":Qt.yellow,
    "axial":Qt.red
}

class MPRView(QWidget):
    def __init__(self,panel,orientation):
        super().__init__()
        self.panel=panel
        self.orientation=orientation
        self.drag_axis=None
        self.setMouseTracking(True)
        self.setMinimumSize(280,280)

    def _plane_info(self):
        v=self.panel.volume
        z,y,x=v.shape
        sx,sy,sz=self.panel.spacing

        if self.orientation=="axial":
            return x,y,sx,sy
        if self.orientation=="coronal":
            return x,z,sx,sz
        return y,z,sy,sz

    def _target_rect(self):
        cols,rows,spx,spy=self._plane_info()
        physical_w=max(cols*spx,1e-6)
        physical_h=max(rows*spy,1e-6)
        avail=QRectF(8,34,max(1,self.width()-16),max(1,self.height()-42))

        image_ratio=physical_w/physical_h
        box_ratio=avail.width()/avail.height()

        if image_ratio>box_ratio:
            w=avail.width()
            h=w/image_ratio
        else:
            h=avail.height()
            w=h*image_ratio

        x=avail.x()+(avail.width()-w)/2
        y=avail.y()+(avail.height()-h)/2
        return QRectF(x,y,w,h)

    def _slab_half_count(self,axis):
        spacing=self.panel.axis_spacing(axis)
        thickness=self.panel.slab_mm[axis]
        return max(0,int(round((thickness/spacing)/2.0)))

    def _image_array(self):
        v=self.panel.volume
        idx=self.panel.index
        mode=self.panel.mode

        if self.orientation=="axial":
            c=idx["axial"]
            if mode=="MIP Slab":
                h=self._slab_half_count("axial")
                lo=max(0,c-h)
                hi=min(v.shape[0],c+h+1)
                arr=np.max(v[lo:hi,:,:],axis=0)
            else:
                arr=v[c,:,:]

            return arr

        if self.orientation=="coronal":
            c=idx["coronal"]
            if mode=="MIP Slab":
                h=self._slab_half_count("coronal")
                lo=max(0,c-h)
                hi=min(v.shape[1],c+h+1)
                arr=np.max(v[:,lo:hi,:],axis=1)
            else:
                arr=v[:,c,:]

            # Array row axis = volume Z.
            # 화면의 첫 row가 Superior(Head)가 되도록 자동 보정.
            if self.panel.superior_at_high_index:
                arr=np.flipud(arr)

            return arr

        c=idx["sagittal"]
        if mode=="MIP Slab":
            h=self._slab_half_count("sagittal")
            lo=max(0,c-h)
            hi=min(v.shape[2],c+h+1)
            arr=np.max(v[:,:,lo:hi],axis=2)
        else:
            arr=v[:,:,c]

        if self.panel.superior_at_high_index:
            arr=np.flipud(arr)

        return arr


    def _to_qimage(self,arr):
        wl=self.panel.window_level
        ww=max(1.0,self.panel.window_width)
        low=wl-ww/2.0
        high=wl+ww/2.0
        img=np.clip(arr,low,high)
        img=((img-low)/(high-low)*255.0).astype(np.uint8)
        img=np.ascontiguousarray(img)
        h,w=img.shape
        return QImage(
            img.data,w,h,img.strides[0],QImage.Format_Grayscale8
        ).copy()

    def _index_to_screen(self,axis,index,rect):
        z,y,x=self.panel.volume.shape

        if self.orientation=="axial":
            if axis=="sagittal":
                return rect.left()+index/max(x-1,1)*rect.width()
            if axis=="coronal":
                return rect.top()+index/max(y-1,1)*rect.height()

        elif self.orientation=="coronal":
            if axis=="sagittal":
                return rect.left()+index/max(x-1,1)*rect.width()
            if axis=="axial":
                ratio=index/max(z-1,1)
                if self.panel.superior_at_high_index:
                    ratio=1.0-ratio
                return rect.top()+ratio*rect.height()

        else:
            if axis=="coronal":
                return rect.left()+index/max(y-1,1)*rect.width()
            if axis=="axial":
                ratio=index/max(z-1,1)
                if self.panel.superior_at_high_index:
                    ratio=1.0-ratio
                return rect.top()+ratio*rect.height()

        return None


    def _screen_to_index(self,axis,pos,rect):
        z,y,x=self.panel.volume.shape

        if axis=="sagittal":
            ratio=(pos.x()-rect.left())/max(rect.width(),1)
            return int(round(np.clip(ratio,0,1)*(x-1)))

        if axis=="coronal":
            if self.orientation=="sagittal":
                ratio=(pos.x()-rect.left())/max(rect.width(),1)
            else:
                ratio=(pos.y()-rect.top())/max(rect.height(),1)

            return int(round(np.clip(ratio,0,1)*(y-1)))

        ratio=(pos.y()-rect.top())/max(rect.height(),1)
        ratio=float(np.clip(ratio,0,1))

        if (
            self.orientation in ("coronal","sagittal")
            and self.panel.superior_at_high_index
        ):
            ratio=1.0-ratio

        return int(round(ratio*(z-1)))


    def _visible_axes(self):
        if self.orientation=="axial":
            return ("sagittal","coronal")
        if self.orientation=="coronal":
            return ("sagittal","axial")
        return ("coronal","axial")

    def _boundary_positions(self,axis,rect):
        center=self.panel.index[axis]
        half=self._slab_half_count(axis)
        limits={
            "sagittal":self.panel.volume.shape[2]-1,
            "coronal":self.panel.volume.shape[1]-1,
            "axial":self.panel.volume.shape[0]-1
        }
        lo=max(0,center-half)
        hi=min(limits[axis],center+half)
        return (
            self._index_to_screen(axis,lo,rect),
            self._index_to_screen(axis,hi,rect)
        )

    def paintEvent(self,event):
        painter=QPainter(self)
        painter.fillRect(self.rect(),Qt.black)

        rect=self._target_rect()
        arr=self._image_array()
        qimg=self._to_qimage(arr)
        painter.drawPixmap(rect.toRect(),QPixmap.fromImage(qimg))

        painter.setFont(QFont("Consolas",10,QFont.Bold))
        painter.setPen(Qt.white)
        title=self.orientation.capitalize()
        current=self.panel.index[self.orientation]+1
        total=self.panel.axis_size(self.orientation)
        painter.drawText(10,20,f"{title}   Slice {current}/{total}")

        # Solid crosshair center lines
        for axis in self._visible_axes():
            p=self._index_to_screen(axis,self.panel.index[axis],rect)
            pen=QPen(AXIS_COLORS[axis],1.4,Qt.SolidLine)
            painter.setPen(pen)

            if (
                (self.orientation=="axial" and axis=="sagittal")
                or (self.orientation=="coronal" and axis=="sagittal")
                or (self.orientation=="sagittal" and axis=="coronal")
            ):
                painter.drawLine(int(p),int(rect.top()),int(p),int(rect.bottom()))
            else:
                painter.drawLine(int(rect.left()),int(p),int(rect.right()),int(p))

        # MIP slab boundaries
        if self.panel.mode=="MIP Slab":
            for axis in self._visible_axes():
                lo,hi=self._boundary_positions(axis,rect)
                pen=QPen(AXIS_COLORS[axis],1.2,Qt.DotLine)
                painter.setPen(pen)

                vertical=(
                    (self.orientation=="axial" and axis=="sagittal")
                    or (self.orientation=="coronal" and axis=="sagittal")
                    or (self.orientation=="sagittal" and axis=="coronal")
                )

                for p in (lo,hi):
                    if vertical:
                        painter.drawLine(
                            int(p),int(rect.top()),int(p),int(rect.bottom())
                        )
                    else:
                        painter.drawLine(
                            int(rect.left()),int(p),int(rect.right()),int(p)
                        )

        painter.end()

    def wheelEvent(self,event):
        delta=event.angleDelta().y()
        # Same convention as the 2D viewer:
        # wheel down -> next slice
        step=-1 if delta>0 else 1
        self.panel.change_slice(self.orientation,step)
        event.accept()

    def mousePressEvent(self,event):
        if event.button()!=Qt.LeftButton:
            return super().mousePressEvent(event)

        rect=self._target_rect()
        if not rect.contains(event.position()):
            return

        # In slab mode, first check whether a dotted boundary was grabbed.
        if self.panel.mode=="MIP Slab":
            tolerance=9.0
            for axis in self._visible_axes():
                lo,hi=self._boundary_positions(axis,rect)
                coord=(
                    event.position().x()
                    if (
                        (self.orientation=="axial" and axis=="sagittal")
                        or (self.orientation=="coronal" and axis=="sagittal")
                        or (self.orientation=="sagittal" and axis=="coronal")
                    )
                    else event.position().y()
                )

                if min(abs(coord-lo),abs(coord-hi))<=tolerance:
                    self.drag_axis=axis
                    event.accept()
                    return

        self.panel.move_crosshair(self.orientation,event.position(),rect)
        event.accept()

    def mouseMoveEvent(self,event):
        if self.drag_axis is not None:
            rect=self._target_rect()
            idx=self._screen_to_index(self.drag_axis,event.position(),rect)
            center=self.panel.index[self.drag_axis]
            distance=abs(idx-center)
            spacing=self.panel.axis_spacing(self.drag_axis)

            # Full slab width between the two parallel boundaries.
            thickness=max(spacing,2.0*distance*spacing)
            self.panel.set_slab_thickness(self.drag_axis,thickness)
            event.accept()
            return

        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self,event):
        if event.button()==Qt.LeftButton:
            self.drag_axis=None
        super().mouseReleaseEvent(event)


class MPRPanel(QWidget):
    def __init__(self,volume,spacing,superior_at_high_index=True,parent=None):
        super().__init__(parent)
        self.original_volume=np.asarray(volume,dtype=np.float32)
        self.original_spacing=tuple(float(v) for v in spacing)
        self.superior_at_high_index=bool(superior_at_high_index)

        self.volume=self.original_volume
        self.spacing=self.original_spacing

        z,y,x=self.volume.shape
        self.index={
            "axial":z//2,
            "coronal":y//2,
            "sagittal":x//2
        }

        self.mode="Slice"
        self.slab_mm={
            "axial":max(self.spacing[2],10.0),
            "coronal":max(self.spacing[1],10.0),
            "sagittal":max(self.spacing[0],10.0)
        }

        self.window_level=40.0
        self.window_width=350.0

        controls=QHBoxLayout()
        controls.addWidget(QLabel("MPR"))

        self.mode_combo=QComboBox()
        self.mode_combo.addItems(["Slice","MIP Slab"])
        self.mode_combo.currentTextChanged.connect(self.set_mode)
        controls.addWidget(self.mode_combo)

        controls.addWidget(QLabel("Quality"))
        self.quality_combo=QComboBox()
        self.quality_combo.addItems([
            "Auto",
            "Original",
            "0.7 mm Isotropic",
            "1.0 mm Isotropic",
            "1.5 mm Isotropic",
            "2.0 mm Isotropic"
        ])
        self.quality_combo.currentTextChanged.connect(self.set_quality)
        controls.addWidget(self.quality_combo)

        self.auto_quality_label=QLabel()
        controls.addWidget(self.auto_quality_label)

        self.slab_label=QLabel()
        controls.addWidget(self.slab_label)
        controls.addStretch()

        self.axial=MPRView(self,"axial")
        self.coronal=MPRView(self,"coronal")
        self.sagittal=MPRView(self,"sagittal")

        views=QHBoxLayout()
        views.setSpacing(2)
        views.addWidget(self.axial,1)
        views.addWidget(self.coronal,1)
        views.addWidget(self.sagittal,1)

        layout=QVBoxLayout(self)
        layout.setContentsMargins(0,0,0,0)
        layout.addLayout(controls)
        layout.addLayout(views,1)

        self.update_slab_label()

        self.quality_combo.blockSignals(True)
        self.quality_combo.setCurrentText("Auto")
        self.quality_combo.blockSignals(False)
        self.set_quality("Auto")

    def axis_size(self,axis):
        if axis=="axial":
            return self.volume.shape[0]
        if axis=="coronal":
            return self.volume.shape[1]
        return self.volume.shape[2]

    def axis_spacing(self,axis):
        if axis=="axial":
            return self.spacing[2]
        if axis=="coronal":
            return self.spacing[1]
        return self.spacing[0]

    def _auto_target_spacing(self):
        sx,sy,sz=self.original_spacing
        max_spacing=max(float(sx),float(sy),float(sz))

        if max_spacing<=0.7:
            return 0.7
        if max_spacing<=3.0:
            return 1.0
        if max_spacing<=5.0:
            return 1.5
        return 2.0

    def set_quality(self,text):
        if text=="Original":
            self.volume=self.original_volume
            self.spacing=self.original_spacing
            self.auto_quality_label.setText("")

        else:
            if text=="Auto":
                target=self._auto_target_spacing()
                self.auto_quality_label.setText(
                    f"Auto → {target:.1f} mm isotropic"
                )
            elif text.startswith("0.7"):
                target=0.7
                self.auto_quality_label.setText("")
            elif text.startswith("1.0"):
                target=1.0
                self.auto_quality_label.setText("")
            elif text.startswith("1.5"):
                target=1.5
                self.auto_quality_label.setText("")
            else:
                target=2.0
                self.auto_quality_label.setText("")

            try:
                self.setCursor(Qt.WaitCursor)

                volume,spacing=resample_volume_isotropic(
                    self.original_volume,
                    self.original_spacing,
                    target_spacing=target
                )

                self.volume=volume
                self.spacing=spacing

            except Exception as e:
                QMessageBox.critical(
                    self,
                    "MPR Resampling Error",
                    str(e)
                )

                self.quality_combo.blockSignals(True)
                self.quality_combo.setCurrentText("Original")
                self.quality_combo.blockSignals(False)

                self.volume=self.original_volume
                self.spacing=self.original_spacing
                self.auto_quality_label.setText("")

            finally:
                self.unsetCursor()

        z,y,x=self.volume.shape
        self.index={
            "axial":z//2,
            "coronal":y//2,
            "sagittal":x//2
        }

        self.slab_mm={
            "axial":max(self.spacing[2],10.0),
            "coronal":max(self.spacing[1],10.0),
            "sagittal":max(self.spacing[0],10.0)
        }

        self.update_slab_label()
        self.update_all()


    def set_mode(self,mode):
        self.mode=mode
        self.update_all()

    def set_slab_thickness(self,axis,value):
        self.slab_mm[axis]=max(self.axis_spacing(axis),float(value))
        self.update_slab_label()
        self.update_all()

    def update_slab_label(self):
        self.slab_label.setText(
            "Slab thickness  "
            f"A: {self.slab_mm['axial']:.1f} mm   "
            f"C: {self.slab_mm['coronal']:.1f} mm   "
            f"S: {self.slab_mm['sagittal']:.1f} mm"
        )

    def change_slice(self,axis,step):
        limit=self.axis_size(axis)-1
        self.index[axis]=max(0,min(limit,self.index[axis]+step))
        self.update_all()

    def move_crosshair(self,orientation,pos,rect):
        z,y,x=self.volume.shape

        rx=np.clip(
            (pos.x()-rect.left())/max(rect.width(),1),
            0,
            1
        )
        ry=np.clip(
            (pos.y()-rect.top())/max(rect.height(),1),
            0,
            1
        )

        if orientation=="axial":
            self.index["sagittal"]=int(round(rx*(x-1)))
            self.index["coronal"]=int(round(ry*(y-1)))

        elif orientation=="coronal":
            self.index["sagittal"]=int(round(rx*(x-1)))

            axial_ratio=float(ry)
            if self.superior_at_high_index:
                axial_ratio=1.0-axial_ratio

            self.index["axial"]=int(round(axial_ratio*(z-1)))

        else:
            self.index["coronal"]=int(round(rx*(y-1)))

            axial_ratio=float(ry)
            if self.superior_at_high_index:
                axial_ratio=1.0-axial_ratio

            self.index["axial"]=int(round(axial_ratio*(z-1)))

        self.update_all()


    def reset_view(self):
        z,y,x=self.volume.shape
        self.index={
            "axial":z//2,
            "coronal":y//2,
            "sagittal":x//2
        }
        self.update_all()

    def update_all(self):
        self.axial.update()
        self.coronal.update()
        self.sagittal.update()
