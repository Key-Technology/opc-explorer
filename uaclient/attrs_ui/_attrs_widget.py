# Copied from uawidgets on 03/27/25 and made async

import logging
import functools
import contextlib
import asyncio
from enum import Enum
from dataclasses import fields

from PyQt5.QtCore import pyqtSignal, Qt, QObject, QSettings
from PyQt5.QtGui import QStandardItemModel, QStandardItem
from PyQt5.QtWidgets import (
    QApplication,
    QMenu,
    QAction,
    QStyledItemDelegate,
    QComboBox,
    QVBoxLayout,
    QCheckBox,
    QDialog,
    QAbstractItemView,
)

from asyncua import ua
from asyncua.common.ua_utils import string_to_val, val_to_string, data_type_to_string
from asyncua.ua.uatypes import type_string_from_type

from uawidgets.utils import trycatchslot

from qasync import asyncSlot

logger = logging.getLogger(__name__)


def robust(func):
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except Exception:
            logger.exception("failed to call %s with args: %s %s", func, args, kwargs)

    return wrapper


class BitEditor(QDialog):
    """
    Edit bits in data
    FIXME: this should be a dialog but a Widget appearing directly in treewidget
    Patch welcome
    """

    def __init__(self, parent, attr, val):
        QDialog.__init__(self, parent)
        layout = QVBoxLayout(self)
        self.setLayout(layout)
        self.boxes = []
        self.enum = attr_to_enum(attr)
        for el in self.enum:
            box = QCheckBox(el.name, parent)
            layout.addWidget(box)
            self.boxes.append(box)
            if ua.ua_binary.test_bit(val, el.value):
                box.setChecked(True)
            else:
                box.setChecked(False)

    def get_byte(self):
        data = 0
        for box in self.boxes:
            if box.isChecked():
                data = ua.ua_binary.set_bit(data, self.enum[box.text()].value)
        return data


class _Data(object):
    def is_editable(self):
        if self.uatype != ua.VariantType.ExtensionObject:
            return True
        return False


class AttributeData(_Data):
    def __init__(self, attr, value, uatype):
        self.attr = attr
        self.value = value
        self.uatype = uatype


class MemberData(_Data):
    def __init__(self, obj, name, value, uatype):
        self.obj = obj
        self.name = name
        self.value = value
        self.uatype = uatype


class ListData(_Data):
    def __init__(self, mylist, idx, val, uatype):
        self.mylist = mylist
        self.idx = idx
        self.value = val
        self.uatype = uatype


