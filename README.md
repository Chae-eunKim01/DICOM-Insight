# Python DICOM Viewer - Dicron Style v0.2

## UI 변경
- 상단: Open DICOM / Open Folder / About
- 현재 DICOM 파일 경로 표시
- WindowCenter / WindowWidth / Reset WL / Slice 표시
- 좌측 DICOM Tree + 파일 개수 + Expand all
- Series 하위에 Slice 파일 목록 표시
- 중앙 흰색 Viewer 영역
- 우측 DICOM Tags 패널
- 검색: Tag ID / Description / Value
- Show all tags 옵션

## 마우스
- Wheel: Slice
- Left Drag: WW/WL
- Right Drag: Zoom
- Middle Drag: Pan
- Double Click: Fit

## Drag & Drop

- DICOM 폴더를 프로그램 창 위로 드래그하면 하위 폴더까지 자동 스캔합니다.
- `.dcm` 파일 하나를 드롭할 수 있습니다.
- 여러 `.dcm` 파일을 동시에 드롭할 수 있습니다.
- 폴더와 파일을 함께 드롭하는 것도 지원합니다.

## Theme

상단 메뉴에서 변경할 수 있습니다.

`View > Theme > Light`
`View > Theme > Dark`

마지막으로 선택한 Theme은 QSettings에 저장되어 다음 실행 시 유지됩니다.

## View Button

Theme 메뉴는 상단 버튼 영역으로 이동했습니다.

`Open DICOM | Open Folder | About | View`

`View > Theme > Light`
`View > Theme > Dark`

## v0.6 Viewer Load Fix

- DICOM 폴더/파일을 Import하면 첫 번째 Series를 자동으로 표시합니다.
- Series를 한 번 클릭하면 바로 Viewer에 표시합니다.
- Series 아래의 개별 DICOM 파일을 클릭해도 해당 Series를 Viewer에 표시합니다.
- DICOM 한 개만 Drag & Drop한 경우에도 바로 영상과 Tag가 표시됩니다.

## v0.7 Progress

DICOM import와 rendering 진행률을 상단에서 확인할 수 있습니다.

예:
`Scanning 3835 / 4480 | 85% | 3835 DICOM | ETA 2s`

`Rendering 25 / 39 | 64% | 25 loaded | ETA 1s`

Drag & Drop, Open DICOM, Open Folder 모두 동일하게 진행률을 표시합니다.

## v0.8 DICOM Tag Fix

- 비표준 길이 DICOM element를 pydicom에서 UN으로 처리합니다.
- 깨진 Tag 하나 때문에 전체 DICOM Tag panel이 비지 않도록 수정했습니다.
- 기본 화면에서는 주요 DICOM Tag를 표시합니다.
- `Show all tags`를 체크하면 전체 top-level DICOM Element를 표시합니다.
- Tag ID / Description / VR / Value 4열 표시
- Pixel Data와 긴 binary value는 안전하게 요약 표시합니다.
- Metadata 오류가 있어도 영상 렌더링은 계속됩니다.

## v0.9 VR Column

기본 DICOM Tag 화면:
`Tag ID | Description | Value`

`Show all tags` 체크 시:
`Tag ID | Description | VR | Value`

체크 해제 시 VR 컬럼은 다시 숨겨집니다.

## v0.10 Tag ID / Tree Sync

- 기본 DICOM Tag 화면에서도 실제 Tag ID를 표시합니다.
- 기본 상태: `Tag ID | Description | Value`
- Show all tags: `Tag ID | Description | VR | Value`
- Mouse Wheel로 Slice를 이동하면 좌측 DICOM Tree의 현재 `.dcm` 항목이 자동 선택됩니다.
- 현재 Slice 항목이 Tree 화면 밖에 있으면 자동으로 중앙 위치까지 스크롤합니다.

## v0.11 UX Fix

- 현재 보고 있는 DICOM slice를 좌측 DICOM Tree에서 굵은 글씨 + 선택 배경색으로 강조합니다.
- Show all tags에서도 VR 컬럼을 제거했습니다.
- DICOM Tag 표는 항상 `Tag ID | Description | Value` 3열입니다.
- Mouse Wheel Down = 다음 Slice
- Mouse Wheel Up = 이전 Slice

## v0.12 Tree Selection Sync

- Viewer의 현재 DICOM 파일 경로를 기준으로 DICOM Tree를 동기화합니다.
- 굵은 글씨뿐 아니라 실제 Qt 선택 표시(파란 selection indicator)도 현재 DICOM으로 이동합니다.
- 현재 항목의 부모 Patient / Study / Series는 자동으로 펼쳐집니다.
- 현재 DICOM이 Tree 화면 밖에 있으면 자동으로 중앙까지 스크롤합니다.
- Tree 원본 순서와 Viewer slice 정렬 순서가 달라도 실제 파일 경로 기준으로 정확히 선택합니다.

