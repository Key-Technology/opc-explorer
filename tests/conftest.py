import pytest
from asyncua.sync import Server
from uaclient.mainwindow import Window


@pytest.fixture(scope="module")
def url():
    yield "opc.tcp://localhost:48401/freeopcua/server/"


@pytest.fixture(scope="module")
def server(url):
    server = Server()
    server.set_endpoint(url)
    server.start()
    yield server
    server.stop()


@pytest.fixture
def client(qtbot, url, server):
    client = Window()
    qtbot.addWidget = client
    client.ui.addrComboBox.setCurrentText(url)
    client.connect()
    yield client
    client.disconnect()
