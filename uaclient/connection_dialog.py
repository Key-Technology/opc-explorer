from PyQt5.QtWidgets import QDialog, QFileDialog

from qasync import asyncSlot

from asyncua import Client

from uaclient.connection_ui import Ui_ConnectionDialog
from uawidgets.utils import trycatchslot


class ConnectionDialog(QDialog):
    def __init__(
        self,
        parent,
        uri,
        security_mode,
        security_policy,
        user_certificate_path,
        user_private_key_path,
    ):
        super().__init__(parent)

        self._uri = uri
        self._security_mode = security_mode
        self._security_policy = security_policy
        self._user_certificate_path = user_certificate_path
        self._user_private_key_path = user_private_key_path

        self._setup_ui()

    def _setup_ui(self) -> None:
        self._ui = Ui_ConnectionDialog()
        self._ui.setupUi(self)

        self._ui.modeComboBox.addItem("None")
        self._ui.modeComboBox.addItem("Sign")
        self._ui.modeComboBox.addItem("SignAndEncrypt")
        self._ui.modeComboBox.setCurrentText(self._security_mode)

        self._ui.policyComboBox.addItem("None")
        self._ui.policyComboBox.addItem("Basic128Rsa15")
        self._ui.policyComboBox.addItem("Basic256")
        self._ui.policyComboBox.setCurrentText(self._security_policy)

        self._ui.certificateLabel.setText(self._user_certificate_path)
        self._ui.privateKeyLabel.setText(self._user_private_key_path)

        self._ui.closeButton.clicked.connect(self.accept)
        self._ui.certificateButton.clicked.connect(self._get_certificate)
        self._ui.privateKeyButton.clicked.connect(self._get_private_key)
        self._ui.queryButton.clicked.connect(self._query)

    @asyncSlot()
    @trycatchslot
    async def _query(self) -> None:
        self._ui.modeComboBox.clear()
        self._ui.policyComboBox.clear()

        client = Client(self._uri, timeout=2)
        endpoints = await client.connect_and_get_server_endpoints()
        modes = []
        policies = []
        for edp in endpoints:
            mode = edp.SecurityMode.name
            if mode not in modes:
                self._ui.modeComboBox.addItem(mode)
                modes.append(mode)
            policy = edp.SecurityPolicyUri.split("#")[1]
            if policy not in policies:
                self._ui.policyComboBox.addItem(policy)
                policies.append(policy)

    @property
    def security_mode(self):
        text = self._ui.modeComboBox.currentText()
        if text == "None":
            return None
        return text

    @property
    def security_policy(self):
        text = self._ui.policyComboBox.currentText()
        if text == "None":
            return None
        return text

    @property
    def certificate_path(self):
        return self._ui.certificateLabel.text()

    @property
    def private_key_path(self):
        return self._ui.privateKeyLabel.text()

    def _get_certificate(self):
        path, ok = QFileDialog.getOpenFileName(
            self, "Select certificate", self.certificate_path, "Certificate (*.der)"
        )
        if ok:
            self._ui.certificateLabel.setText(path)

    def _get_private_key(self):
        path, ok = QFileDialog.getOpenFileName(
            self, "Select private key", self.private_key_path, "Private key (*.pem)"
        )
        if ok:
            self._ui.privateKeyLabel.setText(path)
