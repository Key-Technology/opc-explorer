# Copied from uawidgets on 03/27/25 and made async

import pytest
import functools

from asyncua import ua
from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import QTreeView, QAbstractItemDelegate

from uaclient.attrs_ui import AttrsWidget


@pytest.fixture
def widget(application):
    view = QTreeView()
    widget = AttrsWidget(view, {})
    yield widget
    widget.deleteLater()
    view.deleteLater()


@pytest.fixture
def modify_item(widget, wait_for_signal):
    async def _modify(text, val, match_to_use=0):
        """
        modify the current item and set its displayed value to 'val'
        """
        idxlist = widget.model.match(
            widget.model.index(0, 0),
            Qt.DisplayRole,
            text,
            match_to_use + 1,
            Qt.MatchExactly | Qt.MatchRecursive,
        )
        if not idxlist:
            raise RuntimeError("Item with text '{}' not found".format(text))
        idx = idxlist[match_to_use]
        widget.view.setCurrentIndex(idx)
        idx = idx.sibling(idx.row(), 1)
        widget.view.edit(idx)
        editor = widget.view.focusWidget()
        if not editor:
            raise RuntimeError(
                "Could not get editor widget!, it does not have the focus"
            )

        if hasattr(editor, "_current_node"):
            editor._current_node = val
        elif hasattr(editor, "setCurrentText"):
            editor.setCurrentText(val)
        else:
            editor.setText(val)

        async with wait_for_signal(widget.attr_written):
            widget.view.commitData(editor)
            widget.view.closeEditor(editor, QAbstractItemDelegate.NoHint)
            widget.view.reset()

    return _modify


@pytest.fixture
def modify_value(modify_item):
    return functools.partial(modify_item, "Value", match_to_use=1)


async def test_display_objects_node(widget, async_server, modify_item):
    objects = async_server.nodes.objects
    await widget.show_attrs(objects)
    await modify_item("BrowseName", "5:titi")
    browse_name = await objects.read_browse_name()
    assert browse_name.to_string() == "5:titi"


async def test_display_var_double(widget, async_server, modify_value):
    objects = async_server.nodes.objects
    myvar = await objects.add_variable(1, "myvar1", 9.99, ua.VariantType.Double)
    await widget.show_attrs(myvar)
    await modify_value("8.45")
    value = await myvar.read_value()
    assert value == 8.45


async def test_display_var_bytes(widget, async_server, modify_value):
    objects = async_server.nodes.objects
    myvar = await objects.add_variable(
        1, "myvar_bytes", b"jkl", ua.VariantType.ByteString
    )
    await widget.show_attrs(myvar)
    await modify_value("titi")
    value = await myvar.read_value()
    assert value == b"titi"


# This doesn't work today, we need to port more sync things to async
# async def test_change_data_type(widget, async_server, modify_item, modify_value):
#     objects = async_server.nodes.objects
#     myvar = await objects.add_variable(1, "myvar1", 9.99, ua.VariantType.Double)
#     await widget.show_attrs(myvar)
#     dtype = await myvar.read_data_type()
#     assert dtype == ua.NodeId(ua.ObjectIds.Double)
#     new_dtype = ua.NodeId(ua.ObjectIds.String)
#     await modify_item("DataType", async_server.get_node(new_dtype))
#     dtype = await myvar.read_data_type()
#     assert dtype == new_dtype

#     # now try to write a value which is a string
#     await modify_value("mystring")
#     value = await myvar.read_value()
#     assert value == "mystring"


async def test_change_value_rank(
    widget, async_server, modify_item
):  # need to find a way to modify combo box with QTest
    objects = async_server.nodes.objects
    myvar = await objects.add_variable(1, "myvar1", 9.99, ua.VariantType.Double)
    await widget.show_attrs(myvar)
    await modify_item("ValueRank", "ThreeDimensions")
    rank = await myvar.read_value_rank()
    assert rank == ua.ValueRank.ThreeDimensions
