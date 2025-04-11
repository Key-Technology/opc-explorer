from PyQt5.QtCore import Qt


async def test_model_columns(mainwindow):
    assert mainwindow._model.columnCount() == 4
    assert mainwindow._model.headerData(0, Qt.Orientation.Horizontal) == "Display Name"
    assert mainwindow._model.headerData(1, Qt.Orientation.Horizontal) == "Value"
    assert mainwindow._model.headerData(2, Qt.Orientation.Horizontal) == "Description"
    assert mainwindow._model.headerData(3, Qt.Orientation.Horizontal) == "Data Type"


async def test_model_is_updated_when_value_changes(
    mainwindow, async_server, wait_for_signal
):
    tree_model = mainwindow._model

    index = await async_server.register_namespace("test")
    objects_node = async_server.nodes.objects
    variable_node = await objects_node.add_variable(index, "TestVariable", 42)

    # Expand the root
    matches = tree_model.match(
        tree_model.index(0, 0),
        Qt.ItemDataRole.DisplayRole,
        "Root",
        1,
        Qt.MatchFlag.MatchExactly | Qt.MatchFlag.MatchRecursive,
    )
    assert len(matches) == 1

    async with wait_for_signal(
        tree_model.item_added,
        check_params_callback=lambda item: item.node == objects_node,
    ):
        mainwindow._ui.treeView.setExpanded(matches[0], True)

    # Expand objects
    matches = tree_model.match(
        tree_model.index(0, 0),
        Qt.ItemDataRole.DisplayRole,
        "Objects",
        1,
        Qt.MatchFlag.MatchExactly | Qt.MatchFlag.MatchRecursive,
    )
    assert len(matches) == 1
    async with wait_for_signal(
        tree_model.item_added,
        check_params_callback=lambda item: item.node == variable_node,
    ):
        mainwindow._ui.treeView.setExpanded(matches[0], True)

    # Find variable
    matches = tree_model.match(
        tree_model.index(0, 0),
        Qt.ItemDataRole.DisplayRole,
        "TestVariable",
        1,
        Qt.MatchFlag.MatchExactly | Qt.MatchFlag.MatchRecursive,
    )
    assert len(matches) == 1
    index = matches[0]

    # Confirm value
    assert index.siblingAtColumn(1).data() == "42"

    # Now change value in OPC and confirm it flows into the model via subscription
    async with wait_for_signal(tree_model.dataChanged):
        await variable_node.write_value(43)
    assert index.siblingAtColumn(1).data() == "43"
