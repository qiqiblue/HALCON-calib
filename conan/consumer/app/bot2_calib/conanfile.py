import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "share" / "conan"))

from common import AbTeaConanBase


class Bot2CalibDependencies(AbTeaConanBase):
    def requirements(self):
        self.common_requirements()
        self.requires("abc/0.8.16")
        self.requires("realman/1.1.1.t2")
        self.requires("woosh/1.3.17")
        # bot2 注册 pipeline 工具步骤, pipeline 的 Qt UI 依赖 QtNodes.
        self.requires("qtnodes/3.0.16")
