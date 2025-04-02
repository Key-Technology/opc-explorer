import pytest
from unittest.mock import ANY, create_autospec

from PyQt5.QtCore import QAbstractItemModel, QPersistentModelIndex, QModelIndex
from PyQt5.QtGui import QIcon

from asyncua import ua

from uaclient.tree_ui import OpcTreeItem


@pytest.fixture
def mock_model():
    yield create_autospec(QAbstractItemModel)


def opc_method(parent, value):
    return value * 2


async def test_column_count_1(mock_model, async_server):
    item = OpcTreeItem(
        mock_model,
        async_server.nodes.objects,
        QPersistentModelIndex(),
        [ua.AttributeIds.DisplayName],
    )
    assert item.column_count() == 1


async def test_column_count_2(mock_model, async_server):
    item = OpcTreeItem(
        mock_model,
        async_server.nodes.objects,
        QPersistentModelIndex(),
        [ua.AttributeIds.DisplayName, ua.AttributeIds.Description],
    )
    assert item.column_count() == 2


async def test_column_count_browse_name(mock_model, async_server):
    item = OpcTreeItem(
        mock_model,
        async_server.nodes.objects,
        QPersistentModelIndex(),
        [ua.AttributeIds.DisplayName, ua.AttributeIds.BrowseName],
    )
    assert item.column_count() == 2


async def test_column_count_node_class(mock_model, async_server):
    item = OpcTreeItem(
        mock_model,
        async_server.nodes.objects,
        QPersistentModelIndex(),
        [ua.AttributeIds.DisplayName, ua.AttributeIds.NodeClass],
    )
    assert item.column_count() == 2


async def test_child_count(mock_model, async_server):
    item = OpcTreeItem(
        mock_model,
        async_server.nodes.objects,
        QPersistentModelIndex(),
        [ua.AttributeIds.DisplayName],
    )
    assert item.child_count() == 0


async def test_row_without_parent(mock_model, async_server):
    item = OpcTreeItem(
        mock_model,
        async_server.nodes.objects,
        QPersistentModelIndex(),
        [ua.AttributeIds.DisplayName],
    )
    assert item.row() == 0


async def test_row_with_parent(qtbot, mock_model, async_server):
    mock_model.index.return_value = QModelIndex()

    index = await async_server.register_namespace("test")
    node = await async_server.nodes.objects.add_object(index, "TestObject")
    await node.add_variable(index, "TestVariable", 42)

    item = OpcTreeItem(
        mock_model, node, QPersistentModelIndex(), [ua.AttributeIds.DisplayName]
    )
    await item._refresh_data()
    await item.refresh_children()

    assert item.child_count() == 1
    assert item.child(0).row() == 0


async def test_row_multiple_children(qtbot, mock_model, async_server):
    mock_model.index.return_value = QModelIndex()

    index = await async_server.register_namespace("test")
    node = await async_server.nodes.objects.add_object(index, "TestObject")
    await node.add_variable(index, "TestVariable1", 42)
    await node.add_variable(index, "TestVariable2", 43)

    item = OpcTreeItem(
        mock_model, node, QPersistentModelIndex(), [ua.AttributeIds.DisplayName]
    )
    await item._refresh_data()
    await item.refresh_children()

    assert item.child_count() == 2
    assert item.child(1).row() == 1


async def test_data(mock_model, async_server):
    index = await async_server.register_namespace("test")
    node = await async_server.nodes.objects.add_variable(index, "TestVariable", 42)
    item = OpcTreeItem(
        mock_model,
        node,
        QPersistentModelIndex(),
        [ua.AttributeIds.DisplayName, ua.AttributeIds.Value],
    )
    await item._refresh_data()

    assert item.data(0) == "TestVariable"
    assert item.data(1) == 42


async def test_data_reversed(mock_model, async_server):
    index = await async_server.register_namespace("test")
    node = await async_server.nodes.objects.add_variable(index, "TestVariable", 42)
    item = OpcTreeItem(
        mock_model,
        node,
        QPersistentModelIndex(),
        [ua.AttributeIds.Value, ua.AttributeIds.DisplayName],
    )
    await item._refresh_data()

    assert item.data(0) == 42
    assert item.data(1) == "TestVariable"


