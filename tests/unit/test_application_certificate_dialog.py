import pytest
from uaclient.application_certificate_dialog import ApplicationCertificateDialog
from unittest.mock import patch
from PyQt5.QtWidgets import QFileDialog


@pytest.fixture
def dialog(application):
    dialog = ApplicationCertificateDialog(None, "certificate/path", "key/path")
    yield dialog
    dialog.deleteLater()


def test_certificate_path(dialog):
    assert dialog.certificate_path == "certificate/path"


def test_private_key_path(dialog):
    assert dialog.private_key_path == "key/path"


def test_get_certificate(dialog):
    with patch.object(
        QFileDialog, "getOpenFileName", return_value=("/test/path", True)
    ) as mock:
        dialog._get_certificate()
        mock.assert_called_once_with(
            dialog,
            "Select application certificate",
            "certificate/path",
            "Certificate (*.der)",
        )
        assert dialog.certificate_path == "/test/path"


def test_get_private_key(dialog):
    with patch.object(
        QFileDialog, "getOpenFileName", return_value=("/test/path", True)
    ) as mock:
        dialog._get_private_key()
        mock.assert_called_once_with(
            dialog,
            "Select application private key",
            "key/path",
            "Private key (*.pem)",
        )
        assert dialog.private_key_path == "/test/path"
