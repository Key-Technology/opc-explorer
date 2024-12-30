import pytest
from uaclient.mainwindow import DataChangeSubscriptionManager
from unittest.mock import Mock


@pytest.fixture
def server_node(server):
    yield server.nodes.server


@pytest.fixture
def window(server_node):
    window = Mock()
    window.get_current_node.return_value = server_node
    yield window


@pytest.fixture
def uaclient():
    yield Mock()


def test_subscribe_data_changed(window, server_node, uaclient):
    data_change_manager = DataChangeSubscriptionManager(window, uaclient)
    data_change_manager._subscribe()

    # only one subscription per node is allowed, so this should not be added to _subscribed_nodes
    data_change_manager._subscribe()

    assert len(data_change_manager._subscribed_nodes) == 1
    assert data_change_manager._subscribed_nodes[0] == server_node


def test_unsubscribe_data_changed(window, server_node, uaclient):
    data_change_manager = DataChangeSubscriptionManager(window, uaclient)
    data_change_manager._subscribe(server_node)
    assert len(data_change_manager._subscribed_nodes) == 1

    data_change_manager._unsubscribe(server_node)
    data_change_manager._unsubscribe(server_node)
    assert len(data_change_manager._subscribed_nodes) == 0


def test_clear(window, server_node, uaclient):
    data_change_manager = DataChangeSubscriptionManager(window, uaclient)
    data_change_manager._subscribe(server_node)

    data_change_manager.clear()
    assert len(data_change_manager._subscribed_nodes) == 0
