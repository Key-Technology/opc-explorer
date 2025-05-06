
from PyQt5.QtWidgets import QTreeView
# from uaclient.tree.expand_collapse_manager import ExpandCollapseManager
from PyQt5.QtCore import pyqtSignal, Qt, QModelIndex

from qasync import asyncSlot


class OPCTreeView(QTreeView):
    shift_click_expand = pyqtSignal(QModelIndex)
    shift_click_collapse = pyqtSignal(QModelIndex)

    def __init__(self, parent):
        super().__init__(parent)
        self.hasShiftExpanded = False
        self.hasShiftCollapsed = False

    def mousePressEvent(self, event):
        idx = self.indexAt(event.pos())
        if idx.isValid() and event.modifiers() & Qt.ShiftModifier:

            if self.isExpanded(idx):

                self.hasShiftCollapsed = True
                self.shift_click_collapse.emit(idx)
            else:
                self.hasShiftExpanded = True
                self.shift_click_expand.emit(idx)
        else:
            super().mousePressEvent(event)