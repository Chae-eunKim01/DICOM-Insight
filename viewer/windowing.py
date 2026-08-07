from dataclasses import dataclass
from utils.constants import DEFAULT_WINDOW_WIDTH,DEFAULT_WINDOW_LEVEL,MIN_WINDOW_WIDTH

@dataclass
class WindowState:
    width:float=DEFAULT_WINDOW_WIDTH
    level:float=DEFAULT_WINDOW_LEVEL

    def update(self,dx,dy):
        self.width=max(MIN_WINDOW_WIDTH,self.width+dx*2.0)
        self.level=self.level+dy*2.0
