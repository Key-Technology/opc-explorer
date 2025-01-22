from PyQt5.QtCore import pyqtSignal, QObject


class NodeSubscriptionSignal(QObject):
    signal = pyqtSignal(object, object, str)
