from PyQt5.QtWidgets import QTreeView
from uaclient.tree.expand_collapse_manager import ExpandCollapseManager
from PyQt5.QtCore import pyqtSignal, Qt


class OPCTreeView(QTreeView):
    shift_click_expand = pyqtSignal(object)
    shift_click_collapse = pyqtSignal(object)
    has_expanded = pyqtSignal(object)
    has_collapsed = pyqtSignal(object)

    def __init__(self, parent):
        super().__init__(parent)
        self.expand_collapse_managers = {}
        self.has_expanded.connect(self.expand_item)
        self.has_collapsed.connect(self.collapse_item)
        self.shift_click_expand.connect(self.custom_expand)
        self.shift_click_collapse.connect(self.custom_collapse)

    def mousePressEvent(self, event):
        idx = self.indexAt(event.pos())
        if idx.isValid() and event.modifiers() & Qt.ShiftModifier:
            if self.isExpanded(idx):
                self.shift_click_collapse.emit(idx)
            else:
                self.shift_click_expand.emit(idx)
        else:
            super().mousePressEvent(event)

    def custom_expand(self, idx):
        if idx not in self.expand_collapse_managers:
            manager = ExpandCollapseManager(idx, self)
            self.expand_collapse_managers[idx] = manager
        elif self.expand_collapse_managers[idx].collapse_thread.isRunning():
            self.expand_collapse_managers[idx].collapse_thread.wait()
        self.expand_collapse_managers[idx].expand_thread.start()

    def expand_item(self, idx):
        self.expand(idx)

    def collapse_item(self, idx):
        self.setExpanded(idx, False)

    def custom_collapse(self, idx):
        if idx not in self.expand_collapse_managers:
            manager = ExpandCollapseManager(idx, self)
            self.expand_collapse_managers[idx] = manager
        self.expand_collapse_managers[idx].collapse_thread.start()