## v0.13 Unified Tree Selection

- 현재 Slice의 Bold와 Qt 파란 선택 표시를 하나의 선택 상태로 통합했습니다.
- 이전에 클릭했던 DICOM에 파란 표시가 남는 현상을 수정했습니다.
- Mouse Wheel로 이동할 때 현재 DICOM 파일만 Bold + 선택 표시됩니다.

## v0.14 Performance

- DICOM Tree에서 현재 파일을 찾을 때 전체 4,000+ Tree를 매번 순회하지 않고 파일 경로 인덱스를 사용합니다.
- Tree 자동 스크롤은 현재 항목이 화면 밖에 있을 때만 수행합니다.
- 최근 48개 Slice의 HU pixel array를 LRU cache로 보관합니다.
- 이전 Slice로 다시 돌아갈 때 pixel data를 다시 decode하지 않습니다.
- DICOM Tag 기본 테이블은 매 Slice마다 모든 cell widget을 새로 만들지 않고 기존 cell 값을 갱신합니다.

## v0.15 Fast Scanning / Indexing

성능 개선:
- 기존: Scanning에서 DICOM header 1회 + Indexing에서 다시 1회
- 변경: DICOM 판별과 Indexing을 하나의 header read로 통합
- `os.scandir()` 기반 빠른 폴더 재귀 탐색
- `ThreadPoolExecutor`를 이용한 병렬 DICOM header read
- Index 구성에 필요한 DICOM Tag만 `specific_tags`로 읽음
- Pixel Data는 Scanning/Indexing 단계에서 읽지 않음

4,000개 이상 파일이 있는 폴더에서 기존 방식보다 빠른 로딩을 목표로 합니다.

## v0.16 RGB / Fit Fix

- `Samples Per Pixel > 1` 또는 `Photometric Interpretation = RGB`인 DICOM을 RGB888로 표시합니다.
- RGB DICOM을 Grayscale8로 잘못 해석해 영상이 작게/왜곡되어 보이던 문제를 수정했습니다.
- MONOCHROME1/2 영상은 기존 HU + WW/WL 방식을 유지합니다.
- RGB 영상에서는 WW/WL 조작을 적용하지 않습니다.
- 새 Series를 열 때 Qt layout이 끝난 뒤 Fit to View를 수행합니다.

## v0.17 Image Overlay

MicroDicom 스타일의 영상 정보 Overlay를 추가했습니다.

좌측 상단:
- Study Description
- Series Description

우측 상단:
- Study Date
- Study Time

좌측 하단:
- Slice Thickness
- Slice Location
- Images: 현재 Slice / 전체 Slice

Mouse Wheel로 Slice를 이동하면 Slice Location과 Images 값도 자동 갱신됩니다.
SliceLocation Tag가 없는 경우 ImagePositionPatient의 Z 값을 대신 표시합니다.

## v0.18 Study DateTime Format

우측 상단 Study Date / Study Time을 한 줄로 표시합니다.

예:
`16-November-2024 19:52:57`

DICOM:
- StudyDate `20241116`
- StudyTime `195257.123456`

처럼 fractional seconds가 있어도 화면에는 `19:52:57`까지만 표시합니다.

## v0.19 Manufacturer Overlay

우측 상단 Overlay:
- Manufacturer
- Study DateTime

예:
`SIEMENS`
`16-November-2024 19:52:57`

## v0.20 Side Marker Overlay

MicroDicom 스타일의 방향 마커를 추가했습니다.

- 좌측 중간: `R`
- 우측 중간: `L`

Viewer 높이의 중앙에 고정되어 표시됩니다.

## v0.21 Window Preset

`View > Window Preset`

- 0 Default: DICOM 기본 Window Center / Width
- 1 Full Dynamic: 현재 Slice의 전체 HU 범위
- 2 Skull: WL 600 / WW 2800
- 3 Lung: WL -600 / WW 1500
- 4 Abdomen: WL 60 / WW 400
- 5 Mediastinum: WL 40 / WW 400
- 6 Bone: WL 300 / WW 1500
- 7 Spine: WL 50 / WW 250
- 8 Postmyelo: WL 150 / WW 700
- 9 Felsenbein: WL 700 / WW 4000

키보드 숫자 0~9로도 바로 적용할 수 있습니다.

## v0.22 Window Preset Update

