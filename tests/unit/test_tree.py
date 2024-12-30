from asyncua.sync import Server
from PyQt5.QtTest import QSignalSpy
import pytest
from asyncua import ua


@pytest.fixture
def server(url):
    server = Server()
    namepace = server.register_namespace("custom_namespace")
    objects = server.nodes.root
    objects.add_variable(namepace, "float_variable", 1.0)
    server.set_endpoint(url)
    server.start()
    yield server
    server.stop()


def test_extra_columns(client, server):
    tree_model = client.tree_ui.model
    root = tree_model.itemFromIndex(tree_model.index(0, 0))
    tree_model.subscription_handlers[root.index()].subscribe_thread.wait()
    id = root.child(3, 2).text()
    signal = client.node_signal_dict[id].signal
    spy = QSignalSpy(signal)
    assert spy.wait()
    assert root.child(3, 4).text() == "float_variable"
    assert root.child(3, 5).text() == "Double"
    assert root.child(3, 3).text() == "1.0"

    node = server.get_node(id)

    node.write_attribute(ua.AttributeIds.Value, ua.DataValue(2.0))
    assert node in client.tree_ui.model.data_change_manager._subscribed_nodes
    assert spy.wait()
    assert root.child(3, 3).text() == "2.0"


def test_unsub_extra_columns(client, server):
    tree_model = client.tree_ui.model
    root = tree_model.itemFromIndex(tree_model.index(0, 0))
    tree_model.subscription_handlers[root.index()].subscribe_thread.wait()
    id = root.child(3, 2).text()
    signal = client.node_signal_dict[id].signal
    node = server.get_node(id)
    spy = QSignalSpy(signal)
    spy.wait()
    client.ui.treeView.setExpanded(root.index(), False)
    tree_model.subscription_handlers[root.index()].unsubscribe_thread.wait()

    assert node not in tree_model.data_change_manager._subscribed_nodes
