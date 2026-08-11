from PySide6.QtCore import Qt
import numpy as np
from PySide6.QtWidgets import (
    QDialog,QVBoxLayout,QHBoxLayout,QComboBox,QLabel,QPushButton,QStackedWidget,QDoubleSpinBox,QWidget
)

try:
    import vtk
    from vtk.util import numpy_support
    from vtkmodules.qt.QVTKRenderWindowInteractor import QVTKRenderWindowInteractor
    VTK_AVAILABLE=True
except Exception:
    vtk=None
    numpy_support=None
    QVTKRenderWindowInteractor=None
    VTK_AVAILABLE=False

from dicom.volume_builder import build_volume,resample_volume_isotropic
from viewer.mpr_widget import MPRPanel


class Viewer3DDialog(QDialog):
    def __init__(self,datasets=None,parent=None,mode="MPR",low_resolution=False,volume_info=None):
        super().__init__(parent)

        self.low_resolution=bool(low_resolution)
        self.setWindowTitle(
            "3D Viewer - Low Resolution"
            if self.low_resolution
            else "3D Viewer"
        )
        self.resize(1500,900)

        self.volume_info=volume_info if volume_info is not None else build_volume(datasets or [])
        self.volume=self.volume_info["volume"]
        self.spacing=self.volume_info["spacing"]
        self.original_volume=self.volume
        self.original_spacing=self.spacing
        self.mip_volume=self.volume
        self.mip_spacing=self.spacing
        self.mip_window_level=300.0
        self.mip_window_width=700.0

        self.mode_combo=QComboBox()
        self.mode_combo.addItems(["MPR","MIP","Volume Rendering"])
        self.mode_combo.setCurrentText(mode)
        self.mode_combo.currentTextChanged.connect(self.set_mode)

        self.reset_btn=QPushButton("Reset View")
        self.reset_btn.clicked.connect(self.reset_view)

        st=self.volume_info.get("slice_thickness",0.0)
        zs=self.volume_info.get("slice_spacing",0.0)
        count=self.volume_info.get("slice_count",len(datasets or []))

        self.quality_label=QLabel(
            (
                f"Low-resolution source | "
                f"{count} slices | ST {st:.2f} mm | Z {zs:.2f} mm"
            )
            if self.low_resolution
            else
            f"{count} slices | ST {st:.2f} mm | Z {zs:.2f} mm"
        )

        if self.low_resolution:
            self.quality_label.setStyleSheet(
                "QLabel{font-weight:600;padding:4px 8px;"
                "border:1px solid #8a6d3b;border-radius:3px;}"
            )

        top=QHBoxLayout()
        top.addWidget(QLabel("Mode"))
        top.addWidget(self.mode_combo)
        top.addWidget(self.reset_btn)
        top.addStretch()
        top.addWidget(self.quality_label)

        self.mip_controls=QWidget()
        mip_row=QHBoxLayout(self.mip_controls)
        mip_row.setContentsMargins(0,0,0,0)

        mip_row.addWidget(QLabel("MIP Quality"))
        self.mip_quality_combo=QComboBox()
        self.mip_quality_combo.addItems([
            "Auto",
            "Original",
            "0.7 mm Isotropic",
            "1.0 mm Isotropic",
            "1.5 mm Isotropic",
            "2.0 mm Isotropic"
        ])
        self.mip_quality_combo.currentTextChanged.connect(
            self._change_mip_quality
        )
        mip_row.addWidget(self.mip_quality_combo)

        self.mip_auto_label=QLabel()
        mip_row.addWidget(self.mip_auto_label)

        mip_row.addSpacing(18)
        mip_row.addWidget(QLabel("WL"))
        self.mip_wl_spin=QDoubleSpinBox()
        self.mip_wl_spin.setRange(-3000.0,10000.0)
        self.mip_wl_spin.setDecimals(0)
        self.mip_wl_spin.setSingleStep(10.0)
        self.mip_wl_spin.setValue(self.mip_window_level)
        self.mip_wl_spin.valueChanged.connect(self._change_mip_window)
        mip_row.addWidget(self.mip_wl_spin)

        mip_row.addWidget(QLabel("WW"))
        self.mip_ww_spin=QDoubleSpinBox()
        self.mip_ww_spin.setRange(1.0,20000.0)
        self.mip_ww_spin.setDecimals(0)
        self.mip_ww_spin.setSingleStep(10.0)
        self.mip_ww_spin.setValue(self.mip_window_width)
        self.mip_ww_spin.valueChanged.connect(self._change_mip_window)
        mip_row.addWidget(self.mip_ww_spin)

        self.mip_reset_window_btn=QPushButton("Reset MIP WL")
        self.mip_reset_window_btn.clicked.connect(self._reset_mip_window)
        mip_row.addWidget(self.mip_reset_window_btn)
        mip_row.addStretch()

        self.stack=QStackedWidget()

        # Interactive MPR / Thick-slab MIP panel
        self.mpr_panel=MPRPanel(
            self.volume,
            self.spacing,
            superior_at_high_index=self.volume_info.get(
                "superior_at_high_index",
                True
            )
        )
        self.stack.addWidget(self.mpr_panel)

        # VTK is expensive to initialize. Create it only when Volume Rendering is opened.
        self.vtk_widget=None
        self.render_window=None
        self.renderer=None
        self.interactor=None
        self._vtk_numpy_ref=None

        layout=QVBoxLayout(self)
        layout.addLayout(top)
        layout.addWidget(self.mip_controls)
        layout.addWidget(self.stack,1)

        self.image_data=None
        self.current_volume=None
        self.current_mapper=None
        self.current_mip_property=None

        # MPR and slab MIP use the original volume directly. Do not perform an
        # expensive isotropic resample or VTK deep copy during dialog startup.
        self.mip_quality_combo.blockSignals(True)
        self.mip_quality_combo.setCurrentText("Original")
        self.mip_quality_combo.blockSignals(False)

        self.set_mode(mode)

    def _ensure_vtk(self):
        if self.vtk_widget is not None:
            return
        if not VTK_AVAILABLE:
            raise RuntimeError("VTK is not installed.\n\nInstall it with:\npip install vtk")
        self.vtk_widget=QVTKRenderWindowInteractor(self)
        self.render_window=self.vtk_widget.GetRenderWindow()
        self.renderer=vtk.vtkRenderer()
        self.renderer.SetBackground(0.0,0.0,0.0)
        self.render_window.AddRenderer(self.renderer)
        self.interactor=self.render_window.GetInteractor()
        self.render_window.SetMultiSamples(0)
        self.stack.addWidget(self.vtk_widget)
        self.interactor.Initialize()

    def _to_vtk_image(self,volume,spacing):
        z,y,x=volume.shape
        image=vtk.vtkImageData()
        image.SetDimensions(x,y,z)
        image.SetSpacing(
            float(spacing[0]),
            float(spacing[1]),
            float(spacing[2])
        )
        image.SetOrigin(0.0,0.0,0.0)

        flat=np.ascontiguousarray(volume,dtype=np.float32).ravel(order="C")
        self._vtk_numpy_ref=flat
        vtk_array=numpy_support.numpy_to_vtk(
            num_array=flat,
            deep=False,
            array_type=vtk.VTK_FLOAT
        )
        image.GetPointData().SetScalars(vtk_array)
        return image

    def _auto_mip_spacing(self):
        sx,sy,sz=[float(v) for v in self.original_spacing]
        max_spacing=max(sx,sy,sz)

        if max_spacing<=0.7:
            return 0.7
        if max_spacing<=3.0:
            return 1.0
        if max_spacing<=5.0:
            return 1.5
        return 2.0

    def _quality_target(self,text):
        if text=="Original":
            return None
        if text=="Auto":
            return self._auto_mip_spacing()
        if text.startswith("0.7"):
            return 0.7
        if text.startswith("1.0"):
            return 1.0
        if text.startswith("1.5"):
            return 1.5
        return 2.0

    def _change_mip_quality(self,text,render=True):
        target=self._quality_target(text)

        if target is None:
            self.mip_volume=self.original_volume
            self.mip_spacing=self.original_spacing
            self.mip_auto_label.setText("")
        else:
            if text=="Auto":
                self.mip_auto_label.setText(
                    f"Auto → {target:.1f} mm isotropic"
                )
            else:
                self.mip_auto_label.setText("")

            try:
                self.setCursor(Qt.WaitCursor)
                volume,spacing=resample_volume_isotropic(
                    self.original_volume,
                    self.original_spacing,
                    target_spacing=target
                )
                self.mip_volume=volume
                self.mip_spacing=spacing
            except Exception as e:
                from PySide6.QtWidgets import QMessageBox
                QMessageBox.critical(
                    self,
                    "MIP Resolution Error",
                    str(e)
                )
                self.mip_volume=self.original_volume
                self.mip_spacing=self.original_spacing
                self.mip_auto_label.setText("")
            finally:
                self.unsetCursor()

        if render and self.mode_combo.currentText()=="MIP":
            self._ensure_vtk()
            self.image_data=self._to_vtk_image(self.mip_volume,self.mip_spacing)

        if render and self.mode_combo.currentText()=="MIP":
            self.renderer.RemoveAllViewProps()
            self._show_mip()
            self.renderer.ResetCamera()
            self.render_window.Render()

    def _change_mip_window(self,*args):
        self.mip_window_level=float(self.mip_wl_spin.value())
        self.mip_window_width=max(1.0,float(self.mip_ww_spin.value()))

        if self.mode_combo.currentText()=="MIP":
            self._update_mip_transfer()
            self.render_window.Render()

    def _reset_mip_window(self):
        self.mip_wl_spin.blockSignals(True)
        self.mip_ww_spin.blockSignals(True)
        self.mip_wl_spin.setValue(300.0)
        self.mip_ww_spin.setValue(700.0)
        self.mip_wl_spin.blockSignals(False)
        self.mip_ww_spin.blockSignals(False)

        self.mip_window_level=300.0
        self.mip_window_width=700.0

        if self.mode_combo.currentText()=="MIP":
            self._update_mip_transfer()
            self.render_window.Render()

    def _update_mip_transfer(self):
        if self.current_mip_property is None:
            return

        wl=float(self.mip_window_level)
        ww=max(1.0,float(self.mip_window_width))
        low=wl-ww/2.0
        high=wl+ww/2.0
        mid=(low+high)/2.0

        color=vtk.vtkColorTransferFunction()
        color.AddRGBPoint(low,0.0,0.0,0.0)
        color.AddRGBPoint(mid,0.5,0.5,0.5)
        color.AddRGBPoint(high,1.0,1.0,1.0)

        opacity=vtk.vtkPiecewiseFunction()
        opacity.AddPoint(low-1.0,0.0)
        opacity.AddPoint(low,0.0)
        opacity.AddPoint(mid,0.65)
        opacity.AddPoint(high,1.0)
        opacity.AddPoint(high+2000.0,1.0)

        self.current_mip_property.SetColor(color)
        self.current_mip_property.SetScalarOpacity(opacity)

    def set_mode(self,mode):
        # MPR and MIP share the same interactive 3-panel MPR workspace.
        # MPR = single-slice mode
        # MIP = draggable thick-slab MIP mode
        self.mip_controls.setVisible(False)

        if mode=="MPR":
            self.stack.setCurrentWidget(self.mpr_panel)
            self.mpr_panel.mode_combo.blockSignals(True)
            self.mpr_panel.mode_combo.setCurrentText("Slice")
            self.mpr_panel.mode_combo.blockSignals(False)
            self.mpr_panel.set_mode("Slice")
            return

        if mode=="MIP":
            self.stack.setCurrentWidget(self.mpr_panel)
            self.mpr_panel.mode_combo.blockSignals(True)
            self.mpr_panel.mode_combo.setCurrentText("MIP Slab")
            self.mpr_panel.mode_combo.blockSignals(False)
            self.mpr_panel.set_mode("MIP Slab")
            return

        self._ensure_vtk()
        self.stack.setCurrentWidget(self.vtk_widget)
        self.renderer.RemoveAllViewProps()
        self.image_data=self._to_vtk_image(
            self.original_volume,
            self.original_spacing
        )
        self._show_volume()
        self.renderer.ResetCamera()
        self.render_window.Render()

    def _show_mip(self):
        mapper=vtk.vtkGPUVolumeRayCastMapper()
        mapper.SetInputData(self.image_data)
        mapper.SetBlendModeToMaximumIntensity()

        # Higher quality ray sampling.
        min_spacing=min(float(v) for v in self.mip_spacing)
        try:
            mapper.SetAutoAdjustSampleDistances(False)
            mapper.SetSampleDistance(max(0.15,min_spacing*0.4))
        except Exception:
            pass

        prop=vtk.vtkVolumeProperty()
        prop.SetInterpolationTypeToLinear()
        prop.ShadeOff()

        volume=vtk.vtkVolume()
        volume.SetMapper(mapper)
        volume.SetProperty(prop)

        self.current_mapper=mapper
        self.current_mip_property=prop
        self._update_mip_transfer()

        self.renderer.AddVolume(volume)
        self.current_volume=volume

    def _show_volume(self):
        mapper=vtk.vtkGPUVolumeRayCastMapper()
        mapper.SetInputData(self.image_data)
        mapper.SetBlendModeToComposite()

        color=vtk.vtkColorTransferFunction()
        color.AddRGBPoint(-1000,0.0,0.0,0.0)
        color.AddRGBPoint(-100,0.1,0.1,0.1)
        color.AddRGBPoint(40,0.55,0.35,0.25)
        color.AddRGBPoint(200,0.9,0.75,0.55)
        color.AddRGBPoint(500,1.0,0.95,0.85)
        color.AddRGBPoint(1500,1.0,1.0,1.0)

        opacity=vtk.vtkPiecewiseFunction()
        opacity.AddPoint(-1000,0.0)
        opacity.AddPoint(-100,0.0)
        opacity.AddPoint(20,0.02)
        opacity.AddPoint(100,0.08)
        opacity.AddPoint(300,0.2)
        opacity.AddPoint(800,0.5)
        opacity.AddPoint(1500,0.85)

        prop=vtk.vtkVolumeProperty()
        prop.SetColor(color)
        prop.SetScalarOpacity(opacity)
        prop.SetInterpolationTypeToLinear()
        prop.ShadeOn()
        prop.SetAmbient(0.2)
        prop.SetDiffuse(0.7)
        prop.SetSpecular(0.2)

        volume=vtk.vtkVolume()
        volume.SetMapper(mapper)
        volume.SetProperty(prop)
        self.renderer.AddVolume(volume)
        self.current_volume=volume

    def reset_view(self):
        if self.mode_combo.currentText() in ("MPR","MIP"):
            self.mpr_panel.reset_view()
            return

        self.renderer.ResetCamera()
        self.render_window.Render()
