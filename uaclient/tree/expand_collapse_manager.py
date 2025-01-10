from uaclient.tree.recursive_tree_expand import RecursiveTreeExpand
from uaclient.tree.recursive_tree_collapse import RecursiveTreeCollapse
from PyQt5.QtCore import QMutex


class ExpandCollapseManager:
    def __init__(self, idx, treeView):
        self.expand_thread = RecursiveTreeExpand(idx, treeView, self)
        self.collapse_thread = RecursiveTreeCollapse(idx, treeView, self)
        self.expand_collapse_managers_lock = QMutex()
