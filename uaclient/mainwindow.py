#! /usr/bin/env python3

import sys
import asyncio
import contextlib
import collections
import functools
import logging
from typing import Any, Dict, List

from qasync import QEventLoop, QApplication, asyncClose, asyncSlot
from PyQt5.QtCore import (
    QCoreApplication,
    QSettings,
    pyqtSignal,
    QObject,
    QTimer,
    QItemSelection,
    QSignalBlocker,
)
from PyQt5.QtGui import QIcon
from PyQt5.QtWidgets import QMainWindow, QWidget, QAbstractItemView, QDialog

from asyncua import Client, Node
from asyncua import crypto
from asyncua.common.subscription import Subscription, DataChangeNotif
from asyncua.ua import NodeId, AttributeIds, DataValue, MessageSecurityMode
import asyncua.ua.uaerrors

# must be here for resources even if not used
from uawidgets import resources  # noqa: F401

from uaclient.mainwindow_ui import Ui_MainWindow
from uaclient import tree_ui
from uaclient import attrs_ui
from uaclient.connection_dialog import ConnectionDialog
from uaclient.application_certificate_dialog import ApplicationCertificateDialog

logger = logging.getLogger(__name__)

_SubscriptionData = collections.namedtuple("_SubscriptionData", ["handle", "signal"])


class _SubscriptionSignal(QObject):
    signal = pyqtSignal(DataValue)


class _DataChangeHandler:
    def __init__(self, _callback) -> None:
        self._callback = _callback

    async def datachange_notification(
        self, node: Node, _value: Any, data: DataChangeNotif
    ):
        await self._callback(node, data.monitored_item.Value)