Preset:
- Skull: WL 25 / WW 95
- Lung: WL -400 / WW 1600
- Abdomen: WL 10 / WW 400
- Mediastinum: WL 10 / WW 400
- Bone: WL 300 / WW 2500
- Spine: WL 20 / WW 300
- Postmyelo: WL 200 / WW 1000
- Felsenbein: WL 500 / WW 4000

`View > Window Preset > Edit Windowing...`

직접 Window Level / Window Width 값을 입력하고 OK를 누르면 현재 영상에 즉시 적용됩니다.

## v0.23 WL / WW Overlay

상단의 WindowCenter / WindowWidth / Slice 표시 줄을 제거했습니다.

상단 버튼:
`Open DICOM | Open Folder | About | View | Reset WL`

영상 우측 하단:
- `WL`
- `WW`

Window Preset, Edit Windowing, Mouse Drag로 Window 값을 변경하면 우측 하단 Overlay도 즉시 갱신됩니다.

## v0.24 WL / WW Inline

영상 우측 하단 Window 정보는 한 줄로 표시됩니다.

예:
`WL: 45  WW: 130`

## v0.25 Pixel Probe

Viewer 영상 위에 마우스를 올리면 우측 하단에 현재 Pixel 정보를 표시합니다.

예:
`X: 313  Y: 288  Value: 29`
`WL: 45  WW: 130`

- X/Y는 DICOM image pixel 좌표입니다.
- MONOCHROME CT의 Value는 Rescale Slope / Intercept가 적용된 값(HU)을 사용합니다.
- RGB 영상은 `(R, G, B)` 형태로 표시합니다.
- 영상 영역 밖으로 마우스가 이동하면 Pixel 정보는 숨겨집니다.

## v0.26 HU Pixel Probe Fix

Pixel Probe를 QGraphicsView mouseMoveEvent가 아니라 viewport EventFilter에서 직접 감지하도록 변경했습니다.

CT / MONOCHROME:
`X: 313  Y: 288  HU: 43`
`WL: 45  WW: 130`

- X/Y는 DICOM Pixel 좌표
- HU는 Rescale Slope / Rescale Intercept가 적용된 값
- 영상 바깥에서는 Pixel Probe를 숨김
- Zoom/Pan 상태에서도 scene 좌표를 image pixel 좌표로 변환

## v0.27 HU Probe Fix

Pixel Probe 이벤트 처리를 `eventFilter` 대신 `QGraphicsView.viewportEvent()`로 변경했습니다.

표시:
`X: 313  Y: 288  HU: 43`
`WL: 45  WW: 130`

- viewport MouseMove에서 직접 좌표를 받습니다.
- mouseMoveEvent에서도 fallback으로 Pixel Probe를 갱신합니다.
- DICOM Pixel Array는 RescaleSlope/RescaleIntercept가 적용된 HU 배열을 사용합니다.

## v0.28 HU Probe - Pixmap Hover

Pixel Probe를 QGraphicsView mouse event 방식에서
실제 DICOM Image Pixmap의 hover event 방식으로 변경했습니다.

- 영상 위에 마우스가 올라가면 QGraphicsPixmapItem이 직접 X/Y 좌표를 전달
- CT: `X: 313  Y: 288  HU: 43`
- RGB: `X: 313  Y: 288  RGB: (R, G, B)`
- 영상 밖으로 벗어나면 probe 정보 숨김
- Zoom/Pan 여부와 관계없이 image local coordinate를 직접 사용

## v0.29 HU Probe Callback Fix

PySide6의 `QGraphicsPixmapItem`은 QObject가 아니므로 `Signal()`을 직접 사용할 수 없습니다.

기존:
`HoverPixmapItem.hover_moved = Signal(...)`

수정:
- HoverPixmapItem 생성 시 callback 함수 전달
- hoverMoveEvent -> `on_hover(x,y)` 직접 호출
- hoverLeaveEvent -> `on_leave()` 직접 호출

따라서 `Signal object has no attribute connect` 오류를 제거했습니다.

## v0.30 NumPy Import Fix

`viewer2d.py`의 HU Pixel Probe에서 `np.asarray()`를 사용하지만
`import numpy as np`가 누락되어 발생하던 NameError를 수정했습니다.

## v0.31 Rotate / Flip

`View > Rotate`

- Flip Horizontal — Ctrl+H
- Flip Vertical — Ctrl+F
- Rotate 90 Left — Ctrl+L
- Rotate 90 Right — Ctrl+R
- Restore Orientation — Ctrl+Alt+R

Rotate/Flip 후 자동으로 Fit to View를 수행합니다.
새 Series를 열면 원래 orientation으로 초기화됩니다.

## v0.32 Rotate Menu

