from PyQt5.QtCore import QObject, QMutex
from uaclient.tree.subscribe_worker import SubscribeWorker
from uaclient.tree.unsubscribe_worker import UnsubscribeWorker


class SubscriptionHandler(QObject):

    def __init__(self, model, idx):
        super().__init__()
        self.model = model
        self.idx = idx
        self.is_expanded = False
        self.last_unsubscribed = -1
        self.thread_running_lock = QMutex()
        self.expanded_lock = QMutex()
        self.subscribe_thread = SubscribeWorker(idx, model, self)
        self.unsubscribe_thread = UnsubscribeWorker(idx, model, self)
