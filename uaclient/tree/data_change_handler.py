from datetime import datetime

from PyQt5.QtCore import pyqtSignal, QObject


class DataChangeHandler(QObject):

    def __init__(self, node_signal_dict):
        super().__init__()
        self.node_signal_dict = node_signal_dict

    data_change_fired = pyqtSignal(object, str, str)

    def datachange_notification(self, node, val, data):
        if data.monitored_item.Value.SourceTimestamp:
            dato = data.monitored_item.Value.SourceTimestamp.isoformat()
        elif data.monitored_item.Value.ServerTimestamp:
            dato = data.monitored_item.Value.ServerTimestamp.isoformat()
        else:
            dato = datetime.now().isoformat()
        self.node_signal_dict[str(node)].signal.emit(node, val, dato)