Rotate 메뉴에서 Ctrl+ 단축키 표시 및 단축키 설정을 제거했습니다.

- Flip Horizontal
- Flip Vertical
- Rotate 90 Left
- Rotate 90 Right
- Restore Orientation

## v0.33 Menu Width Fix

View 및 하위 메뉴 최소 폭을 넓혔습니다.

- View: 180 px
- Window Preset: 190 px
- Rotate: 190 px

`Window Preset`, `Edit Windowing...`, `Restore Orientation` 등 긴 메뉴 문구가 잘리지 않도록 수정했습니다.

## v0.34 3D Reconstruction

`View > 3D`

- MPR
- MIP
- Volume Rendering

현재 선택된 Series의 Slice를 정렬하여 3D Volume으로 구성합니다.

사용 Tag:
- ImagePositionPatient
- ImageOrientationPatient
- PixelSpacing
- SliceThickness / SpacingBetweenSlices
- RescaleSlope / RescaleIntercept

추가 설치:
`pip install vtk`

MPR:
- Axial / Coronal / Sagittal plane 표시

MIP:
- GPU volume ray cast maximum intensity projection

Volume Rendering:
- GPU volume ray casting 기반 3D CT volume rendering

## v0.35 Low-resolution 3D Mode

Slice Thickness 또는 실제 Z spacing이 3.0 mm 이상이면
3D reconstruction 실행 전에 경고를 표시합니다.

예:
- Images: 36
- Slice Thickness: 5.00 mm
- Z Spacing: 5.00 mm

사용자가 `Open Low-resolution 3D`를 선택하면
MPR / MIP / Volume Rendering을 계속 사용할 수 있습니다.

3D Viewer 상단에는:
`Low-resolution source | 36 slices | ST 5.00 mm | Z 5.00 mm`

형태로 원본 해상도를 표시합니다.

이 모드는 없는 해부학 정보를 생성하지 않으며,
원본 voxel spacing을 그대로 사용합니다.

## v0.36 MPR Fix

기존 MPR은 Axial / Coronal / Sagittal plane을 하나의 3D renderer에
겹쳐 표시하여 서로 교차된 형태로 보였습니다.

수정:
- Axial / Coronal / Sagittal을 각각 독립 renderer로 분리
- 화면을 3등분하여 각 방향을 개별 표시
- 실제 PixelSpacing / Z spacing을 VTK image spacing으로 유지
- 각 MPR renderer는 parallel projection 사용
- MIP / Volume Rendering은 기존 단일 3D renderer 유지

5 mm NCCT에서는 Coronal/Sagittal이 낮은 Z 해상도 때문에
거칠게 보일 수 있지만, 세 plane이 서로 교차되어 보이는 문제는 제거됩니다.

## v0.37 Interactive MPR

MPR을 실제 3분할 Viewer 형태로 확장했습니다.

화면:
`Axial | Coronal | Sagittal`

기능:
- 각 화면 위에서 Mouse Wheel로 해당 방향 Slice 이동
- 현재 Slice 번호 표시
- 한 화면에서 Slice를 변경하면 다른 화면의 Crosshair도 동기화
- 화면을 클릭하면 해당 위치로 Crosshair 이동
- Axial / Coronal / Sagittal의 위치가 서로 연동
- PixelSpacing / Z spacing 유지
- Reset View로 중앙 Slice 및 카메라 초기화

5 mm NCCT처럼 Z 해상도가 낮은 Series는 Coronal/Sagittal이
거칠게 보일 수 있지만 원본 spacing을 그대로 사용합니다.

## v0.38 Interactive Thick-slab MIP

MPR 화면에서 `Slice / MIP Slab` 모드를 선택할 수 있습니다.

MIP Slab:
- Axial / Coronal / Sagittal 각각의 중심선 주변에 두 개의 점선 경계 표시
- 점선 경계를 마우스로 Drag하여 slab thickness 변경
- 경계를 넓히면 해당 방향으로 포함되는 Slice 수가 증가
- 포함된 voxel 중 Maximum 값을 사용하여 Thick-slab MIP 생성
- A / C / S 방향 slab thickness를 mm 단위로 독립 관리

예:
`Slab thickness A: 10.0 mm C: 10.0 mm S: 10.0 mm`

MPR 조작:
- Mouse Wheel: 해당 화면 Slice 이동
- Click: crosshair 이동
- Dotted slab boundary Drag: MIP thickness 조절

원본 voxel spacing을 사용하며 5 mm NCCT에서는 최소 slab 단위도
원본 z spacing에 제한됩니다.

## v0.39 Coronal/Sagittal Fix + High Quality MPR

