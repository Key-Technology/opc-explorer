import pytest

from unittest import mock

from PyQt5.QtCore import Qt, QModelIndex
from PyQt5.QtWidgets import QTreeView
from PyQt5.QtGui import QIcon

from asyncua import ua

from uaclient.tree_ui import OpcTreeModel


@pytest.fixture
def tree_view(application):
    view = QTreeView()
    yield view
    view.deleteLater()


def test_init(tree_view):
    with mock.patch.object(tree_view, "setModel") as mock_set_model:
        model = OpcTreeModel(tree_view, [])

    mock_set_model.assert_called_with(model)
    assert model.columnCount() == 0
    assert model.rowCount() == 0


def test_init_columns(tree_view):
    model = OpcTreeModel(
        tree_view, [ua.AttributeIds.DisplayName, ua.AttributeIds.BrowseName]
    )
    assert model.columnCount() == 2
    assert model.rowCount() == 0


async def test_index(tree_view, async_server):
    model = OpcTreeModel(tree_view, [ua.AttributeIds.DisplayName])

    assert not model.index(0, 0).isValid()

    index = await async_server.register_namespace("test")
    object_node = await async_server.nodes.objects.add_object(index, "TestObject")
    await model.set_root_node(object_node)

    index = model.index(0, 0)
    assert index.isValid()
    assert index.data() == "TestObject"


def test_header_data(tree_view):
    model = OpcTreeModel(
        tree_view, [ua.AttributeIds.DisplayName, ua.AttributeIds.BrowseName]
    )

    assert model.headerData(0, Qt.Orientation.Horizontal) == "Display Name"
    assert model.headerData(1, Qt.Orientation.Horizontal) == "Browse Name"


def test_header_data_all_possible_columns(tree_view):
    model = OpcTreeModel(tree_view, [id for id in ua.AttributeIds])

    assert model.columnCount() > 0

    # Make sure no possible column throws KeyErrors when we're fetching its name
    for column in range(model.columnCount()):
        model.headerData(column, Qt.Orientation.Horizontal)


async def test_data(tree_view, async_server, wait_for_signal):
    model = OpcTreeModel(
        tree_view, [ua.AttributeIds.DisplayName, ua.AttributeIds.Value]
    )

    index = await async_server.register_namespace("test")
    object_node = await async_server.nodes.objects.add_object(index, "TestObject")
    node = await object_node.add_variable(index, "TestVariable", 42)

    await model.set_root_node(object_node)

    root_index = model.index(0, 0)
    async with wait_for_signal(
        model.item_added, check_params_callback=lambda item: item.node == node
    ):
        tree_view.setExpanded(root_index, True)

    assert model.data(root_index) == "TestObject"
    assert model.data(model.index(0, 0, root_index)) == "TestVariable"
    assert model.data(model.index(0, 1, root_index)) == "42"

    # DecorationRole gets an icon
    assert isinstance(
        model.data(model.index(0, 0, root_index), Qt.ItemDataRole.DecorationRole), QIcon
    )


async def _expand_root_node(tree_view, async_server, wait_for_signal):
    model = OpcTreeModel(tree_view, [ua.AttributeIds.Value])

    index = await async_server.register_namespace("test")
    object_node = await async_server.nodes.objects.add_object(index, "TestObject")
    node = await object_node.add_variable(index, "TestVariable", 42)

    await model.set_root_node(object_node)
    assert model.rowCount() == 1

    index = model.index(0, 0)
    assert model.rowCount(index) == 0

    async with wait_for_signal(
        model.item_added, check_params_callback=lambda item: item.node == node
    ):
        tree_view.setExpanded(index, True)

    assert model.rowCount(index) == 1

    return model, node


async def test_expand_root_node(tree_view, async_server, wait_for_signal):
    await _expand_root_node(tree_view, async_server, wait_for_signal)


async def test_collapse_root_node(tree_view, async_server, wait_for_signal):
    model, node = await _expand_root_node(tree_view, async_server, wait_for_signal)

    index = model.index(0, 0)
    assert model.rowCount(index) == 1

    async with wait_for_signal(
        model.item_removed, check_params_callback=lambda item: item.node == node
    ):
        tree_view.setExpanded(index, False)

    assert model.rowCount(index) == 0


async def test_data_changed(tree_view, async_server, wait_for_signal):
    model, _node = await _expand_root_node(tree_view, async_server, wait_for_signal)

    child_index = model.index(0, 0, model.index(0, 0))
    assert child_index.isValid()

    data_index = QModelIndex(child_index)
    item = child_index.internalPointer()

    def _check_params_callback(*args):
        return args[0] == data_index and args[1] == data_index

    async with wait_for_signal(
        model.dataChanged, check_params_callback=_check_params_callback
    ):
        item.set_data(ua.AttributeIds.Value, ua.DataValue(43))


async def test_has_children(tree_view, async_server):
    model = OpcTreeModel(tree_view, [ua.AttributeIds.Value])

    index = await async_server.register_namespace("test")
    node = await async_server.nodes.objects.add_object(index, "TestObject")
    await node.add_variable(index, "TestVariable", 42)

    await model.set_root_node(node)
    index = model.index(0, 0)

    # We haven't actually fetched any yet, so it should assume we have children
    assert model.hasChildren(index)

    await index.internalPointer().refresh_children()

    # Now we've fetched them, it knows we do
    assert model.hasChildren(index)


async def test_has_children_no_children(tree_view, async_server):
    model = OpcTreeModel(tree_view, [ua.AttributeIds.Value])

    index = await async_server.register_namespace("test")
    node = await async_server.nodes.objects.add_variable(index, "TestVariable", 42)

    await model.set_root_node(node)
    index = model.index(0, 0)

    # We haven't actually fetched any yet, so it should assume we have children
    assert model.hasChildren(index)

    await index.internalPointer().refresh_children()

    # Now we've fetched them, it knows we do not
    assert not model.hasChildren(index)
