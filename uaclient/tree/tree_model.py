from PyQt5.QtCore import Qt


from uawidgets.tree_widget import TreeViewModel


class TreeModel(TreeViewModel):

    def __init__(self):
        super().__init__()
        self.node_with_loaded_children = []

    def fetchMore(self, idx):
        parent = self.itemFromIndex(idx)
        if parent in self.node_with_loaded_children or not parent:
            return
        if parent:
            self._fetchMore(parent)

    def _fetchMore(self, parent):
        try:
            node = parent.data(Qt.UserRole)
            descs = node.get_children_descriptions()
            descs.sort(key=lambda x: x.BrowseName)
            added = []
            for desc in descs:
                if desc.NodeId not in added:
                    self.add_item(desc, parent)
                    added.append(desc.NodeId)
            self.node_with_loaded_children.append(parent)
        except Exception as ex:
            self.error.emit(ex)
            raise