수정:
- Coronal / Sagittal 화면 배치를 올바르게 수정
- 화면 순서: Axial | Sagittal | Coronal

MPR Quality:
- Original
- 1.0 mm Isotropic
- 0.7 mm Isotropic

Isotropic resampling은 scipy.ndimage.zoom(order=1)을 사용합니다.

예:
원본 spacing = 0.52 x 0.52 x 3.00 mm
1.0 mm Isotropic 선택 시:
1.0 x 1.0 x 1.0 mm volume으로 보간 후 MPR 표시

주의:
Resampling은 Coronal/Sagittal의 계단 현상과 픽셀 거칠기를 줄이지만
원본에 존재하지 않는 해부학적 정보를 복원하는 기능은 아닙니다.

추가 설치:
pip install scipy

## v0.40 Auto MPR Resolution

MPR 화면 순서:
`Axial | Coronal | Sagittal`

AISCAN 스타일의 일반적인 3-panel MPR 순서로 고정했습니다.

Quality 기본값:
`Auto`

Auto resolution 규칙:
- Max source spacing <= 0.7 mm -> 0.7 mm isotropic
- Max source spacing <= 3.0 mm -> 1.0 mm isotropic
- Max source spacing <= 5.0 mm -> 1.5 mm isotropic
- Max source spacing > 5.0 mm -> 2.0 mm isotropic

예:
source spacing = 0.52 x 0.52 x 3.00 mm
-> Auto = 1.0 mm isotropic

source spacing = 0.45 x 0.45 x 5.00 mm
-> Auto = 1.5 mm isotropic

Quality 메뉴에서는 Auto 외에 Original / 0.7 / 1.0 / 1.5 / 2.0 mm를
수동으로 선택할 수도 있습니다.

## v0.41 Automatic Superior Orientation

Coronal / Sagittal MPR의 vertical orientation을 DICOM Patient Coordinate
System 기준으로 자동 보정합니다.

사용 정보:
- ImagePositionPatient
- ImageOrientationPatient
- 실제 첫 Slice -> 마지막 Slice patient-space 이동 방향

DICOM LPS 좌표계에서 +Z는 Superior(Head)이므로,
volume index가 증가하는 방향과 patient-space +Z 방향의 관계를 계산합니다.

결과:
- Coronal: Head / Vertex가 항상 화면 위
- Sagittal: Head / Vertex가 항상 화면 위

함께 보정되는 기능:
- MPR image orientation
- Crosshair 위치
- 화면 Click으로 위치 이동
- MIP Slab 경계선 Drag
- Axial slice crosshair 위치

단순 고정 flip이 아니라 Series마다 실제 DICOM geometry를 확인하여
필요한 경우에만 상하 반전합니다.

## v0.42 DICOM Tree Slice Order

멀티스레드 Scanning/Indexing에서 `as_completed()` 완료 순서대로
파일이 Tree에 들어가던 문제를 수정했습니다.

각 Series의 DICOM은 다음 우선순위로 정렬됩니다.

1. ImagePositionPatient + ImageOrientationPatient 기반 실제 Slice 위치
2. InstanceNumber
3. 파일명

따라서 Tree의 `#1, #2, #3 ...` 순서가 실제 Series slice 순서와
일치하도록 정렬됩니다.

## v0.43 3D MIP Window / Resolution

3D MIP mode에 전용 조절 기능을 추가했습니다.

MIP Quality:
- Auto
- Original
- 0.7 mm Isotropic
- 1.0 mm Isotropic
- 1.5 mm Isotropic
- 2.0 mm Isotropic

Auto:
- max source spacing <= 0.7 mm -> 0.7 mm
- max source spacing <= 3.0 mm -> 1.0 mm
- max source spacing <= 5.0 mm -> 1.5 mm
- 그 이상 -> 2.0 mm

MIP Window:
- WL 직접 입력
- WW 직접 입력
- Reset MIP WL
- 기본 CTA MIP: WL 300 / WW 700

Rendering quality:
- VTK GPU Maximum Intensity Projection
- Linear interpolation
- Reduced ray sample distance
- 8x multisampling

주의:
Isotropic resampling은 display/reconstruction을 부드럽게 하지만
원본에 존재하지 않는 해부학적 정보를 새로 생성하지 않습니다.

## v0.44 Fast Import Pipeline

DICOM Import / Scanning / Indexing 성능을 크게 개선했습니다.

1. Persistent header cache
- `%LOCALAPPDATA%/PythonDICOMViewer/dicom_index_v1.sqlite3`
- path + file size + modified time이 동일한 DICOM은 다음 Import에서
  pydicom header를 다시 읽지 않습니다.