class AttrsWidget(QObject):

    error = pyqtSignal(Exception)
    attr_written = pyqtSignal(ua.AttributeIds, ua.DataValue)

    def __init__(self, view, subscription_data):
        QObject.__init__(self, view)
        self.view = view
        self._timestamps = True
        self._subscription_data = subscription_data
        delegate = MyDelegate(self.view, self)
        delegate.error.connect(self.error.emit)
        delegate.attr_written.connect(self.attr_written.emit)
        self.view.setItemDelegate(delegate)
        self.model = QStandardItemModel()
        self.model.setHorizontalHeaderLabels(["Attribute", "Value", "DataType"])
        self.view.setModel(self.model)
        self.current_node = None
        self.view.header().setSectionResizeMode(0)
        self.view.header().setStretchLastSection(True)
        self.view.expanded.connect(self._item_expanded)
        self.view.collapsed.connect(self._item_collapsed)
        self.view.setEditTriggers(QAbstractItemView.DoubleClicked)

        # Context menu
        self.view.setContextMenuPolicy(Qt.CustomContextMenu)
        self.view.customContextMenuRequested.connect(self.showContextMenu)
        copyaction = QAction("&Copy Value", self.model)
        copyaction.triggered.connect(self._copy_value)
        self._contextMenu = QMenu()
        self._contextMenu.addAction(copyaction)

    def save_state(self, settings: QSettings):
        settings.setValue("header/state", self.view.header().saveState())

    def load_state(self, settings: QSettings):
        state = settings.value("header/state", None)
        if state is not None:
            self.view.header().restoreState(state)

    def _item_expanded(self, idx):
        if not idx.parent().isValid():
            # only for value attributes which a re childs
            # maybe add more tests
            return
        it = self.model.itemFromIndex(idx.sibling(0, 1))
        it.setText("")

    def _item_collapsed(self, idx):
        it = self.model.itemFromIndex(idx.sibling(0, 1))
        data = it.data(Qt.ItemDataRole.UserRole)
        it.setText(val_to_string(data.value))

    def showContextMenu(self, position):
        item = self.get_current_item()
        if item:
            self._contextMenu.exec_(self.view.viewport().mapToGlobal(position))

    def get_current_item(self, col_idx=0):
        idx = self.view.currentIndex()
        idx = idx.siblingAtColumn(col_idx)
        return self.model.itemFromIndex(idx)

    def _copy_value(self, position):
        it = self.get_current_item(1)
        if it:
            QApplication.clipboard().setText(it.text())

    def clear(self):
        # remove all rows but not header!!
        self.model.removeRows(0, self.model.rowCount())

    @asyncSlot()
    async def reload(self):
        await self.show_attrs(self.current_node)

    def _set_value(self, dv: ua.DataValue):
        items = self.model.findItems("Value")
        if len(items) != 1:
            raise RuntimeError(f"Expected a single value item, got {len(items)}")

        self._update_value_attr(items[0], ua.AttributeIds.Value, dv)

    async def show_attrs(self, node):
        if self.current_node is not None and self.current_node != node:
            with contextlib.suppress(TypeError, KeyError):
                self._subscription_data[
                    self.current_node.nodeid
                ].signal.signal.disconnect(self._set_value)

        self.current_node = node
        self.clear()
        if self.current_node:
            await self._show_attrs()
        self.view.expandToDepth(0)

        with contextlib.suppress(KeyError):
            self._subscription_data[self.current_node.nodeid].signal.signal.connect(
                self._set_value
            )

    async def _show_attrs(self):
        attrs = await self.get_all_attrs()
        for attr, dv in attrs:
            try:
                # try/except to show as many attributes as possible
                if attr == ua.AttributeIds.Value:
                    self._show_value_attr(attr, dv)
                elif attr == ua.AttributeIds.DataTypeDefinition:
                    self._show_sdef_attr(attr, dv)
                else:
                    self._show_attr(attr, dv)
            except Exception as ex:
                logger.exception(
                    "Exception while displaying attribute %s with value %s for node %s",
                    attr,
                    dv,
                    self.current_node,
                )
                self.error.emit(ex)

    def _show_attr(self, attr, dv):
        if attr == ua.AttributeIds.DataType:
            # FIXME: Could query for browsename here, it does not cost much
            string = data_type_to_string(dv.Value.Value)
        elif attr in (
            ua.AttributeIds.AccessLevel,
            ua.AttributeIds.UserAccessLevel,
            ua.AttributeIds.WriteMask,
            ua.AttributeIds.UserWriteMask,
            ua.AttributeIds.EventNotifier,
        ):
            string = enum_to_string(attr, dv.Value.Value)
        else:
            string = val_to_string(dv.Value.Value)
        name_item = QStandardItem(attr.name)
        vitem = QStandardItem(string)
        vitem.setData(
            AttributeData(attr, dv.Value.Value, dv.Value.VariantType),
            Qt.ItemDataRole.UserRole,
        )
        self.model.appendRow(
            [name_item, vitem, QStandardItem(dv.Value.VariantType.name)]
        )

    def _show_value_attr(self, attr, dv):
        name_item = QStandardItem("Value")
        self._update_value_attr(name_item, attr, dv)

        vitem = QStandardItem()
        row = [name_item, vitem, QStandardItem(dv.Value.VariantType.name)]
        self.model.appendRow(row)

    def _update_value_attr(self, item: QStandardItem, attr, dv):
        item.removeRows(0, item.rowCount())  # Remove all children before adding more

        items = self._show_val(
            item, None, "Value", dv.Value.Value, dv.Value.VariantType
        )
        items[1].setData(
            AttributeData(attr, dv.Value.Value, dv.Value.VariantType),
            Qt.ItemDataRole.UserRole,
        )
        self._show_timestamps(item, dv)

    def _show_sdef_attr(self, attr, dv):
        if dv.Value.Value is None:
            return
        items = self._show_val(
            self.model, None, "DataTypeDefinition", dv.Value.Value, dv.Value.VariantType
        )
        items[1].setData(
            AttributeData(attr, dv.Value.Value, dv.Value.VariantType),
            Qt.ItemDataRole.UserRole,
        )

    @robust
    def _show_val(self, parent, obj, name, val, vtype):
        name_item = QStandardItem(name)
        vitem = QStandardItem()
        vitem.setText(val_to_string(val))
        vitem.setData(MemberData(obj, name, val, vtype), Qt.ItemDataRole.UserRole)
        row = [name_item, vitem, QStandardItem(str(vtype))]
        # if we have a list or extension object we display children
        if isinstance(val, list):
            row[2].setText("List of " + str(vtype))
            self._show_list(name_item, val, vtype)
        elif vtype == ua.VariantType.ExtensionObject:
            self._show_ext_obj(name_item, val)
        parent.appendRow(row)
        return row

    @robust
    def _show_list(self, parent, mylist, vtype):
        for idx, val in enumerate(mylist):
            name_item = QStandardItem(str(idx))
            vitem = QStandardItem()
            vitem.setText(val_to_string(val))
            vitem.setData(ListData(mylist, idx, val, vtype), Qt.ItemDataRole.UserRole)
            vtypename = vtype.name if isinstance(vtype, Enum) else str(vtype)
            row = [name_item, vitem, QStandardItem(vtypename)]
            parent.appendRow(row)
            if vtype == ua.VariantType.ExtensionObject or not isinstance(
                vtype, ua.VariantType
            ):
                self._show_ext_obj(name_item, val)

    def refresh_list(self, parent, mylist, vtype):
        while parent.hasChildren():
            self.model.removeRow(0, parent.index())
        self._show_list(parent, mylist, vtype)

    @robust
    def _show_ext_obj(self, item, val):
        item.setText(item.text() + ": " + val.__class__.__name__)
        if val is None:
            self._show_val(item, val, "Value", None, ua.VariantType.Null)
            return
        for field in fields(val):
            member_val = getattr(val, field.name)
            att_type = type_string_from_type(field.type)
            if hasattr(ua.VariantType, att_type):
                attr = getattr(ua.VariantType, att_type)
            elif hasattr(ua, att_type):
                attr = getattr(ua, att_type)
            else:
                return
            self._show_val(item, val, field.name, member_val, attr)

    def _show_timestamps(self, item, dv):
        # while item.hasChildren():
        # self.model.removeRow(0, item.index())
        string = val_to_string(dv.ServerTimestamp)
        item.appendRow(
            [
                QStandardItem("Server Timestamp"),
                QStandardItem(string),
                QStandardItem(ua.VariantType.DateTime.name),
            ]
        )
        string = val_to_string(dv.SourceTimestamp)
        item.appendRow(
            [
                QStandardItem("Source Timestamp"),
                QStandardItem(string),
                QStandardItem(ua.VariantType.DateTime.name),
            ]
        )

    async def get_all_attrs(self):
        attrs = [attr for attr in ua.AttributeIds]
        dvs = await self.current_node.read_attributes(attrs)
        res = []
        for idx, dv in enumerate(dvs):
            if dv.StatusCode.is_good():
                res.append((attrs[idx], dv))
        res.sort(key=lambda x: x[0].name)
        return res


