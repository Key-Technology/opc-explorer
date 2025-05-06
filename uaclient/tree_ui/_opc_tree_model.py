from typing import Any, List, Union, Optional, overload
from qasync import asyncSlot
from PyQt5.QtCore import (
    Qt,
    QModelIndex,
    QPersistentModelIndex,
    pyqtSignal,
    QAbstractItemModel,
    QVariant,
    QObject,
)
from PyQt5.QtWidgets import QTreeView

from asyncua import Node
from asyncua import ua
from asyncua.ua import AttributeIds
import asyncio
from ._opc_tree_item import OpcTreeItem

_UA_ATTRIBUTE_NAMES = {
    AttributeIds.NodeId: "Node ID",
    AttributeIds.NodeClass: "Node Class",
    AttributeIds.BrowseName: "Browse Name",
    AttributeIds.DisplayName: "Display Name",
    AttributeIds.Description: "Description",
    AttributeIds.WriteMask: "Write Mask",
    AttributeIds.UserWriteMask: "User Write Mask",
    AttributeIds.IsAbstract: "Is Abstract",
    AttributeIds.Symmetric: "Symmetric",
    AttributeIds.InverseName: "Inverse Name",
    AttributeIds.ContainsNoLoops: "Contains No Loops",
    AttributeIds.EventNotifier: "Event Notifier",
    AttributeIds.Value: "Value",
    AttributeIds.DataType: "Data Type",
    AttributeIds.ValueRank: "Value Rank",
    AttributeIds.ArrayDimensions: "Array Dimensions",
    AttributeIds.AccessLevel: "Access Level",
    AttributeIds.UserAccessLevel: "User Access Level",
    AttributeIds.MinimumSamplingInterval: "Minimum Sampling Interval",
    AttributeIds.Historizing: "Historizing",
    AttributeIds.Executable: "Executable",
    AttributeIds.UserExecutable: "User Executable",
    AttributeIds.DataTypeDefinition: "Data Type Definition",
    AttributeIds.RolePermissions: "Role Permissions",
    AttributeIds.UserRolePermissions: "User Role Permissions",
    AttributeIds.AccessRestrictions: "Access Restrictions",
    AttributeIds.AccessLevelEx: "Access Level",
}