- 동일 폴더 재오픈은 특히 큰 폭으로 빨라집니다.

2. Faster initial indexing
- PixelData는 Indexing 단계에서 읽지 않음
- 필요한 Header Tag만 specific_tags로 읽음
- 최대 32개 I/O worker
- Future/as_completed 대신 ThreadPoolExecutor.map 사용
- cache write는 DICOM마다 하지 않고 한 번의 batch transaction으로 처리

3. Progress UI throttling
- 기존에는 거의 모든 DICOM마다 QApplication.processEvents() 실행
- 이제 약 80 ms 간격으로만 Progress UI 갱신
- UI 갱신 때문에 Indexing이 느려지는 현상을 크게 감소

4. Lazy DICOM Tree
- Import 즉시 수천 개의 file QTreeWidgetItem을 만들지 않음
- Patient / Study / Series Tree를 먼저 즉시 생성
- 실제 Series를 선택/확장할 때만 해당 Series의 DICOM file node 생성

5. Faster Series Loading
- pydicom.dcmread(defer_size=4096)
- PixelData는 실제 Slice가 렌더링될 때까지 deferred
- 최대 16 worker로 Series dataset 병렬 load
- 16 Slice 단위로 Progress 갱신

첫 Import는 디스크/CPU 환경에 따라 기존보다 수 배 빨라질 수 있고,
같은 폴더의 두 번째 Import부터는 metadata cache 효과로 더 빠릅니다.

## v0.45 MIP = MPR Thick-slab MIP

`View > 3D` 구조를 정리했습니다.

- MPR
  - Axial / Coronal / Sagittal 3-panel
  - 일반 Slice 모드

- MIP
  - 동일한 Axial / Coronal / Sagittal 3-panel
  - `MIP Slab` 모드가 자동 활성화
  - 점선 slab boundary를 Drag하여 thickness 조절
  - 각 방향에서 포함된 voxel의 Maximum Intensity Projection 표시
  - Mouse Wheel로 Slice 이동
  - Crosshair 동기화
  - Auto MPR Resolution 사용 가능

- Volume Rendering
  - 기존 GPU 3D Volume Rendering 유지

기존 별도 회전형 3D GPU MIP 화면은 메뉴 동작에서 제거했습니다.

## v0.46 DICOM Tree Instance Order

DICOM Tree 표시 순서를 사용자에게 직관적인 방식으로 변경했습니다.

Series 내부 표시 순서:
1. Instance Number 오름차순
2. Instance Number가 없으면 ImagePositionPatient 기반 Slice 위치
3. 둘 다 없으면 파일명

중요:
- DICOM Tree / 2D Series 목록은 Instance Number 순으로 표시
- MPR / MIP / Volume Rendering의 3D Volume 생성은 기존처럼
  ImagePositionPatient + ImageOrientationPatient 기반 geometry 정렬을 사용

따라서 Tree는 #1, #2, #3 ... 순으로 보기 쉬워지고,
3D reconstruction의 spatial ordering 정확도는 유지됩니다.

## v0.47 Top Bar Cleanup

상단 Toolbar에서 `About` 버튼을 제거했습니다.

현재 상단 버튼:
`Open DICOM | Open Folder | View | Reset WL`

## v0.48 DICOM File Click Navigation

DICOM Tree에서 개별 DCM 파일을 클릭했을 때 해당 파일로 직접 이동합니다.

동작:
- Series 항목 클릭 -> 해당 Series의 첫 Slice
- DCM 파일 항목 클릭 -> 정확히 클릭한 DCM Slice
- 이미 같은 Series가 로드된 경우 -> Series 재로딩 없이 즉시 Slice 이동
- 다른 Series의 DCM을 클릭한 경우 -> 해당 Series 로드 후 선택한 DCM으로 이동

Tree의 표시 순서와 Viewer의 geometry 정렬 순서가 달라도
파일 경로를 직접 매칭하므로 올바른 DCM을 표시합니다.

## v0.49 Reset View

상단 `Reset WL` 버튼을 `Reset View`로 변경했습니다.

Reset View를 누르면 현재 Slice는 유지한 상태로 다음 항목을 모두 초기화합니다.

- Window Level
- Window Width
- Rotate
- Flip Horizontal
- Flip Vertical
- Zoom
- Pan
- Viewer Fit

즉 현재 Series를 처음 열었을 때의 표시 상태로 복원합니다.

## v0.50 Horizontal Scrollbars

DICOM Tree와 DICOM Tags에 가로 스크롤을 추가했습니다.

