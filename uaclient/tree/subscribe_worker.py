import logging
from PyQt5.QtCore import QThread

logger = logging.getLogger(__name__)


class SubscribeWorker(QThread):
    def __init__(self, idx, model, subscription_handler):
        super().__init__()
        self.idx = idx
        self.model = model
        self.uaclient = model.uaclient
        self.data_change_manager = model.data_change_manager
        self.subscription_handler = subscription_handler
        self.last_unsubscribed = subscription_handler.last_unsubscribed

    def run(self):
        self.subscription_handler.expanded_lock.lock()
        self.subscription_handler.is_expanded = True
        self.subscription_handler.expanded_lock.unlock()

        self.subscription_handler.thread_running_lock.lock()
        idx = self.idx
        item = self.model.itemFromIndex(idx)
        i = 0
        while True:
            child = item.child(i)
            if child is None or i == self.last_unsubscribed:
                break
            index = item.child(i).index()
            childNodeId = self.model.data(index.sibling(index.row(), 2))
            childNode = self.uaclient.client.get_node(childNodeId)
            res = self.data_change_manager._subscribe(childNode)
            if res:
                logger.error(res)
                break
            i = i + 1
        self.last_unsubscribed = -1
        self.subscription_handler.thread_running_lock.unlock()
