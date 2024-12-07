import pytest


@pytest.fixture
def server_node(server, client, url):
    server_node = server.nodes.server

    current_nodes = client.settings.value("current_node", None)
    current_nodes[url] = server_node.nodeid.to_string()
    client.settings.setValue("current_node", current_nodes)
    client.load_current_node()
    yield server_node


def test_subscribe_data_changed(client, server, server_node):
    client.datachange_ui._subscribe()

    # only one subscription per node is allowed, so this should not be added to _subscribed_nodes
    client.datachange_ui._subscribe()

    assert len(client.datachange_ui._subscribed_nodes) == 1
    assert client.datachange_ui._subscribed_nodes[0] == server_node


def test_unsubscribe_data_changed(client, server, server_node):
    client.datachange_ui._unsubscribe(server_node)
    client.datachange_ui._unsubscribe(server_node)
    assert len(client.datachange_ui._subscribed_nodes) == 0
