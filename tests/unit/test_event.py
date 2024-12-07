def test_event_subscription(client, server):
    namepace = server.register_namespace("custom_namespace")
    objects = server.nodes.objects
    string_variable = objects.add_variable(namepace, "string_variable", "Value")
    server_node = server.nodes.server

    client.event_ui._subscribe(server_node)

    # invalid type wont be added
    client.event_ui._subscribe(string_variable)
    # only one subscription per node is allowed, so this should not be added to _subscribed_nodes
    client.event_ui._subscribe(server_node)

    assert len(client.event_ui._subscribed_nodes) == 1
    assert client.event_ui._subscribed_nodes[0] == server_node


def test_unsubscribe_event_subscription(client, server, url):
    server_node = server.nodes.server
    current_nodes = client.settings.value("current_node", None)
    current_nodes[url] = server_node.nodeid.to_string()
    client.settings.setValue("current_node", current_nodes)
    client.load_current_node()

    client.event_ui._subscribe(server_node)
    assert len(client.event_ui._subscribed_nodes) == 1

    client.event_ui._unsubscribe(server_node)
    client.event_ui._unsubscribe(server_node)
    assert len(client.event_ui._subscribed_nodes) == 0
