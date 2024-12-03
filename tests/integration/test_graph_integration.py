import pytest
from asyncua.sync import Server
from uaclient.mainwindow import Window

URL = "opc.tcp://localhost:48400/freeopcua/server/"


@pytest.fixture
def server():
    server = Server()
    server.set_endpoint(URL)
    server.start()
    yield server
    server.stop()


@pytest.fixture
def client(qtbot, server):
    client = Window()
    qtbot.addWidget = client
    client.ui.addrComboBox.setCurrentText(URL)
    client.connect()
    yield client
    client.disconnect()


def test_restart_timer(qtbot, client, server):
    client.ui.spinBoxNumberOfPoints.setValue(90)
    client.ui.buttonApply.click()
    assert client.graph_ui.N == 90
