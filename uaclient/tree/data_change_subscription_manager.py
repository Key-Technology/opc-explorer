import logging

from asyncua import ua
from asyncua.sync import SyncNode

from uawidgets.utils import trycatchslot

logger = logging.getLogger(__name__)


class DataChangeSubscriptionManager:

    def __init__(self, window, uaclient):
        self.window = window
        self.uaclient = uaclient
        self._subscribed_nodes = []

    def clear(self):
        self._subscribed_nodes = []

    def show_error(self, *args):
        self.window.show_error(*args)

    @trycatchslot
    def _subscribe(self, node=None):
        if not isinstance(node, SyncNode):
            node = self.window.get_current_node()
            if node is None:
                return
        if node in self._subscribed_nodes:
            return
        try:
            self.uaclient.subscribe_datachange(node, self.window._subhandler)

        except Exception as ex:
            if type(ex) is ua.uaerrors.BadAttributeIdInvalid:
                return
            return ex

        self._subscribed_nodes.append(node)

    @trycatchslot
    def _unsubscribe(self, node):
        if node is None:
            node = self.window.get_current_node()
        try:
            self._subscribed_nodes.remove(node)
            self.uaclient.unsubscribe_datachange(node)
        except Exception as ex:
            if type(ex) is ValueError:
                return
            logger.error(ex)

    def _update_subscription_model(self, node, value, timestamp):
        i = 0
        while self.model.item(i):
            item = self.model.item(i)
            if item.data() == node:
                it = self.model.item(i, 1)
                it.setText(value)
                it_ts = self.model.item(i, 2)
                it_ts.setText(timestamp)
            i += 1
