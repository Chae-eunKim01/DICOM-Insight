from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime,timedelta
from pathlib import Path
from statistics import mean,median

import pydicom
from PySide6.QtCore import Qt,QRectF,QPointF
from PySide6.QtGui import QColor,QPainter,QPen,QFont,QBrush
from PySide6.QtWidgets import (
    QDialog,QVBoxLayout,QHBoxLayout,QLabel,QTableWidget,QTableWidgetItem,
    QHeaderView,QWidget,QAbstractItemView,QPushButton,QTabWidget,QScrollArea,QFrame,
    QSizePolicy,QAbstractScrollArea
)

from dicom.frame_metadata import frame_value


@dataclass
class TimingPoint:
    index:int
    path:str
    frame_index:int|None
    timestamp:datetime|None
    source:str
    temporal_hint:str=""
    spatial_key:tuple|None=None


@dataclass
class AcquisitionGroup:
    group_index:int
    timestamp:datetime
    point_rows:list[int]

    @property
    def count(self):
        return len(self.point_rows)


def _text(value):
    if value is None:
        return ""
    try:
        return str(value).strip()
    except Exception:
        return ""


def _parse_da_tm(date_value,time_value):
    date_text=_text(date_value).replace("-","").replace(".","")
    time_text=_text(time_value).replace(":","")
    if not date_text or not time_text:
        return None
    time_text=time_text.split("+")[0].split("-")[0]
    if "." in time_text:
        main,fraction=time_text.split(".",1)
    else:
        main,fraction=time_text,""
    main=(main+"000000")[:6]
    try:
        base=datetime.strptime(date_text[:8]+main,"%Y%m%d%H%M%S")
        if fraction:
            base=base.replace(microsecond=int((fraction+"000000")[:6]))
        return base
    except Exception:
        return None


def _parse_dt(value):
    text=_text(value)
    if not text:
        return None
    core=text
    for sign in ("+","-"):
        pos=core.find(sign,8)
        if pos>0:
            core=core[:pos]
            break
    if "." in core:
        main,fraction=core.split(".",1)
    else:
        main,fraction=core,""
    main=(main+"00000000000000")[:14]
    try:
        base=datetime.strptime(main,"%Y%m%d%H%M%S")
        if fraction:
            base=base.replace(microsecond=int((fraction+"000000")[:6]))
        return base
    except Exception:
        return None


def _dataset_datetime(ds,frame_index=None):
    if frame_index is not None:
        for keyword in ("FrameAcquisitionDateTime","FrameReferenceDateTime"):
            value=frame_value(ds,keyword,frame_index,None)
            parsed=_parse_dt(value)
            if parsed:
                return parsed,keyword

    for keyword in ("AcquisitionDateTime","ContentDateTime"):
        value=getattr(ds,keyword,None)
        parsed=_parse_dt(value)
        if parsed:
            return parsed,keyword

    pairs=(
        ("AcquisitionDate","AcquisitionTime"),
        ("ContentDate","ContentTime"),
        ("SeriesDate","SeriesTime"),
        ("StudyDate","StudyTime"),
    )
    for date_kw,time_kw in pairs:
        if frame_index is not None:
            date_value=frame_value(ds,date_kw,frame_index,getattr(ds,date_kw,None))
            time_value=frame_value(ds,time_kw,frame_index,getattr(ds,time_kw,None))
        else:
            date_value=getattr(ds,date_kw,None)
            time_value=getattr(ds,time_kw,None)
        parsed=_parse_da_tm(date_value,time_value)
        if parsed:
            return parsed,f"{date_kw}+{time_kw}"
    return None,""


def _frame_time_offsets(ds,count):
    try:
        vector=getattr(ds,"FrameTimeVector",None)
        if vector is not None:
            values=[float(v) for v in vector]
            if len(values)>=count:
                offsets=[0.0]
                total=0.0
                for value in values[:count-1]:
                    total+=value/1000.0
                    offsets.append(total)
                return offsets,"FrameTimeVector"
    except Exception:
        pass
    try:
        frame_time=float(getattr(ds,"FrameTime"))
        return [i*frame_time/1000.0 for i in range(count)],"FrameTime"
    except Exception:
        return None,""


def _timing_hint(ds,frame_index=None):
    # Prefer DICOM temporal identifiers when they repeat across multiple slices.
    for keyword in (
        "TemporalPositionIdentifier",
        "TemporalPositionIndex",
        "FrameAcquisitionNumber",
        "AcquisitionNumber",
    ):
        try:
            value=frame_value(ds,keyword,frame_index,getattr(ds,keyword,None))
            text=_text(value)
            if text:
                return f"{keyword}:{text}"
        except Exception:
            continue
    return ""


