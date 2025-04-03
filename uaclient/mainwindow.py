#! /usr/bin/env python3

import sys

import logging

from PyQt5.QtCore import (
    pyqtSignal,
    QFile,
    QTimer,
    Qt,
    QObject,
    QSettings,
    QTextStream,
    QItemSelection,
    QCoreApplication,
)
from PyQt5.QtGui import QIcon
from PyQt5.QtWidgets import (
    QMainWindow,
    QMessageBox,
    QWidget,
    QApplication,
    QMenu,
    QDialog,
)

from asyncua import ua

from uaclient.uaclient import UaClient
from uaclient.mainwindow_ui import Ui_MainWindow
from uaclient.connection_dialog import ConnectionDialog
from uaclient.application_certificate_dialog import ApplicationCertificateDialog

# must be here for resources even if not used
from uawidgets import resources  # noqa: F401
from uawidgets.attrs_widget import AttrsWidget
from uawidgets.tree_widget import TreeWidget
from uawidgets.utils import trycatchslot
from uawidgets.logger import QtHandler
from uawidgets.call_method_dialog import CallMethodDialog


logger = logging.getLogger(__name__)


class EventHandler(QObject):
    event_fired = pyqtSignal(object)

    def event_notification(self, event):
        self.event_fired.emit(event)


