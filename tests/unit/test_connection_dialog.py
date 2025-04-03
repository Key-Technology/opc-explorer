import pytest
from uaclient.connection_dialog import ConnectionDialog
from unittest.mock import patch
from PyQt5.QtWidgets import QFileDialog


@pytest.fixture
def dialog(application):
    dialog = ConnectionDialog(
        None,
        "test uri",
        "test security mode",
        "test security policy",
        "test user cert",
        "test user key",
    )
    yield dialog
    dialog.deleteLater()


def test_get_certificate(dialog):
    with patch.object(
        QFileDialog, "getOpenFileName", return_value=("/test/path", True)
    ) as mock:
        dialog._get_certificate()
        mock.assert_called_once_with(
            dialog, "Select certificate", "test user cert", "Certificate (*.der)"
        )
        assert dialog.certificate_path == "/test/path"


def test_get_private_key(dialog):
    with patch.object(
        QFileDialog, "getOpenFileName", return_value=("/test/path", True)
    ) as mock:
        dialog._get_private_key()
        mock.assert_called_once_with(
            dialog, "Select private key", "test user key", "Private key (*.pem)"
        )
        assert dialog.private_key_path == "/test/path"