class OpcTreeModel(QAbstractItemModel):
    item_added = pyqtSignal(OpcTreeItem)
    item_removed = pyqtSignal(OpcTreeItem)

    def __init__(self, view: QTreeView, columns: List[AttributeIds]):
        super().__init__()
        self._columns = columns
        self._root_item = OpcTreeItem(self, None, QPersistentModelIndex(), columns)
        self._root_item.data_changed.connect(self._handle_data_changed)
        self._root_item.item_added.connect(self.item_added)
        self._root_item.item_removed.connect(self.item_removed)
        self._expand_tasks = None

        view.setModel(self)
        view.expanded.connect(self._handle_expanded)
        view.collapsed.connect(self._handle_collapsed)
        view.shift_click_expand.connect(self.trigger_expand)
        view.shift_click_collapse.connect(self.trigger_collapse)
        self.view = view

    def index(
        self, row: int, column: int, parent: QModelIndex = QModelIndex()
    ) -> QModelIndex:
        if not self.hasIndex(row, column, parent):
            return QModelIndex()

        parent_item = parent.internalPointer() if parent.isValid() else self._root_item
        child_item = parent_item.child(row)
        if child_item is None:
            return QModelIndex()

        return self.createIndex(row, column, child_item)

    @overload
    def parent(self, child: QModelIndex) -> QModelIndex: ...

    @overload
    def parent(self) -> Optional[QObject]: ...

    def parent(
        self, child: Optional[QModelIndex] = None
    ) -> Union[Optional[QObject], QModelIndex]:
        if child is None:
            return super().parent()

        if not child.isValid():
            return QModelIndex()

        child_item = child.internalPointer()
        parent_item = child_item.parent()

        if parent_item is None or parent_item == self._root_item:
            return QModelIndex()

        return self.createIndex(parent_item.row(), 0, parent_item)

    def rowCount(self, parent: QModelIndex = QModelIndex()) -> int:
        if parent.column() > 0:
            return 0

        parent_item = parent.internalPointer() if parent.isValid() else self._root_item
        if parent_item is None:
            return 0

        return parent_item.child_count()

    def columnCount(self, parent: QModelIndex = QModelIndex()) -> int:
        parent_item = parent.internalPointer() if parent.isValid() else self._root_item
        if parent_item is None:
            return 0

        return parent_item.column_count()

    def data(self, index: QModelIndex, role: int = Qt.ItemDataRole.DisplayRole) -> Any:
        if not index.isValid():
            return None

        item = index.internalPointer()
        if role == Qt.ItemDataRole.DisplayRole:
            return item.data(index.column())

        if role == Qt.ItemDataRole.DecorationRole and index.column() == 0:
            return item.icon()

    async def set_root_node(self, node: Node):
        index = self.index(0, 0)
        item = OpcTreeItem(self, node, QPersistentModelIndex(), self._columns)

        self.beginInsertRows(index, 0, 0)
        await self._root_item.add_child(item)
        self.endInsertRows()

    def hasChildren(self, parent: QModelIndex = QModelIndex()) -> bool:
        item = parent.internalPointer()

        if not parent.isValid() or item.children_fetched():
            return super().hasChildren(parent)

        return True

    def headerData(
        self,
        section: int,
        orientation: Qt.Orientation,
        role: int = Qt.ItemDataRole.DisplayRole,
    ) -> QVariant:
        if (
            role == Qt.ItemDataRole.DisplayRole
            and orientation == Qt.Orientation.Horizontal
        ):
            return QVariant(_UA_ATTRIBUTE_NAMES[self._columns[section]])
        return QVariant()

    def clear(self) -> None:
        self._root_item.clear_children(recursive=True)

    @asyncSlot(QModelIndex, QModelIndex)
    async def _handle_data_changed(
        self, start_index: QModelIndex, end_index: QModelIndex
    ) -> None:
        self.dataChanged.emit(start_index, end_index)

    @asyncSlot(QModelIndex)
    async def _handle_expanded(self, index: QModelIndex) -> None:
        if not index.isValid():
            return

        # Refresh the children for the item that was just expanded
        item = index.internalPointer()

        if not item.is_refreshing_children:
            await item.refresh_children()

        if self.view.hasShiftExpanded:
            self.view.hasShiftExpanded = False
            text = item.data(0)
            item.set_data(ua.AttributeIds.DisplayName, ua.DataValue("loading..."))
            await self.custom_expand(index)
            item.set_data(ua.AttributeIds.DisplayName, ua.DataValue(text))

    @asyncSlot(QModelIndex)
    async def _handle_collapsed(self, index: QModelIndex) -> None:
        if not index.isValid():
            return

        # Clear the children for the item just collapsed
        item = index.internalPointer()
        item.clear_children()

    @asyncSlot(QModelIndex)
    async def custom_expand(self, idx):
        if not idx.isValid():
            return
        item = idx.internalPointer()

        children = []

        children.append(item)
        while len(children) > 0:
            if not self.view.isExpanded(idx):
                break
            child_item = children[0]
            tasks = set()
            for i in range(0, child_item.child_count()):

                child = child_item.child(i)

                index = QModelIndex(child.persistent_index(0))
                if not self.view.isExpanded(idx):
                    break
                if len(await child.node.get_children_descriptions()) > 0:
                    children.append(child)
                    child.is_refreshing_children = True
                    self.view.expand(index)
                    task = asyncio.create_task(child.refresh_children())
                    tasks.add(task)
            try:
                await asyncio.gather(*tasks)
            except ValueError:
                pass
            children.pop(0)

    @asyncSlot(QModelIndex)
    async def trigger_expand(self, idx):
        self.view.setExpanded(idx, True)

    @asyncSlot(QModelIndex)
    async def trigger_collapse(self, idx):
        self.view.setExpanded(idx, False)