def _spatial_key(ds,frame_index=None):
    # Repeated slice positions are a strong signal for dynamic CT/MR volumes.
    try:
        value=frame_value(ds,"ImagePositionPatient",frame_index,getattr(ds,"ImagePositionPatient",None))
        if value is not None:
            vals=[float(v) for v in value]
            if len(vals)>=3:
                return tuple(round(v,3) for v in vals[:3])
    except Exception:
        pass
    try:
        value=frame_value(ds,"SliceLocation",frame_index,getattr(ds,"SliceLocation",None))
        if value is not None and _text(value):
            return (round(float(value),3),)
    except Exception:
        pass
    return None


def collect_timing_points(paths,frame_indices=None):
    paths=[str(path) for path in paths]
    if frame_indices is None:
        frame_indices=[None]*len(paths)
    cache={}
    points=[]
    path_positions={}

    for i,(path,frame_index) in enumerate(zip(paths,frame_indices),1):
        if path not in cache:
            try:
                cache[path]=pydicom.dcmread(path,stop_before_pixels=True,force=True)
            except Exception:
                cache[path]=None
        ds=cache[path]
        timestamp=None
        source=""
        temporal_hint=""
        spatial_key=None
        if ds is not None:
            timestamp,source=_dataset_datetime(ds,frame_index)
            temporal_hint=_timing_hint(ds,frame_index)
            spatial_key=_spatial_key(ds,frame_index)
        points.append(TimingPoint(i,path,frame_index,timestamp,source,temporal_hint,spatial_key))
        path_positions.setdefault(path,[]).append(len(points)-1)

    for path,positions in path_positions.items():
        if len(positions)<=1:
            continue
        ds=cache.get(path)
        if ds is None:
            continue
        if all(points[pos].timestamp is not None and points[pos].source.startswith("Frame") for pos in positions):
            continue
        offsets,offset_source=_frame_time_offsets(ds,len(positions))
        if offsets is None:
            continue
        base,base_source=_dataset_datetime(ds,None)
        if base is None:
            continue
        for local_index,pos in enumerate(positions):
            point=points[pos]
            if point.timestamp is None or not point.source.startswith("Frame"):
                point.timestamp=base+timedelta(seconds=offsets[local_index])
                point.source=f"{base_source}+{offset_source}"
    return points


def build_acquisition_groups(points,tolerance_seconds=0.001):
    valid=[(row,point) for row,point in enumerate(points) if point.timestamp is not None]
    if not valid:
        return []
    valid.sort(key=lambda item:(item[1].timestamp,item[0]))

    def finalize(row_groups):
        groups=[]
        for rows in row_groups:
            if not rows:
                continue
            timestamp=min(points[row].timestamp for row in rows if points[row].timestamp is not None)
            groups.append(AcquisitionGroup(len(groups)+1,timestamp,list(rows)))
        return groups

    # 1) Exact/same-time grouping works well for many CTP exports where all
    # slices from one temporal phase share one AcquisitionTime.
    exact=[]
    for row,point in valid:
        if not exact or abs((point.timestamp-points[exact[-1][0]].timestamp).total_seconds())>tolerance_seconds:
            exact.append([row])
        else:
            exact[-1].append(row)
    if len(exact)<=max(1,int(len(valid)*0.50)):
        return finalize(exact)

    # 2) Prefer explicit temporal identifiers if the same identifier is reused
    # for multiple slices. This handles many CT/MR dynamic acquisitions.
    hinted=[(row,point.temporal_hint) for row,point in valid if point.temporal_hint]
    if hinted:
        hint_counts={}
        hint_order=[]
        for row,hint in hinted:
            if hint not in hint_counts:
                hint_counts[hint]=[]
                hint_order.append(hint)
            hint_counts[hint].append(row)
        multi=sum(1 for rows in hint_counts.values() if len(rows)>1)
        if 1<len(hint_counts)<len(valid)*0.80 and multi>=max(1,len(hint_counts)//2):
            ordered=sorted(hint_counts.values(),key=lambda rows:min(points[row].timestamp for row in rows))
            return finalize(ordered)

    # 3) Dynamic perfusion series often acquire the same spatial slice set
    # repeatedly, but each slice has its own timestamp (e.g. every 35-50 ms).
    # Detect a new temporal phase when a slice position repeats.
    spatial_rows=[(row,point.spatial_key) for row,point in valid if point.spatial_key is not None]
    unique_positions={key for _,key in spatial_rows}
    if len(unique_positions)>=2 and len(spatial_rows)>=len(valid)*0.70:
        cycles=[]
        current=[]
        seen=set()
        for row,point in valid:
            key=point.spatial_key
            if key is not None and key in seen and current:
                cycles.append(current)
                current=[]
                seen=set()
            current.append(row)
            if key is not None:
                seen.add(key)
        if current:
            cycles.append(current)
        # Only accept spatial cycling when it actually reduces timestamp
        # fragmentation and produces more than one repeated acquisition.
        if 1<len(cycles)<len(exact)*0.75 and median([len(rows) for rows in cycles])>=2:
            return finalize(cycles)

    # 4) Last resort: split on large temporal gaps. Short per-slice intervals
    # remain in one acquisition phase while long pauses start a new phase.
    timestamps=[point.timestamp for _,point in valid]
    positive_gaps=[
        (timestamps[i]-timestamps[i-1]).total_seconds()
        for i in range(1,len(timestamps))
        if (timestamps[i]-timestamps[i-1]).total_seconds()>0
    ]
    baseline=median(positive_gaps) if positive_gaps else 0.0
    threshold=max(0.25,baseline*5.0)
    phases=[]
    current=[]
    prev=None
    for row,point in valid:
        if prev is not None and (point.timestamp-prev).total_seconds()>threshold and current:
            phases.append(current)
            current=[]
        current.append(row)
        prev=point.timestamp
    if current:
        phases.append(current)
    return finalize(phases)


def _fmt_timestamp(value):
    if value is None:
        return "-"
    return value.strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]


