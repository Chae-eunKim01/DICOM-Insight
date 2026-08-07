class VolumeViewer:
    """
    v0.4 구현 예정.
    VTK GPU Volume Rendering을 담당합니다.
    """
    def __init__(self):
        self.volume=None

    def set_volume(self,volume):
        self.volume=volume