async def _setup_child_tests(mock_model, async_server):
    mock_model.index.return_value = QModelIndex()

    index = await async_server.register_namespace("test")
    node1 = await async_server.nodes.objects.add_object(index, "TestObject1")
    node2 = await async_server.nodes.objects.add_object(index, "TestObject2")

    root_item = OpcTreeItem(
        mock_model,
        async_server.nodes.objects,
        QPersistentModelIndex(),
        [ua.AttributeIds.DisplayName],
    )

    item1 = OpcTreeItem(
        mock_model,
        node1,
        QPersistentModelIndex(),
        [ua.AttributeIds.DisplayName],
    )

    item2 = OpcTreeItem(
        mock_model,
        node2,
        QPersistentModelIndex(),
        [ua.AttributeIds.DisplayName],
    )

    return root_item, item1, item2


async def test_add_child(mock_model, async_server):
    root_item, item1, item2 = await _setup_child_tests(mock_model, async_server)

    await root_item.add_child(item1)
    assert item1.parent() == root_item
    assert root_item.child_count() == 1
    assert root_item.child(0) == item1

    await root_item.add_child(item2)
    assert item2.parent() == root_item
    assert root_item.child_count() == 2

    # Assert that the children are sorted
    assert root_item.child(0) == item1
    assert root_item.child(1) == item2


async def test_add_child_reversed(mock_model, async_server):
    root_item, item1, item2 = await _setup_child_tests(mock_model, async_server)

    await root_item.add_child(item2)
    assert item2.parent() == root_item
    assert root_item.child_count() == 1
    assert root_item.child(0) == item2

    await root_item.add_child(item1)
    assert item1.parent() == root_item
    assert root_item.child_count() == 2

    # Assert that the children are still sorted
    assert root_item.child(0) == item1
    assert root_item.child(1) == item2


async def test_refresh_children(qtbot, mock_model, async_server):
    index = await async_server.register_namespace("test")
    node = await async_server.nodes.objects.add_object(index, "TestObject")
    child = await node.add_variable(index, "TestVariable", 42)

    item = OpcTreeItem(
        mock_model, node, QPersistentModelIndex(), [ua.AttributeIds.DisplayName]
    )
    await item._refresh_data()

    mock_model.index.return_value = QModelIndex()

    assert not item.children_fetched()

    with qtbot.waitSignal(item.item_added, timeout=0) as blocker:
        await item.refresh_children()

    assert blocker.args[0].node == child
    assert item.child_count() == 1
    assert item.children_fetched()

    mock_model.beginInsertRows.assert_called_with(ANY, 0, 0)
    mock_model.endInsertRows.assert_called_with()


async def test_clear_children(qtbot, mock_model, async_server):
    mock_model.index.return_value = QModelIndex()

    index = await async_server.register_namespace("test")
    node = await async_server.nodes.objects.add_object(index, "TestObject")
    child = await node.add_variable(index, "TestVariable", 42)

    item = OpcTreeItem(
        mock_model, node, QPersistentModelIndex(), [ua.AttributeIds.DisplayName]
    )
    await item._refresh_data()
    await item.refresh_children()

    assert item.children_fetched()
    with qtbot.waitSignal(item.item_removed, timeout=0) as blocker:
        item.clear_children()

    assert blocker.args[0].node == child
    assert item.child_count() == 0
    assert not item.children_fetched()

    mock_model.beginRemoveRows.assert_called_with(ANY, 0, 0)
    mock_model.endRemoveRows.assert_called_with()


async def test_set_data(qtbot, mock_model, async_server):
    mock_model.index.return_value = QModelIndex()

    item = OpcTreeItem(
        mock_model,
        async_server.nodes.objects,
        QPersistentModelIndex(),
        [ua.AttributeIds.Value],
    )

    with qtbot.waitSignal(item.data_changed, timeout=0):
        item.set_data(ua.AttributeIds.Value, ua.DataValue(42))


async def test_icon_without_data(mock_model, async_server):
    index = await async_server.register_namespace("test")
    node = await async_server.nodes.objects.add_variable(index, "TestVariable", 42)
    item = OpcTreeItem(
        mock_model, node, QPersistentModelIndex(), [ua.AttributeIds.DisplayName]
    )

    assert item.icon() is None


