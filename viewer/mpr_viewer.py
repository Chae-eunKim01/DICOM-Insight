class MPRViewer:
    """
    v0.2 구현 예정.
    SimpleITK/VTK 기반 Axial, Coronal, Sagittal MPR를 담당합니다.
    """
    def __init__(self):
        self.volume=None

    def set_volume(self,volume):
        self.volume=volume
