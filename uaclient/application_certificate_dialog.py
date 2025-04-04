from PyQt5.QtWidgets import QDialog, QFileDialog

from uaclient.applicationcertificate_ui import Ui_ApplicationCertificateDialog


class ApplicationCertificateDialog(QDialog):
    def __init__(
        self, parent, application_certificate_path, application_private_key_path
    ):
        super().__init__(parent)

        self._initial_application_certificate_path = application_certificate_path
        self._initial_application_private_key_path = application_private_key_path

        self._setup_ui()

    def _setup_ui(self) -> None:
        self._ui = Ui_ApplicationCertificateDialog()
        self._ui.setupUi(self)

        self._ui.certificateLabel.setText(self._initial_application_certificate_path)
        self._ui.privateKeyLabel.setText(self._initial_application_private_key_path)

        self._ui.certificateButton.clicked.connect(self._get_certificate)
        self._ui.privateKeyButton.clicked.connect(self._get_private_key)

    @property
    def certificate_path(self):
        text = self._ui.certificateLabel.text()
        if text == "None":
            return None
        return text

    @property
    def private_key_path(self):
        text = self._ui.privateKeyLabel.text()
        if text == "None":
            return None
        return text

    def _get_certificate(self):
        path, ok = QFileDialog.getOpenFileName(
            self,
            "Select application certificate",
            self._initial_application_certificate_path,
            "Certificate (*.der)",
        )
        if ok:
            self._ui.certificateLabel.setText(path)

    def _get_private_key(self):
        path, ok = QFileDialog.getOpenFileName(
            self,
            "Select application private key",
            self._initial_application_private_key_path,
            "Private key (*.pem)",
        )
        if ok:
            self._ui.privateKeyLabel.setText(path)
