from asyncua.sync import Server
from PyQt5.QtTest import QSignalSpy
import pytest
import time


@pytest.fixture
def server(url):
    server = Server()
    namepace = server.register_namespace("custom_namespace")
    objects = server.nodes.root
    parent = objects.add_variable(namepace, "parent", 1.0)
    parent.add_variable(namepace, "child 1", 1.0)
    child = parent.add_variable(namepace, "child 2", 1.0)
    child.add_variable(namepace, "grandchild", 1.0)
    server.set_endpoint(url)
    server.start()
    yield server
    server.stop()


# def test_recursive_expand(client, server):
#     treeView = client.ui.treeView
#     parent_idx = treeView.model().itemFromIndex(treeView.model().index(0, 0)).child(3).index()
#     parent = treeView.model().itemFromIndex(parent_idx)
#     treeView.custom_expand(parent_idx)
#     treeView.expand_collapse_managers[parent_idx].expand_thread.wait()
#     signal = treeView.expanded
#     spy = QSignalSpy(signal)
#     spy.wait()
#     assert treeView.isExpanded(parent.index())
#     assert parent.child(0).text() == 'child 1'
#     assert parent.child(1).text() == 'child 2'
#     assert treeView.isExpanded(parent.child(1).index())
#     assert parent.child(1).child(0).text() == 'grandchild'


def test_recursive_collapse(client, server):
    treeView = client.ui.treeView
    parent_idx = (
        treeView.model().itemFromIndex(treeView.model().index(0, 0)).child(3).index()
    )
    parent = treeView.model().itemFromIndex(parent_idx)
    treeView.custom_expand(parent_idx)
    treeView.expand_collapse_managers[parent_idx].expand_thread.wait()
    signal = treeView.expanded
    spy = QSignalSpy(signal)
    spy.wait()

    treeView.custom_collapse(parent_idx)
    treeView.expand_collapse_managers[parent_idx].collapse_thread.wait()
    signal = treeView.collapsed
    spy = QSignalSpy(signal)
    spy.wait()
    assert not treeView.isExpanded(parent.index())
    assert parent.child(0).text() == "child 1"
    assert parent.child(1).text() == "child 2"
    assert not treeView.isExpanded(parent.child(1).index())
    assert parent.child(1).child(0).text() == "grandchild"


def test_recursive_collapse_stops_large_expand(client, server):
    treeView = client.ui.treeView
    root_idx = treeView.model().index(0, 0)
    treeView.custom_expand(root_idx)
    assert root_idx in treeView.expand_collapse_managers
    time.sleep(0.5)
    treeView.custom_collapse(root_idx)
    treeView.expand_collapse_managers[root_idx].collapse_thread.wait()
    assert not treeView.expand_collapse_managers[root_idx].expand_thread.isRunning()
