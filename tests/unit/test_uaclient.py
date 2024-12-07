from uaclient.mainwindow import Window


def test_connect(server, url, client):
    assert client._address_list[0] == "opc.tcp://localhost:48400/freeopcua/server/"
    assert client.uaclient._connected
    current_node = client.tree_ui.get_current_node()
    assert (
        client.uaclient.settings.value("current_node")[url]
        == current_node.nodeid.to_string()
    )


def test_disconnect(qtbot, url, server):
    client = Window()
    qtbot.addWidget = client
    client.ui.addrComboBox.setCurrentText(url)
    client.connect()
    current_node = client.tree_ui.get_current_node()
    client.disconnect()

    assert not client.uaclient._connected
    assert (
        client.uaclient.settings.value("current_node")[url]
        == current_node.nodeid.to_string()
    )
    assert len(client.tree_ui.model._fetched) == 0
    assert len(client.datachange_ui._subscribed_nodes) == 0
    assert len(client.event_ui._subscribed_nodes) == 0