class Window(QMainWindow):
    def __init__(self, *, use_settings=True) -> None:
        super().__init__()

        self._use_settings = (
            use_settings  # Support not using settings files (for tests)
        )

        self._uaclient: Client = None
        self._ua_subscription: Subscription = None
        self._ua_subscription_data: Dict[NodeId, _SubscriptionData] = dict()
        self._application_certificate_path = None
        self._application_private_key_path = None
        self._user_certificate_path = None
        self._user_private_key_path = None
        self._security_mode = None
        self._security_policy = None
        self._address_list: List[str] = []

        self._setup_settings()
        self._setup_ui()
        self._load_state()

    @asyncClose
    async def closeEvent(self, event):
        self._save_state()
        await self._disconnect()
        event.accept()

    def _setup_settings(self):
        # setup QSettings for application and get a settings object
        QCoreApplication.setOrganizationName("Key Technology")
        QCoreApplication.setApplicationName("OPC Explorer")
        self._settings = QSettings()

    def _setup_ui(self):
        self._ui = Ui_MainWindow()
        self._ui.setupUi(self)
        self.setWindowIcon(QIcon(":/network.svg"))

        # we only show statusbar in case of errors
        self._ui.statusBar.hide()

        self._setup_ui_tree()
        self._setup_ui_attrs()
        self._setup_ui_dock()
        self._setup_ui_connect_disconnect()
        self._setup_ui_connection_dialog()
        self._setup_ui_application_certificate_dialog()

    def _setup_ui_tree(self):
        self._model = tree_ui.OpcTreeModel(
            self._ui.treeView, [AttributeIds.DisplayName, AttributeIds.Value]
        )
        self._model.item_added.connect(self._subscribe_to_node)
        self._model.item_removed.connect(self._unsubscribe_from_node)

        self._ui.treeView.header().setSectionResizeMode(0)
        self._ui.treeView.header().setStretchLastSection(True)
        self._ui.treeView.setSelectionBehavior(QAbstractItemView.SelectRows)

    def _setup_ui_attrs(self):
        self._attrs_ui = attrs_ui.AttrsWidget(
            self._ui.attrView, self._ua_subscription_data
        )
        self._attrs_ui.error.connect(self._show_error)

        self._ui.treeView.selectionModel().selectionChanged.connect(
            self._handle_selection
        )
        self._ui.attrRefreshButton.clicked.connect(self._attrs_ui.reload)

    def _setup_ui_dock(self):
        # fix stuff imposible to do in qtdesigner
        # remove dock titlebar for addressbar
        w = QWidget()
        self._ui.addrDockWidget.setTitleBarWidget(w)

    def _setup_ui_connect_disconnect(self):
        self._ui.connectButton.clicked.connect(self._connect)
        self._ui.actionConnect.triggered.connect(self._connect)

        self._ui.disconnectButton.clicked.connect(self._disconnect)
        self._ui.actionDisconnect.triggered.connect(self._disconnect)

    def _setup_ui_connection_dialog(self):
        self._ui.connectOptionButton.clicked.connect(self._show_connection_dialog)

    def _setup_ui_application_certificate_dialog(self):
        self._ui.actionClient_Application_Certificate.triggered.connect(
            self._show_application_certificate_dialog
        )

    def _save_state(self):
        if not self._use_settings:
            return

        self._settings.setValue("main_window/geometry", self.saveGeometry())
        self._settings.setValue("main_window/state", self.saveState())
        self._settings.setValue("main_window/address_list", self._address_list)
        self._settings.setValue(
            "tree_view/header/state", self._ui.treeView.header().saveState()
        )

        self._settings.setValue(
            "opc_client/certificate", self._application_certificate_path
        )
        self._settings.setValue("opc_client/key", self._application_private_key_path)
        self._settings.setValue(
            "opc_client/user_certificate", self._user_certificate_path
        )
        self._settings.setValue("opc_client/user_key", self._user_private_key_path)
        self._settings.setValue("opc_client/security_mode", self._security_mode)
        self._settings.setValue("opc_client/security_policy", self._security_policy)

        self._settings.beginGroup("attrs_widget")
        self._attrs_ui.save_state(self._settings)
        self._settings.endGroup()

    def _load_state(self):
        if not self._use_settings:
            return

        data = self._settings.value("main_window/geometry", None)
        if data is not None:
            self.restoreGeometry(data)

        data = self._settings.value("main_window/state", None)
        if data is not None:
            self.restoreState(data)

        self._address_list = self._settings.value("main_window/address_list", [])
        for addr in self._address_list:
            self._ui.addrComboBox.insertItem(100, addr)

        data = self._settings.value("tree_view/header/state", None)
        if data is not None:
            self._ui.treeView.header().restoreState(data)

        self._application_certificate_path = self._settings.value(
            "opc_client/certificate", None
        )
        self._application_private_key_path = self._settings.value(
            "opc_client/key", None
        )
        self._user_certificate_path = self._settings.value(
            "opc_client/user_certificate", None
        )
        self._user_private_key_path = self._settings.value("opc_client/user_key", None)
        self._security_mode = self._settings.value("opc_client/security_mode", None)
        self._security_policy = self._settings.value("opc_client/security_policy", None)

        self._settings.beginGroup("attrs_widget")
        self._attrs_ui.load_state(self._settings)
        self._settings.endGroup()

    async def _handle_subscription_data(self, node: Node, value: DataValue) -> None:
        # Suppress KeyError because there might be a race condition
        # between unsubscribing and receiving data, i.e. we might
        # receive data for a subscription we just removed.
        with contextlib.suppress(KeyError):
            self._ua_subscription_data[node.nodeid].signal.signal.emit(value)

    @asyncSlot(tree_ui.OpcTreeItem)
    async def _subscribe_to_node(self, item: tree_ui.OpcTreeItem):
        with contextlib.suppress(
            asyncua.ua.uaerrors.BadAttributeIdInvalid,
            asyncua.ua.uaerrors.BadTooManyMonitoredItems,
        ):
            subscription_data = _SubscriptionData(
                await self._ua_subscription.subscribe_data_change(item.node),
                _SubscriptionSignal(self),
            )
            self._ua_subscription_data[item.node.nodeid] = subscription_data
            subscription_data.signal.signal.connect(
                functools.partial(item.set_data, AttributeIds.Value)
            )

    @asyncSlot(tree_ui.OpcTreeItem)
    async def _unsubscribe_from_node(self, item: tree_ui.OpcTreeItem):
        try:
            subscription_data = self._ua_subscription_data.pop(item.node.nodeid)
        except KeyError:
            return

        # Disconnect signal from all slots, and unsubscribe from the OPC data
        subscription_data.signal.signal.disconnect()
        await self._ua_subscription.unsubscribe(subscription_data.handle)

    @asyncSlot(QItemSelection, QItemSelection)
    async def _handle_selection(
        self, _selected: QItemSelection, _deselected: QItemSelection
    ):
        current_index = self._ui.treeView.currentIndex()
        if not current_index.isValid():
            return

        item = current_index.internalPointer()
        if item:
            await self._attrs_ui.show_attrs(item.node)

    def _show_connection_dialog(self):
        dia = ConnectionDialog(
            self,
            self._ui.addrComboBox.currentText(),
            self._security_mode,
            self._security_policy,
            self._user_certificate_path,
            self._user_private_key_path,
        )
        ret = dia.exec_()
        if ret:
            self._security_mode = dia.security_mode
            self._security_policy = dia.security_policy
            self._user_certificate_path = dia.certificate_path
            self._user_private_key_path = dia.private_key_path

    def _show_application_certificate_dialog(self):
        dia = ApplicationCertificateDialog(
            self, self._application_certificate_path, self._application_private_key_path
        )
        ret = dia.exec_()
        if ret == QDialog.Accepted:
            self._application_certificate_path = dia.certificate_path
            self._application_private_key_path = dia.private_key_path

    @asyncSlot()
    async def _connect(self):
        uri = self._ui.addrComboBox.currentText()
        uri = uri.strip()
        self._uaclient = Client(url=uri)

        if self._user_private_key_path:
            await self._uaclient.load_private_key(self._user_private_key_path)
        if self._user_certificate_path:
            await self._uaclient.load_client_certificate(self._user_certificate_path)

        if self._security_mode is not None and self._security_policy is not None:
            await self._uaclient.set_security(
                getattr(
                    crypto.security_policies, "SecurityPolicy" + self._security_policy
                ),
                self._application_certificate_path,
                self._application_private_key_path,
                mode=getattr(MessageSecurityMode, self._security_mode),
            )

        try:
            await self._uaclient.connect()
        except Exception as ex:
            self._show_error(ex)
            raise

        self._save_new_uri(uri)

        self._ua_subscription = await self._uaclient.create_subscription(
            500, _DataChangeHandler(self._handle_subscription_data)
        )

        await self._model.set_root_node(self._uaclient.nodes.root)
        self._ui.treeView.setFocus()

    @asyncSlot()
    async def _disconnect(self):
        try:
            if self._uaclient is not None and self._uaclient.uaclient.protocol:
                await self._uaclient.disconnect()
        except Exception as ex:
            self._show_error(ex)
            raise
        finally:
            self._uaclient = None
            self._ua_subscription = None
            self._ua_subscription_data = dict()

            with QSignalBlocker(self._ui.treeView.selectionModel()):
                self._attrs_ui.clear()
                self._model.clear()

    def _show_error(self, msg):
        logger.warning("showing error: %s")
        self._ui.statusBar.show()
        self._ui.statusBar.setStyleSheet(
            "QStatusBar { background-color : red; color : black; }"
        )
        self._ui.statusBar.showMessage(str(msg))
        QTimer.singleShot(1500, self._ui.statusBar.hide)

    def _save_new_uri(self, uri):
        with contextlib.suppress(ValueError):
            self._address_list.remove(uri)

        self._address_list.insert(0, uri)
        if len(self._address_list) > self._settings.value("address_list_max_count", 10):
            self._address_list.pop(-1)


def main():
    app = QApplication(sys.argv)

    event_loop = QEventLoop(app)
    asyncio.set_event_loop(event_loop)

    app_close_event = asyncio.Event()
    app.aboutToQuit.connect(app_close_event.set)

    client = Window()
    client.show()

    with event_loop:
        event_loop.run_until_complete(app_close_event.wait())

    return 0


if __name__ == "__main__":
    main()
