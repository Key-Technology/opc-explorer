import asyncio
import copy
from typing import Optional, Any, List, Dict, cast

from PyQt5.QtCore import (
    QObject,
    pyqtSignal,
    QPersistentModelIndex,
    QModelIndex,
    QAbstractItemModel,
)
from PyQt5.QtGui import QIcon

from asyncua import ua, Node


async def _refresh_item(item):
    await item._refresh_data()
    return item


class OpcTreeItem(QObject):
    data_changed = pyqtSignal(QModelIndex, QModelIndex)
    item_added = pyqtSignal(QObject)
    item_removed = pyqtSignal(QObject)

    def __init__(
        self,
        model: QAbstractItemModel,
        node: Node,
        parent_index: QPersistentModelIndex,
        columns: List[ua.AttributeIds],
        *,
        parent: Optional["OpcTreeItem"] = None,
    ):
        super().__init__(parent)
        self.node = node
        self._model = model
        self._parent_index = parent_index
        self._children: List["OpcTreeItem"] = []

        self._display_name = ""
        self._value = None
        self._children_fetched = False
        self._type_definition = None

        self._requested_columns = columns
        self._model_column_to_ua_column = dict(
            [(index, column) for index, column in enumerate(columns)]
        )
        self._ua_column_to_model_column = dict(
            [(column, index) for index, column in enumerate(columns)]
        )

        self._columns = copy.deepcopy(columns)

        # We always need the node class to determine icon, even if it wasn't requested
        if ua.AttributeIds.NodeClass not in self._columns:
            self._columns.append(ua.AttributeIds.NodeClass)

        # We always need the browse name for sorting, even if it wasn't requested
        if ua.AttributeIds.BrowseName not in self._columns:
            self._columns.append(ua.AttributeIds.BrowseName)

        self._data: Dict[ua.AttributeIds, Any] = {}

    async def _refresh_data(self) -> None:
        self._type_definition = await self.node.read_type_definition()

        values = await self.node.read_attributes(self._columns)
        for index, column in enumerate(self._columns):
            self.set_data(column, values[index].Value, emit=False)

    async def refresh_children(self) -> None:
        self.clear_children()  # Clear first

        children = await self.node.get_children()
        index = self.persistent_index(0)
        items = [
            OpcTreeItem(self._model, child, index, self._requested_columns)
            for child in children
        ]

        self._model.beginInsertRows(QModelIndex(index), 0, len(children) - 1)

        for task in asyncio.as_completed([_refresh_item(item) for item in items]):
            item = await task
            await self.add_child(item)

        self._model.endInsertRows()

        self._children_fetched = True

    def set_parent_index(self, index: QPersistentModelIndex) -> None:
        self._parent_index = index

    def children_fetched(self) -> bool:
        return self._children_fetched

    async def add_child(self, child: "OpcTreeItem") -> None:
        child.setParent(self)
        child.set_parent_index(self.persistent_index(0))
        child.data_changed.connect(self.data_changed)
        child.item_added.connect(self.item_added)
        child.item_removed.connect(self.item_removed)

        try:
            browse_name = child._data[ua.AttributeIds.BrowseName]
        except KeyError:
            await child._refresh_data()
            browse_name = child._data[ua.AttributeIds.BrowseName]

        # Maintain a sorted list here as we insert, so we don't have
        # to sort after the fact. Using a sorted container would be
        # more efficient, but it would be less clear and we really
        # aren't dealing with that many nodes here.
        destination_index = 0
        for index, sibling in enumerate(self._children):
            if browse_name < sibling._data[ua.AttributeIds.BrowseName]:
                break
            destination_index = index + 1

        self._children.insert(destination_index, child)
        self.item_added.emit(child)

    def child(self, row: int) -> Optional["OpcTreeItem"]:
        return self._children[row]

    def persistent_index(self, column) -> QPersistentModelIndex:
        if not self._parent_index.isValid():
            # This must be the root item
            return QPersistentModelIndex(self._model.index(0, 0))

        return QPersistentModelIndex(
            self._model.index(self.row(), column, QModelIndex(self._parent_index))
        )

    def clear_children(self, *, recursive=False) -> None:
        self._children_fetched = False
        children_count = self.child_count()
        if children_count == 0:
            return

        if recursive:
            for child in self._children:
                child.clear_children(recursive=True)

        index = QModelIndex(self.persistent_index(0))
        self._model.beginRemoveRows(index, 0, children_count - 1)

        for child in self._children:
            self.item_removed.emit(child)

        self._children.clear()

        self._model.endRemoveRows()

    def row(self) -> int:
        parent = cast("OpcTreeItem", self.parent())

        if parent is None:
            return 0

        return parent._children.index(self)

    def child_count(self) -> int:
        return len(self._children)

    def column_count(self) -> int:
        return len(self._requested_columns)

    def data(self, column: int) -> Any:
        return self._data[self._model_column_to_ua_column[column]]

    def icon(self) -> Optional[QIcon]:
        try:
            node_class = self._data[ua.AttributeIds.NodeClass]
        except KeyError:
            return None

        if node_class == ua.NodeClass.Object:
            if self._type_definition is None:
                return None

            if self._type_definition == ua.TwoByteNodeId(ua.ObjectIds.FolderType):
                return QIcon(":/folder.svg")
            else:
                return QIcon(":/object.svg")
        elif node_class == ua.NodeClass.Variable:
            if self._type_definition is None:
                return None

            if self._type_definition == ua.TwoByteNodeId(ua.ObjectIds.PropertyType):
                return QIcon(":/property.svg")
            else:
                return QIcon(":/variable.svg")
        elif node_class == ua.NodeClass.Method:
            return QIcon(":/method.svg")
        elif node_class == ua.NodeClass.ObjectType:
            return QIcon(":/object_type.svg")
        elif node_class == ua.NodeClass.VariableType:
            return QIcon(":/variable_type.svg")
        elif node_class == ua.NodeClass.DataType:
            return QIcon(":/data_type.svg")
        elif node_class == ua.NodeClass.ReferenceType:
            return QIcon(":/reference_type.svg")

        return None

    def set_data(
        self, attribute: ua.AttributeIds, value: ua.DataValue, *, emit: bool = True
    ) -> None:
        real_value = value.Value
        if isinstance(real_value, ua.LocalizedText):
            real_value = real_value.Text
        elif isinstance(real_value, ua.Variant):
            real_value = real_value.Value

        self._data[attribute] = real_value

        if emit:
            # Emit signal letting subscribers know what data has changed here
            index = QModelIndex(
                self.persistent_index(self._ua_column_to_model_column[attribute])
            )
            self.data_changed.emit(index, index)

    def __eq__(self, other) -> bool:
        if isinstance(other, OpcTreeItem):
            return self.node == other.node
        return False
