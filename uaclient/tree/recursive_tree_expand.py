from PyQt5.QtCore import Qt, QThread


class RecursiveTreeExpand(QThread):

    def __init__(self, idx, treeView, manager):
        super().__init__()
        self.idx = idx
        self.treeView = treeView
        self.has_expanded = treeView.has_expanded
        self.manager = manager

    def run(self):
        self.manager.expand_collapse_managers_lock.lock()
        item = self.treeView.model().itemFromIndex(self.idx)
        text = item.text()
        self.treeView.model().fetchMore(self.idx)
        self.has_expanded.emit(self.idx)
        item.setText("loading...")
        children = []
        children.append(item)
        while len(children) > 0:
            child_item = children[0]
            i = 0
            if self.manager.collapse_thread.isRunning():
                break
            while True:
                child = child_item.child(i)
                if child is None:
                    break
                index = child.index()

                node = child.data(Qt.UserRole)
                if len(node.get_children_descriptions()) > 0:
                    if self.manager.collapse_thread.isRunning():
                        break
                    children.append(child)
                    self.treeView.model().fetchMore(index)
                    self.has_expanded.emit(index)
                i = i + 1
            children.pop(0)
        item.setText(text)
        self.manager.expand_collapse_managers_lock.unlock()
