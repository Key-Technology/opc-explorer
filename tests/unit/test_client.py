import pytest
from PyQt5.QtCore import Qt

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


def get_attr_value(text, client):
    idxlist = client.attrs_ui.model.match(
        client.attrs_ui.model.index(0, 0),
        Qt.DisplayRole,
        text,
        1,
        Qt.MatchExactly | Qt.MatchRecursive,
    )
    idx = idxlist[0]
    idx = idx.sibling(idx.row(), 1)
    item = client.attrs_ui.model.itemFromIndex(idx)
    return item.data(Qt.UserRole).value


def test_select_objects(client, server):
    objects = server.nodes.objects
    client.tree_ui.expand_to_node(objects)
    assert objects == client.tree_ui.get_current_node()
    assert client.attrs_ui.model.rowCount() > 6
    assert client.refs_ui.model.rowCount() > 1

    data = get_attr_value("NodeId", client)
    assert data == objects.nodeid


def test_select_server_node(client, server):
    server_node = server.nodes.server
    client.tree_ui.expand_to_node(server_node)
    assert server_node == client.tree_ui.get_current_node()
    assert client.attrs_ui.model.rowCount() > 6
    assert client.refs_ui.model.rowCount() > 10

    data = get_attr_value("NodeId", client)
    assert data == server_node.nodeid