- DICOM Tree: 긴 DCM 파일명을 하단 가로 스크롤로 확인
- DICOM Tags: 긴 UID/Value를 하단 가로 스크롤로 확인
- 긴 텍스트를 강제로 ... 처리하지 않고 전체 폭 유지
- ScrollBar는 내용이 패널 폭보다 길 때만 자동 표시

## v0.51 Horizontal Scroll Fix

`metadata_panel.py`에서 `Qt.ScrollBarAsNeeded`를 사용하면서
`Qt` import가 누락되어 발생하던 NameError를 수정했습니다.

추가:
`from PySide6.QtCore import Qt`

## v0.52 Panel Horizontal Scroll

스크롤 위치를 명확하게 분리했습니다.

- Image Viewer
  - Horizontal scrollbar 제거
  - Vertical scrollbar 제거

- DICOM Tree
  - 패널 하단 horizontal scrollbar 항상 표시
  - 긴 DCM 파일명을 좌우로 이동하여 전체 확인
  - Tree column을 content width 기준으로 유지

- DICOM Tags
  - 패널 하단 horizontal scrollbar 항상 표시
  - Tag ID / Description / Value 전체를 좌우 이동하여 확인
  - Value column을 충분히 넓게 유지하여 UID 등이 잘리지 않도록 처리

## v0.53 Panel Scroll Import Fix

`series_tree.py`에서 `QHeaderView.ResizeToContents`를 사용하면서
`QHeaderView` import가 누락되어 발생하던 NameError를 수정했습니다.

추가:
`from PySide6.QtWidgets import QHeaderView`

## v0.54 Smooth Scroll

- DICOM Tree / DICOM Tags: ScrollPerPixel 적용
- 가로 스크롤은 필요할 때만 표시
- 스크롤바를 얇은 10px rounded 스타일로 변경
- Image Viewer: 가로 스크롤 숨김, 세로 스크롤은 필요할 때 자동 표시

## v0.55 DICOM Tags Horizontal Scroll

DICOM Tags의 긴 Value를 좌우로 확인할 수 있도록 가로 스크롤 동작을 보강했습니다.

- Horizontal ScrollBar: As Needed
- Tag ID width: 120 px
- Description width: 220 px
- Value width: 420 px
- Header Stretch 해제
- 긴 UID / ImagePositionPatient / ImageOrientationPatient / Window 값 등을
  좌우 스크롤하여 전체 확인 가능
- ScrollPerPixel 유지

## v0.56 Clean Scrollbar

스크롤바의 빈 track 영역이 별도의 회색 띠처럼 보이지 않도록 수정했습니다.

Dark mode:
- Track: DICOM Tree/Tags 배경과 동일한 #242424
- Handle만 #666666으로 표시
- 폭/높이 8 px

Light mode:
- Track: panel 배경과 동일한 white
- Handle만 연한 회색으로 표시

공통:
- Scrollbar arrow 제거
- 빈 page 영역을 panel 배경과 동일하게 처리
- Handle rounded 처리

## v0.57 Lazy Series Loading

Series 전환 속도를 개선하기 위해 2D Viewer의 로딩 구조를 변경했습니다.

기존:
- Series 클릭
- 해당 Series의 모든 DICOM을 dcmread
- 전체 Dataset 생성
- Rendering progress 완료 후 첫 영상 표시

v0.57:
- Series 클릭
- 선택된 Slice DICOM 1장만 즉시 dcmread
- 바로 화면 표시
- 나머지 Slice는 마우스 휠/Tree 클릭으로 접근할 때 개별 로드
- 최근 Dataset 16개와 HU 48개를 메모리에 LRU cache

따라서 일반 Series 이동 시 상단의
`Rendering 96 / 164 ...`
진행 과정이 더 이상 필요하지 않습니다.

3D:
- MPR / MIP / Volume Rendering을 실행할 때만 전체 Series가 필요하므로
  그 시점에 전체 DICOM을 로드하고 `Preparing 3D` progress를 표시합니다.

효과:
- 수백 장 Series 간 전환 체감 속도 대폭 개선
- 처음 보는 Series도 첫 Slice 표시까지 기다리는 시간이 크게 감소
- 다시 본 Slice는 Dataset/HU cache로 빠르게 표시

## v0.58 Faster Initial Scanning / Indexing

최초 DICOM Import 속도를 추가 최적화했습니다.

Scanning:
- 기존 os.scandir 재귀 탐색 유지
- jpg/png/txt/pdf/xlsx/zip/nii 등 명백한 비-DICOM 파일을
  pydicom Indexing 전에 즉시 제외
- 확장자가 없거나 알 수 없는 파일은 DICOM 가능성이 있으므로 유지
- loop 내부 append/local lookup 최적화

