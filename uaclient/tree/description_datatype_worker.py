from PyQt5.QtCore import QRunnable

from asyncua.common.ua_utils import data_type_to_string

from asyncua import ua


class DescriptionDatatypeWorker(QRunnable):
    def __init__(self, node, description, data_type):
        super().__init__()
        self.node = node
        self.description = description
        self.data_type = data_type

    def run(self):
        attrs = self.node.read_attributes(
            [ua.AttributeIds.Description, ua.AttributeIds.DataType]
        )
        self.description.setText(attrs[0].Value.Value.Text)
        if attrs[1].Value.Value:
            self.data_type.setText(data_type_to_string(attrs[1].Value.Value))
