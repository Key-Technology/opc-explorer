from PyQt5.QtCore import QThread


class RecursiveTreeCollapse(QThread):

    def __init__(self, idx, treeView, manager):
        super().__init__()
        self.idx = idx
        self.treeView = treeView
        self.manager = manager

    def run(self):
        self.manager.expand_collapse_managers_lock.lock()
        self.recursive_collapse(self.idx)
        self.manager.expand_collapse_managers_lock.unlock()

    def recursive_collapse(self, idx):
        child_item = self.treeView.model().itemFromIndex(idx)
        i = 0
        while True:
            child = child_item.child(i)
            if child is None:
                break
            index = child.index()
            self.treeView.has_collapsed.emit(index)
            self.recursive_collapse(index)
            i = i + 1
        self.treeView.has_collapsed.emit(idx)
