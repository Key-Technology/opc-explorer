from PyQt5.QtGui import QStandardItem


class NodeValueItem(QStandardItem):
    def __init__(self, value):
        super(NodeValueItem, self).__init__(value)

    def update_value(self, node, val, data):
        self.setText(str(val))