class MyDelegate(QStyledItemDelegate):

    error = pyqtSignal(Exception)
    attr_written = pyqtSignal(ua.AttributeIds, ua.DataValue)

    def __init__(self, parent, attrs_widget):
        QStyledItemDelegate.__init__(self, parent)
        self.attrs_widget = attrs_widget

    @trycatchslot
    def createEditor(self, parent, option, idx):
        if idx.column() != 1:
            return None
        item = self.attrs_widget.model.itemFromIndex(idx)
        data = item.data(Qt.ItemDataRole.UserRole)
        if not data.is_editable():
            return None
        text = item.text()
        if isinstance(data, (ListData, MemberData)):
            return QStyledItemDelegate.createEditor(self, parent, option, idx)
        elif data.attr == ua.AttributeIds.NodeId:
            return None
        elif data.uatype == ua.VariantType.Boolean:
            combo = QComboBox(parent)
            combo.addItem("True")
            combo.addItem("False")
            combo.setCurrentText(text)
            return combo
        elif data.attr == ua.AttributeIds.NodeClass:
            combo = QComboBox(parent)
            for nclass in ua.NodeClass:
                combo.addItem(nclass.name)
            combo.setCurrentText(text)
            return combo
        elif data.attr == ua.AttributeIds.ValueRank:
            combo = QComboBox(parent)
            for rank in ua.ValueRank:
                combo.addItem(rank.name)
            combo.setCurrentText(text)
            return combo
        # kyrofa (04/02/25): Not supporting this for now, will need to port more
        # sync stuff to async to pull it off
        # elif data.attr == ua.AttributeIds.DataType:
        #     nodeid = data.value
        #     node = Node(self.attrs_widget.current_node.session, nodeid)
        #     startnode = Node(
        #         self.attrs_widget.current_node.session, ua.ObjectIds.BaseDataType
        #     )
        #     button = GetNodeButton(parent, node, startnode)
        #     return button
        elif data.attr in (
            ua.AttributeIds.AccessLevel,
            ua.AttributeIds.UserAccessLevel,
            ua.AttributeIds.WriteMask,
            ua.AttributeIds.UserWriteMask,
            ua.AttributeIds.EventNotifier,
        ):
            return BitEditor(parent, data.attr, data.value)
        else:
            return QStyledItemDelegate.createEditor(self, parent, option, idx)

    @trycatchslot
    def setModelData(self, editor, model, idx):
        # if user is setting a value on a null variant, try using the nodes datatype instead
        data = model.data(idx, Qt.ItemDataRole.UserRole)

        if isinstance(data, AttributeData):
            asyncio.create_task(
                self._write_attribute_data(
                    self.attrs_widget.current_node, data, editor, model, idx
                )
            )
        elif isinstance(data, MemberData):
            self._set_member_data(data, editor, model, idx)
        elif isinstance(data, ListData):
            self._set_list_data(data, editor, model, idx)
        else:
            logger.info("Error while setting model data, data is %s", data)

    def _set_list_data(self, data, editor, model, idx):
        text = editor.text()
        data.mylist[data.idx] = string_to_val(text, data.uatype)
        model.setItemData(idx, {Qt.DisplayRole: text, Qt.ItemDataRole.UserRole: data})
        attr_data = self._get_attr_data(idx, model)
        asyncio.create_task(self._write_attr(self.attrs_widget.current_node, attr_data))

    def _set_member_data(self, data, editor, model, idx):
        val = string_to_val(editor.text(), data.uatype)
        data.value = val
        model.setItemData(
            idx, {Qt.DisplayRole: editor.text(), Qt.ItemDataRole.UserRole: data}
        )
        setattr(data.obj, data.name, val)
        attr_data = self._get_attr_data(idx, model)
        asyncio.create_task(self._write_attr(self.attrs_widget.current_node, attr_data))

    def _get_attr_data(self, idx, model):
        while True:
            idx = idx.parent()
            it = model.itemFromIndex(idx.sibling(0, 1))
            data = it.data(Qt.ItemDataRole.UserRole)
            if isinstance(data, AttributeData):
                return data

    def _get_parent_data(self, idx, model):
        parent_idx = idx.parent()
        it = model.itemFromIndex(parent_idx.sibling(0, 1))
        return parent_idx, it.data(Qt.ItemDataRole.UserRole)

    async def _write_attribute_data(self, node, data, editor, model, idx):
        if data.attr is ua.AttributeIds.Value:
            # for value we checkd data type from the variable data type
            # this is more robust
            try:
                data.uatype = await node.read_data_type_as_variant_type()
            except Exception as ex:
                logger.exception(
                    "Could get primitive type of variable %s",
                    node,
                )
                self.error.emit(ex)
                raise

        if data.attr == ua.AttributeIds.NodeClass:
            data.value = ua.NodeClass[editor.currentText()]
            text = editor.currentText()
        elif data.attr == ua.AttributeIds.ValueRank:
            data.value = ua.ValueRank[editor.currentText()]
            text = editor.currentText()
        elif data.attr == ua.AttributeIds.DataType:
            data.value = editor.get_node().nodeid
            text = data_type_to_string(data.value)
        elif data.attr in (
            ua.AttributeIds.AccessLevel,
            ua.AttributeIds.UserAccessLevel,
            ua.AttributeIds.WriteMask,
            ua.AttributeIds.UserWriteMask,
            ua.AttributeIds.EventNotifier,
        ):
            data.value = editor.get_byte()
            text = enum_to_string(data.attr, data.value)
        else:
            if isinstance(editor, QComboBox):
                text = editor.currentText()
            else:
                text = editor.text()
            data.value = string_to_val(text, data.uatype)
        model.setItemData(idx, {Qt.DisplayRole: text, Qt.ItemDataRole.UserRole: data})
        await self._write_attr(node, data)
        if isinstance(data.value, list):
            # we need to refresh children
            item = self.attrs_widget.model.itemFromIndex(idx.sibling(0, 0))
            self.attrs_widget.refresh_list(item, data.value, data.uatype)

    async def _write_attr(self, node, data):
        dv = ua.DataValue(ua.Variant(data.value, VariantType=data.uatype))
        try:
            logger.info(
                "Writing attribute %s of node %s with value: %s",
                data.attr,
                node,
                dv,
            )
            await node.write_attribute(data.attr, dv)
        except Exception as ex:
            logger.exception("Exception while writing %s to %s", dv, data.attr)
            self.error.emit(ex)
        else:
            self.attr_written.emit(data.attr, dv)


def attr_to_enum(attr):
    attr_name = attr.name
    if attr_name.startswith("User"):
        attr_name = attr_name[4:]
    return getattr(ua, attr_name)


def enum_to_string(attr, val):
    attr_enum = attr_to_enum(attr)
    string = ", ".join([e.name for e in attr_enum.parse_bitfield(val)])
    return string