def _fmt_interval(seconds):
    if seconds is None:
        return "-"
    if abs(seconds)<1.0:
        return f"{seconds*1000.0:.1f} ms"
    return f"{seconds:.3f} s"


def _fmt_elapsed(seconds):
    if seconds is None:
        return "-"
    if abs(seconds)<1.0:
        return f"+{seconds*1000.0:.0f} ms"
    return f"+{seconds:.3f} s"


class AcquisitionGroupChart(QWidget):
    def __init__(self,parent=None):
        super().__init__(parent)
        self.groups=[]
        self.setMinimumHeight(340)
        self.setMinimumWidth(980)

    def _preferred_width(self):
        group_count=max(1,len(self.groups))
        return max(980,180+group_count*72)

    def set_groups(self,groups):
        self.groups=list(groups)
        width=self._preferred_width()
        self.setMinimumWidth(0)
        self.setFixedSize(width,340)
        self.updateGeometry()
        self.update()

    def _colors(self):
        dark=self.palette().window().color().lightness()<128
        if dark:
            return QColor("#171717"),QColor("#f3f4f6"),QColor("#555b66"),QColor("#42c8f5"),QColor("#90e0ff")
        return QColor("#ffffff"),QColor("#202124"),QColor("#c4c7cc"),QColor("#1769aa"),QColor("#4b9ed1")

    def paintEvent(self,event):
        painter=QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing,True)
        bg,fg,grid,accent,accent2=self._colors()
        painter.fillRect(self.rect(),bg)

        # Keep a generous margin around the plot so axis labels never cover
        # the bars or each other, especially on dark mode / high-DPI screens.
        left=90
        right=72
        top=56
        bottom=128
        rect=QRectF(left,top,max(1,self.width()-left-right),max(1,self.height()-top-bottom))
        painter.setFont(QFont("Consolas",9))
        painter.setPen(fg)

        painter.drawText(QRectF(8,8,260,22),Qt.AlignLeft|Qt.AlignVCenter,"Slices / Frames per acquisition")
        painter.drawText(QRectF(rect.left(),self.height()-28,rect.width(),20),Qt.AlignCenter,"Elapsed time from first acquisition")

        if not self.groups:
            painter.drawText(rect,Qt.AlignCenter,"Acquisition groups unavailable")
            return

        max_count=max(group.count for group in self.groups) or 1
        first_time=self.groups[0].timestamp
        elapsed=[max(0.0,(group.timestamp-first_time).total_seconds()) for group in self.groups]
        max_elapsed=max(elapsed) if elapsed else 0.0

        # Y axis/grid. Labels live completely outside the plot rectangle.
        painter.setPen(QPen(grid,1))
        painter.drawRect(rect)
        for fraction in (0.0,0.25,0.5,0.75,1.0):
            y=rect.bottom()-fraction*rect.height()
            painter.setPen(QPen(grid,1,Qt.DotLine))
            painter.drawLine(rect.left(),y,rect.right(),y)
            painter.setPen(fg)
            count_label=str(int(round(max_count*fraction)))
            painter.drawText(QRectF(4,y-10,left-14,20),Qt.AlignRight|Qt.AlignVCenter,count_label)

        group_count=len(self.groups)
        if group_count==1:
            xs=[rect.center().x()]
        elif max_elapsed>0:
            xs=[rect.left()+(value/max_elapsed)*rect.width() for value in elapsed]
        else:
            xs=[rect.left()+i/max(1,group_count-1)*rect.width() for i in range(group_count)]

        if group_count>1:
            min_gap=rect.width()/max(group_count,1)
            bar_width=max(6.0,min(36.0,min_gap*0.62))
        else:
            bar_width=min(70.0,rect.width()*0.25)

        gaps=[]
        typical=None
        anomaly_indices=set()
        if group_count>1:
            gaps=[(self.groups[i].timestamp-self.groups[i-1].timestamp).total_seconds() for i in range(1,group_count)]
            typical=float(median(gaps))
            # Ignore tiny scanner clock jitter. Only materially different
            # acquisition intervals are highlighted.
            tolerance=max(0.020,abs(typical)*0.02)
            for i,gap in enumerate(gaps,1):
                if abs(gap-typical)>tolerance:
                    # Highlight the acquisition group reached after the unusual interval.
                    anomaly_indices.add(i)

        anomaly_fill=QColor("#ff9f43") if self.palette().window().color().lightness()<128 else QColor("#d97706")
        anomaly_edge=QColor("#ffd19a") if self.palette().window().color().lightness()<128 else QColor("#8a4b08")

        # Bars + slice/frame count. If a bar reaches the top, put its count
        # inside the bar instead of allowing the text to collide with the title.
        for group_pos,(group,x) in enumerate(zip(self.groups,xs)):
            height=(group.count/max_count)*rect.height()
            bar=QRectF(x-bar_width/2,rect.bottom()-height,bar_width,height)
            if group_pos in anomaly_indices:
                painter.setPen(QPen(anomaly_edge,1.4))
                painter.setBrush(anomaly_fill)
            else:
                painter.setPen(QPen(accent2,1))
                painter.setBrush(accent)
            painter.drawRoundedRect(bar,3,3)
            painter.setBrush(Qt.NoBrush)

            count_text=str(group.count)
            if bar.top()-22>=rect.top():
                label_rect=QRectF(x-28,bar.top()-22,56,18)
                painter.setPen(fg)
            else:
                label_rect=QRectF(x-28,bar.top()+4,56,18)
                painter.setPen(QColor("#101010") if self.palette().window().color().lightness()>=128 else QColor("#ffffff"))
            painter.drawText(label_rect,Qt.AlignCenter,count_text)

        # Vertical guides are intentionally subtle and drawn behind x labels.
        if group_count>1:
            painter.setPen(QPen(grid,1,Qt.DotLine))
            for x in xs:
                painter.drawLine(x,rect.top(),x,rect.bottom())

        # X-axis elapsed-time labels. Keep them horizontal and inside a
        # dedicated band below the plot so they cannot be clipped by the chart.
        max_labels=max(2,min(9,int(rect.width()//105)))
        if group_count<=max_labels:
            label_indices=list(range(group_count))
        else:
            step=max(1,int(round((group_count-1)/(max_labels-1))))
            label_indices=list(range(0,group_count,step))
            if label_indices[-1]!=group_count-1:
                label_indices.append(group_count-1)

        painter.setPen(fg)
        tick_y=rect.bottom()+8
        for i in label_indices:
            x=xs[i]
            label=_fmt_elapsed(elapsed[i])
            painter.drawLine(QPointF(x,rect.bottom()),QPointF(x,rect.bottom()+5))
            if i==0:
                label_rect=QRectF(rect.left(),tick_y,110,20)
                alignment=Qt.AlignLeft|Qt.AlignTop
            elif i==group_count-1:
                label_rect=QRectF(rect.right()-110,tick_y,110,20)
                alignment=Qt.AlignRight|Qt.AlignTop
            else:
                label_rect=QRectF(x-55,tick_y,110,20)
                alignment=Qt.AlignHCenter|Qt.AlignTop
            painter.drawText(label_rect,alignment,label)

        # Show the usual acquisition interval once, centered between the
        # x-axis tick labels and the axis title. Individual interval labels stay
        # in the table so the chart remains uncluttered.
        if typical is not None:
            painter.setPen(accent2)
            painter.drawText(
                QRectF(rect.left(),rect.bottom()+42,rect.width(),20),
                Qt.AlignHCenter|Qt.AlignTop,
                f"Δ {_fmt_interval(typical)}"
            )

        # Only materially unusual intervals are emphasized by an orange bar,
        # while small scanner-clock jitter stays normal.
        if anomaly_indices:
            legend_y=14
            legend_x=max(rect.left()+290,rect.right()-230)
            painter.setPen(QPen(anomaly_edge,1))
            painter.setBrush(anomaly_fill)
            painter.drawRoundedRect(QRectF(legend_x,legend_y+2,14,14),3,3)
            painter.setBrush(Qt.NoBrush)
            painter.setPen(fg)
            painter.drawText(QRectF(legend_x+20,legend_y,205,20),Qt.AlignLeft|Qt.AlignVCenter,"Different acquisition interval")


class AcquisitionTimingDialog(QDialog):
    def __init__(self,paths,frame_indices=None,series_uid="",series_description="",jump_callback=None,parent=None):
        super().__init__(parent)
        self.setWindowTitle("Acquisition Timing")
        self.resize(1500,900)
        self.jump_callback=jump_callback
        self.points=collect_timing_points(paths,frame_indices)
        self.groups=build_acquisition_groups(self.points)

        outer_layout=QVBoxLayout(self)
        outer_layout.setContentsMargins(0,0,0,0)
        self.content_widget=QWidget()
        layout=QVBoxLayout(self.content_widget)
        title=QLabel("Acquisition Timing")
        title.setStyleSheet("font-size:18px;font-weight:700;")
        layout.addWidget(title)

        meta=QLabel(
            f"Series UID: {series_uid or '-'}\n"
            f"Series Description: {series_description or '-'}\n"
            f"Images / Frames: {len(self.points)}   |   Acquisition Groups: {len(self.groups)}"
        )
        meta.setTextInteractionFlags(Qt.TextSelectableByMouse)
        layout.addWidget(meta)

        valid=[group.timestamp for group in self.groups]
        group_gaps=[]
        for i in range(1,len(self.groups)):
            group_gaps.append((self.groups[i].timestamp-self.groups[i-1].timestamp).total_seconds())

        summary_layout=QHBoxLayout()
        if valid:
            duration=(valid[-1]-valid[0]).total_seconds() if len(valid)>1 else 0.0
            summary_text=(
                f"First: {_fmt_timestamp(valid[0])}\n"
                f"Last: {_fmt_timestamp(valid[-1])}\n"
                f"Total Duration: {_fmt_interval(duration)}"
            )
        else:
            summary_text="Acquisition timing information unavailable"
        summary_layout.addWidget(QLabel(summary_text),1)

        if group_gaps:
            stats=(
                f"Mean group interval: {_fmt_interval(mean(group_gaps))}\n"
                f"Median group interval: {_fmt_interval(median(group_gaps))}\n"
                f"Min / Max: {_fmt_interval(min(group_gaps))} / {_fmt_interval(max(group_gaps))}"
            )
        elif self.groups:
            stats=f"1 acquisition group containing {self.groups[0].count} images / frames"
        else:
            stats="Acquisition group statistics unavailable"
        summary_layout.addWidget(QLabel(stats),1)
        layout.addLayout(summary_layout)

        self.chart=AcquisitionGroupChart()
        self.chart.set_groups(self.groups)
        self.chart.setFixedHeight(340)
        layout.addWidget(self.chart)

        tabs=QTabWidget()
        layout.addWidget(tabs,1)

        self.group_table=QTableWidget(len(self.groups),6)
        self.group_table.setHorizontalHeaderLabels(["Group","Acquisition Time","Elapsed","Δ Previous","Slices / Frames","Slice Range"])
        self.group_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.group_table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.group_table.verticalHeader().setVisible(False)
        self.group_table.horizontalHeader().setSectionResizeMode(0,QHeaderView.ResizeToContents)
        self.group_table.horizontalHeader().setSectionResizeMode(1,QHeaderView.ResizeToContents)
        self.group_table.horizontalHeader().setSectionResizeMode(2,QHeaderView.ResizeToContents)
        self.group_table.horizontalHeader().setSectionResizeMode(3,QHeaderView.ResizeToContents)
        self.group_table.horizontalHeader().setSectionResizeMode(4,QHeaderView.ResizeToContents)
        self.group_table.horizontalHeader().setSectionResizeMode(5,QHeaderView.Stretch)

        first_group_time=self.groups[0].timestamp if self.groups else None
        group_intervals=[
            (self.groups[i].timestamp-self.groups[i-1].timestamp).total_seconds()
            for i in range(1,len(self.groups))
        ]
        typical_interval=float(median(group_intervals)) if group_intervals else None
        interval_tolerance=max(0.020,abs(typical_interval)*0.02) if typical_interval is not None else None
        anomaly_rows=set()
        if typical_interval is not None:
            for i,gap in enumerate(group_intervals,1):
                if abs(gap-typical_interval)>interval_tolerance:
                    anomaly_rows.add(i)

        cumulative_start=1
        for row,group in enumerate(self.groups):
            elapsed=(group.timestamp-first_group_time).total_seconds() if first_group_time else None
            gap=None if row==0 else (group.timestamp-self.groups[row-1].timestamp).total_seconds()
            cumulative_end=cumulative_start+group.count-1
            slice_range=f"{cumulative_start} - {cumulative_end}"
            values=(
                str(group.group_index),
                _fmt_timestamp(group.timestamp),
                _fmt_elapsed(elapsed),
                _fmt_interval(gap),
                str(group.count),
                slice_range,
            )
            for column,value in enumerate(values):
                item=QTableWidgetItem(value)
                if column in (0,4,5):
                    item.setTextAlignment(Qt.AlignCenter)
                if row in anomaly_rows:
                    dark=self.palette().window().color().lightness()<128
                    item.setBackground(QBrush(QColor("#f2b56b" if dark else "#ffe0b8")))
                    item.setForeground(QBrush(QColor("#111111")))
                self.group_table.setItem(row,column,item)
            cumulative_start=cumulative_end+1
        self.group_table.cellDoubleClicked.connect(self._jump_to_group)
        tabs.addTab(self.group_table,"Acquisition Groups")

        self.table=QTableWidget(len(self.points),5)
        self.table.setHorizontalHeaderLabels(["#","File / Frame","Acquisition Time","Δ Previous","Source"])
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.verticalHeader().setVisible(False)
        self.table.horizontalHeader().setSectionResizeMode(0,QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(1,QHeaderView.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(2,QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(3,QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(4,QHeaderView.ResizeToContents)

        previous=None
        for row,point in enumerate(self.points):
            delta=None
            if point.timestamp is not None and previous is not None:
                delta=(point.timestamp-previous).total_seconds()
            if point.timestamp is not None:
                previous=point.timestamp
            frame_text=Path(point.path).name
            if point.frame_index is not None:
                frame_text+=f" [Frame {point.frame_index+1}]"
            values=(str(point.index),frame_text,_fmt_timestamp(point.timestamp),_fmt_interval(delta),point.source or "-")
            for column,value in enumerate(values):
                item=QTableWidgetItem(value)
                if column==0:
                    item.setTextAlignment(Qt.AlignCenter)
                self.table.setItem(row,column,item)
        self.table.cellDoubleClicked.connect(self._jump_to_row)
        tabs.addTab(self.table,"Image / Frame Detail")

        # Scroll the entire Acquisition Timing dashboard horizontally instead
        # of scrolling only the graph. This keeps the chart, tables and footer
        # aligned as one dashboard while the dialog itself stays near the 3D
        # viewer size (1500 x 900).
        content_width=max(1460,self.chart.minimumWidth()+24)
        self.content_widget.setMinimumWidth(content_width)
        self.content_widget.setMinimumHeight(840)
        tabs.setMinimumHeight(300)
        self.group_table.setMinimumHeight(260)
        self.table.setMinimumHeight(260)
        self.content_widget.adjustSize()

        self.dashboard_scroll=QScrollArea()
        self.dashboard_scroll.setWidgetResizable(False)
        self.dashboard_scroll.setSizeAdjustPolicy(QAbstractScrollArea.AdjustIgnored)
        self.dashboard_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOn)
        self.dashboard_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.dashboard_scroll.setFrameShape(QFrame.NoFrame)
        self.dashboard_scroll.setWidget(self.content_widget)
        outer_layout.addWidget(self.dashboard_scroll)

    def _jump_to_group(self,row,column):
        if self.jump_callback is not None and 0<=row<len(self.groups):
            self.jump_callback(self.groups[row].point_rows[0])

    def _jump_to_row(self,row,column):
        if self.jump_callback is not None:
            self.jump_callback(row)