Header Cache:
- 기존에는 cache 조회 전에 모든 candidate file을 os.stat
- 이제 SQLite cache에 실제 존재하는 path만 os.stat
- 처음 Import하는 폴더에서는 불필요한 파일 stat 호출을 줄임

Indexing:
- 파일 개수에 따라 Thread worker 자동 조절
  - <300 files: 최대 16
  - <1500 files: 최대 28
  - >=1500 files: 최대 36
- Progress callback batch를 64 -> 128 files로 완화
- UI progress refresh를 80 ms -> 120 ms로 완화

기존 기능 유지:
- PixelData는 Indexing에서 읽지 않음
- 필요한 header tag만 읽음
- Persistent SQLite header cache
- Lazy Tree
- Lazy Series loading
- MPR/MIP/3D에서만 필요 시 전체 Series load

## v0.59 DICOM Tag Header

DICOM Tags 첫 번째 컬럼명을 변경했습니다.

- 기존: Tag ID
- 변경: (Group, Element)

실제 Tag 값 표시는 기존과 동일하게
`(0010,0020)`, `(0020,000D)` 형식을 유지합니다.

## v0.60 DICOM Tags Column Alignment

DICOM Tags Header와 Row의 column geometry를 동일하게 맞췄습니다.

- (Group, Element): 120 px
- Description: 165 px
- Value: 420 px
- Header / Row 모두 Left + Vertical Center 정렬
- Header resize mode를 Fixed로 통일
- Horizontal scroll은 유지

따라서 Header 아래의 실제 값 시작 위치가 정확히 맞습니다.

## v0.61 DICOM Tag Count

DICOM Tags의 `Show all tags` 옆에 전체 Tag 개수를 표시합니다.

예:
`Show all tags    Total Tags: 142`

- 현재 선택된 DICOM 기준
- Slice 변경 시 자동 갱신
- 다른 DICOM/Series 선택 시 자동 갱신
- Sequence 내부 Tag까지 포함하기 위해 `Dataset.iterall()` 기준으로 계산

## v0.62 Inline Tag Count

`Show all tags`와 `Total Tags`를 같은 줄에 가로 배치했습니다.

표시:
`Show all tags    Total Tags: 142`

## v0.63 DICOM Tags Layout Fix

`Show all tags / Total Tags` 아래에 생기던 큰 공백을 제거했습니다.

원인:
- `layout.addStretch()`가 checkbox row와 table 사이에 남아 있었음

수정:
- 불필요한 stretch 제거
- Table이 checkbox row 바로 아래에 배치
- Table은 남은 세로 공간 전체 사용
- 중복 Header resize 설정 제거
- v0.60의 column alignment 유지

## v0.64 Image Viewer Vertical Scrollbar

가운데 DICOM Image Viewer에 세로 스크롤바를 항상 표시하도록 변경했습니다.

- Horizontal scrollbar: 숨김
- Vertical scrollbar: 항상 표시
- 기존 얇은 scrollbar theme 유지
- 확대/이동된 영상에서 위아래 위치 이동 가능
- vertical single step: 18 px

## v0.65 Slice Navigator Scrollbar

가운데 영상 우측의 세로 Scrollbar를 화면 Pan용이 아닌
Series Slice 이동 전용 Navigator로 변경했습니다.

동작:
- Scrollbar top = 첫 Slice
- Scrollbar bottom = 마지막 Slice
- Scrollbar drag로 수백 장 Series를 빠르게 이동
- Mouse wheel Slice 이동과 scrollbar 위치 자동 동기화
- DICOM Tree file 클릭과 scrollbar 위치 자동 동기화
- Slice 표시 `Slice: current/total`과 자동 동기화

성능:
- Drag 중 모든 중간 DICOM을 전부 decode하지 않도록 35 ms throttle 적용
- Lazy Series Loading과 함께 동작
- 실제 도달한 Slice만 필요한 시점에 읽음

QGraphicsView 자체의 내부 vertical scrollbar는 숨겼습니다.

## v0.66 Default DICOM Tags

기본 DICOM Tags 목록에 다음 항목을 추가했습니다.

- (0010,0040) Patient Sex
- (0010,1010) Patient Age
- (0008,0021) Series Date
- (0008,0031) Series Time

`Show all tags`를 체크하지 않은 상태에서도 표시됩니다.
Tag가 DICOM에 없으면 Value는 빈 값으로 표시됩니다.

## v0.67 Default Acquisition Tags

기본 DICOM Tags에 다음 항목을 추가했습니다.

- (0008,0022) Acquisition Date
- (0008,0032) Acquisition Time

`Show all tags`를 체크하지 않은 상태에서도 표시됩니다.
