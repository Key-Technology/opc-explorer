from PyQt5.QtCore import Qt


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


def test_connect(server, url, client):
    assert client._address_list[0] == "opc.tcp://localhost:48400/freeopcua/server/"
    assert client.uaclient._connected
    current_node = client.tree_ui.get_current_node()
    assert (
        client.uaclient.settings.value("current_node")[url]
        == current_node.nodeid.to_string()
    )


def test_load_current_node(client, server, url):
    server_node = server.nodes.server
    current_nodes = client.settings.value("current_node", None)
    current_nodes[url] = server_node.nodeid.to_string()
    client.settings.setValue("current_node", current_nodes)
    assert server_node == client.get_current_node()