async def test_icon_folder(mock_model, async_server):
    index = await async_server.register_namespace("test")
    node = await async_server.nodes.objects.add_folder(index, "TestFolder")
    item = OpcTreeItem(
        mock_model, node, QPersistentModelIndex(), [ua.AttributeIds.DisplayName]
    )
    await item._refresh_data()

    assert (
        item.icon().pixmap(20, 20).toImage()
        == QIcon(":/folder.svg").pixmap(20, 20).toImage()
    )


async def test_icon_object(mock_model, async_server):
    index = await async_server.register_namespace("test")
    node = await async_server.nodes.objects.add_object(index, "TestObject")
    item = OpcTreeItem(
        mock_model, node, QPersistentModelIndex(), [ua.AttributeIds.DisplayName]
    )
    await item._refresh_data()

    assert (
        item.icon().pixmap(20, 20).toImage()
        == QIcon(":/object.svg").pixmap(20, 20).toImage()
    )


async def test_icon_object_type(mock_model, async_server):
    index = await async_server.register_namespace("test")
    node = await async_server.nodes.objects.add_object_type(index, "TestObjectType")
    item = OpcTreeItem(
        mock_model, node, QPersistentModelIndex(), [ua.AttributeIds.DisplayName]
    )
    await item._refresh_data()

    assert (
        item.icon().pixmap(20, 20).toImage()
        == QIcon(":/object_type.svg").pixmap(20, 20).toImage()
    )


async def test_icon_property(mock_model, async_server):
    index = await async_server.register_namespace("test")
    node = await async_server.nodes.objects.add_property(index, "TestProperty", 42)
    item = OpcTreeItem(
        mock_model, node, QPersistentModelIndex(), [ua.AttributeIds.DisplayName]
    )
    await item._refresh_data()

    assert (
        item.icon().pixmap(20, 20).toImage()
        == QIcon(":/property.svg").pixmap(20, 20).toImage()
    )


async def test_icon_variable(mock_model, async_server):
    index = await async_server.register_namespace("test")
    node = await async_server.nodes.objects.add_variable(index, "TestVariable", 42)
    item = OpcTreeItem(
        mock_model, node, QPersistentModelIndex(), [ua.AttributeIds.DisplayName]
    )
    await item._refresh_data()

    assert (
        item.icon().pixmap(20, 20).toImage()
        == QIcon(":/variable.svg").pixmap(20, 20).toImage()
    )


async def test_icon_variable_type(mock_model, async_server):
    index = await async_server.register_namespace("test")
    node = await async_server.nodes.objects.add_variable_type(
        index, "TestVariableType", 1
    )
    item = OpcTreeItem(
        mock_model, node, QPersistentModelIndex(), [ua.AttributeIds.DisplayName]
    )
    await item._refresh_data()

    assert (
        item.icon().pixmap(20, 20).toImage()
        == QIcon(":/variable_type.svg").pixmap(20, 20).toImage()
    )


async def test_icon_method(mock_model, async_server):
    index = await async_server.register_namespace("test")
    node = await async_server.nodes.objects.add_method(
        ua.NodeId("TestMethod", index),
        ua.QualifiedName("TestMethod", index),
        opc_method,
        [ua.VariantType.Int64],
        [ua.VariantType.Int64],
    )
    item = OpcTreeItem(
        mock_model, node, QPersistentModelIndex(), [ua.AttributeIds.DisplayName]
    )
    await item._refresh_data()

    assert (
        item.icon().pixmap(20, 20).toImage()
        == QIcon(":/method.svg").pixmap(20, 20).toImage()
    )


async def test_icon_data_type(mock_model, async_server):
    index = await async_server.register_namespace("test")
    node = await async_server.nodes.objects.add_data_type(index, "TestDataType")
    item = OpcTreeItem(
        mock_model, node, QPersistentModelIndex(), [ua.AttributeIds.DisplayName]
    )
    await item._refresh_data()

    assert (
        item.icon().pixmap(20, 20).toImage()
        == QIcon(":/data_type.svg").pixmap(20, 20).toImage()
    )


async def test_icon_reference_type(mock_model, async_server):
    index = await async_server.register_namespace("test")
    node = await async_server.nodes.objects.add_reference_type(
        index, "TestReferenceType"
    )
    item = OpcTreeItem(
        mock_model, node, QPersistentModelIndex(), [ua.AttributeIds.DisplayName]
    )
    await item._refresh_data()

    assert (
        item.icon().pixmap(20, 20).toImage()
        == QIcon(":/reference_type.svg").pixmap(20, 20).toImage()
    )