class Window(QMainWindow):
    def __init__(self):
        QMainWindow.__init__(self)
        self.ui = Ui_MainWindow()
        self.ui.setupUi(self)
        self.setWindowIcon(QIcon(":/network.svg"))

        # fix stuff imposible to do in qtdesigner
        # remove dock titlebar for addressbar
        w = QWidget()
        self.ui.addrDockWidget.setTitleBarWidget(w)

        # we only show statusbar in case of errors
        self.ui.statusBar.hide()

        # setup QSettings for application and get a settings object
        QCoreApplication.setOrganizationName("Key Technology")
        QCoreApplication.setApplicationName("OPC Explorer")
        self.settings = QSettings()

        self._address_list = self.settings.value(
            "address_list",
            [
                "opc.tcp://localhost:4840",
                "opc.tcp://localhost:53530/OPCUA/SimulationServer/",
            ],
        )
        print("ADR", self._address_list)
        self._address_list_max_count = int(
            self.settings.value("address_list_max_count", 10)
        )

        # init widgets
        for addr in self._address_list:
            self.ui.addrComboBox.insertItem(100, addr)

        self.uaclient = UaClient()

        self.tree_ui = TreeWidget(self.ui.treeView)
        self.tree_ui.error.connect(self.show_error)
        self.setup_context_menu_tree()
        self.ui.treeView.selectionModel().currentChanged.connect(
            self._update_actions_state
        )

        self.attrs_ui = AttrsWidget(self.ui.attrView)
        self.attrs_ui.error.connect(self.show_error)

        self.ui.addrComboBox.currentTextChanged.connect(self._uri_changed)
        self._uri_changed(
            self.ui.addrComboBox.currentText()
        )  # force update for current value at startup

        self.ui.actionCopyPath.triggered.connect(self.tree_ui.copy_path)
        self.ui.actionCopyNodeId.triggered.connect(self.tree_ui.copy_nodeid)
        self.ui.actionCall.triggered.connect(self.call_method)

        self.ui.treeView.selectionModel().selectionChanged.connect(self.show_attrs)
        self.ui.attrRefreshButton.clicked.connect(self.show_attrs)

        self.resize(
            int(self.settings.value("main_window_width", 800)),
            int(self.settings.value("main_window_height", 600)),
        )
        data = self.settings.value("main_window_state", None)
        if data:
            self.restoreState(data)

        self.ui.connectButton.clicked.connect(self.connect)
        self.ui.disconnectButton.clicked.connect(self.disconnect)
        # self.ui.treeView.expanded.connect(self._fit)

        self.ui.actionConnect.triggered.connect(self.connect)
        self.ui.actionDisconnect.triggered.connect(self.disconnect)

        self.ui.connectOptionButton.clicked.connect(self.show_connection_dialog)
        self.ui.actionClient_Application_Certificate.triggered.connect(
            self.show_application_certificate_dialog
        )
        self.ui.actionDark_Mode.triggered.connect(self.dark_mode)

    def _uri_changed(self, uri):
        self.uaclient.load_security_settings(uri)

    def show_connection_dialog(self):
        dia = ConnectionDialog(
            self,
            self.ui.addrComboBox.currentText(),
            self.uaclient.security_mode,
            self.uaclient.security_policy,
            self.uaclient.user_certificate_path,
            self.uaclient.user_private_key_path,
        )
        ret = dia.exec_()
        if ret:
            self.uaclient.security_mode = dia.security_mode
            self.uaclient.security_policy = dia.security_policy
            self.uaclient.user_certificate_path = dia.certificate_path
            self.uaclient.user_private_key_path = dia.private_key_path

    def show_application_certificate_dialog(self):
        dia = ApplicationCertificateDialog(
            self,
            self.uaclient.application_certificate_path,
            self.uaclient.application_private_key_path,
        )
        ret = dia.exec_()
        if ret == QDialog.Accepted:
            self.uaclient.application_certificate_path = dia.certificate_path
            self.uaclient.application_private_key_path = dia.private_key_path
        self.uaclient.save_application_certificate_settings()

    @trycatchslot
    def show_attrs(self, selection):
        if isinstance(selection, QItemSelection):
            if not selection.indexes():  # no selection
                return

        node = self.get_current_node()
        if node:
            self.attrs_ui.show_attrs(node)

    def show_error(self, msg):
        logger.warning("showing error: %s")
        self.ui.statusBar.show()
        self.ui.statusBar.setStyleSheet(
            "QStatusBar { background-color : red; color : black; }"
        )
        self.ui.statusBar.showMessage(str(msg))
        QTimer.singleShot(1500, self.ui.statusBar.hide)

    def get_current_node(self, idx=None):
        return self.tree_ui.get_current_node(idx)

    def get_uaclient(self):
        return self.uaclient

    @trycatchslot
    def connect(self):
        uri = self.ui.addrComboBox.currentText()
        uri = uri.strip()
        try:
            self.uaclient.connect(uri)
        except Exception as ex:
            self.show_error(ex)
            raise

        self._update_address_list(uri)
        self.tree_ui.set_root_node(self.uaclient.client.nodes.root)
        self.ui.treeView.setFocus()
        self.load_current_node()

    def _update_address_list(self, uri):
        if uri == self._address_list[0]:
            return
        if uri in self._address_list:
            self._address_list.remove(uri)
        self._address_list.insert(0, uri)
        if len(self._address_list) > self._address_list_max_count:
            self._address_list.pop(-1)

    def disconnect(self):
        try:
            self.uaclient.disconnect()
        except Exception as ex:
            self.show_error(ex)
            raise
        finally:
            self.save_current_node()
            self.tree_ui.clear()
            self.attrs_ui.clear()

    def closeEvent(self, event):
        self.tree_ui.save_state()
        self.attrs_ui.save_state()
        self.settings.setValue("main_window_width", self.size().width())
        self.settings.setValue("main_window_height", self.size().height())
        self.settings.setValue("main_window_state", self.saveState())
        self.settings.setValue("address_list", self._address_list)
        self.disconnect()
        event.accept()

    def save_current_node(self):
        current_node = self.tree_ui.get_current_node()
        if current_node:
            mysettings = self.settings.value("current_node", None)
            if mysettings is None:
                mysettings = {}
            uri = self.ui.addrComboBox.currentText()
            mysettings[uri] = current_node.nodeid.to_string()
            self.settings.setValue("current_node", mysettings)

    def load_current_node(self):
        mysettings = self.settings.value("current_node", None)
        if mysettings is None:
            return
        uri = self.ui.addrComboBox.currentText()
        if uri in mysettings:
            nodeid = ua.NodeId.from_string(mysettings[uri])
            node = self.uaclient.client.get_node(nodeid)
            self.tree_ui.expand_to_node(node)

    def setup_context_menu_tree(self):
        self.ui.treeView.setContextMenuPolicy(Qt.CustomContextMenu)
        self.ui.treeView.customContextMenuRequested.connect(
            self._show_context_menu_tree
        )
        self._contextMenu = QMenu()
        self.addAction(self.ui.actionCopyPath)
        self.addAction(self.ui.actionCopyNodeId)
        self._contextMenu.addSeparator()
        self._contextMenu.addAction(self.ui.actionCall)
        self._contextMenu.addSeparator()

    def addAction(self, action):
        self._contextMenu.addAction(action)

    @trycatchslot
    def _update_actions_state(self, current, previous):
        node = self.get_current_node(current)
        self.ui.actionCall.setEnabled(False)
        if node:
            if node.read_node_class() == ua.NodeClass.Method:
                self.ui.actionCall.setEnabled(True)

    def _show_context_menu_tree(self, position):
        node = self.tree_ui.get_current_node()
        if node:
            self._contextMenu.exec_(self.ui.treeView.viewport().mapToGlobal(position))

    def call_method(self):
        node = self.get_current_node()
        dia = CallMethodDialog(self, self.uaclient.client, node)
        dia.show()

    def dark_mode(self):
        self.settings.setValue("dark_mode", self.ui.actionDark_Mode.isChecked())

        msg = QMessageBox()
        msg.setIcon(QMessageBox.Information)
        msg.setText("Restart for changes to take effect")
        msg.exec_()


def main():
    app = QApplication(sys.argv)
    client = Window()
    handler = QtHandler(client.ui.logTextEdit)
    logging.getLogger().addHandler(handler)
    logging.getLogger("uaclient").setLevel(logging.INFO)
    logging.getLogger("uawidgets").setLevel(logging.INFO)
    # logging.getLogger("opcua").setLevel(logging.INFO)  # to enable logging of ua client library

    # set stylesheet
    if QSettings().value("dark_mode", "false") == "true":
        file = QFile(":/dark.qss")
        file.open(QFile.ReadOnly | QFile.Text)
        stream = QTextStream(file)
        app.setStyleSheet(stream.readAll())

    client.show()
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
