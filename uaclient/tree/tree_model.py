from PyQt5.QtCore import (
    pyqtSignal,
    Qt,
    QThreadPool,
)
from PyQt5.QtGui import QStandardItem, QIcon

from asyncua import ua
from asyncua.sync import new_node

from uawidgets.tree_widget import TreeViewModel

from uaclient.tree.node_value_item import NodeValueItem
from uaclient.tree.subscription_handler import SubscriptionHandler
from uaclient.tree.description_datatype_worker import DescriptionDatatypeWorker
from uaclient.tree.node_subscription_signal import NodeSubscriptionSignal


class TreeModel(TreeViewModel):

    description_datatype_added = pyqtSignal(object, object, object)

    def __init__(self, uaclient, node_signal_dict, data_change_manager):
        super().__init__()
        self.uaclient = uaclient
        self.test_item = 0
        self.node_signal_dict = node_signal_dict
        self.threadpool = QThreadPool()
        self.data_change_manager = data_change_manager
        self.subscription_handlers = {}

    # Copied from the opcua-widgets package and edited to fit this project
    # location: https://github.com/FreeOpcUa/opcua-widgets/blob/0bbfca198029a423fb6dd45fde0f60d7c57a5c00/uawidgets/tree_widget.py#L164
    # Copied and edited on 12/30/2024
    def set_root_node(self, node):
        desc = self._get_node_desc(node, is_root=True)
        self.add_item(desc, node=node, is_root=True)

    # Copied from the opcua-widgets package and edited to fit this project
    # location: https://github.com/FreeOpcUa/opcua-widgets/blob/0bbfca198029a423fb6dd45fde0f60d7c57a5c00/uawidgets/tree_widget.py#L168
    # Copied and edited on 12/30/2024
    def _get_node_desc(self, node, is_root=False):
        attrs = node.read_attributes(
            [
                ua.AttributeIds.DisplayName,
                ua.AttributeIds.BrowseName,
                ua.AttributeIds.NodeId,
                ua.AttributeIds.NodeClass,
            ]
        )
        desc = ua.ReferenceDescription()
        desc.DisplayName = attrs[0].Value.Value
        desc.BrowseName = attrs[1].Value.Value
        desc.NodeId = attrs[2].Value.Value
        desc.NodeClass = attrs[3].Value.Value
        if is_root:
            desc.TypeDefinition = ua.TwoByteNodeId(ua.ObjectIds.FolderType)
        return desc

    def tree_expanded(self, idx):
        if idx not in self.subscription_handlers:
            self.subscription_handlers[idx] = SubscriptionHandler(self, idx)

        if self.subscription_handlers[idx].subscribe_thread.isRunning():
            return
        self.subscription_handlers[idx].subscribe_thread.start()

    def tree_collapsed(self, idx):
        self.subscription_handlers[idx].unsubscribe_thread.start()

    def update_description_and_data_type(self, node, description, data_type):
        worker = DescriptionDatatypeWorker(node, description, data_type)
        self.threadpool.start(worker)

    # Copied from the opcua-widgets package and edited to fit this project
    # location: https://github.com/FreeOpcUa/opcua-widgets/blob/0bbfca198029a423fb6dd45fde0f60d7c57a5c00/uawidgets/tree_widget.py#L178
    # Copied and edited on 12/30/2024
    def add_item(self, desc, parent=None, node=None, is_root=False):
        dname = bname = nodeid = "No Value"
        dtype = value = description = None

        if not node:
            node = self.uaclient.get_node(desc.NodeId)

        if value == "None":
            value = ""
        if description == "no description":
            description = ""

        if desc.DisplayName:
            dname = desc.DisplayName.Text
        if desc.BrowseName:
            bname = desc.BrowseName.to_string()
        nodeid = desc.NodeId.to_string()
        item = [
            QStandardItem(dname),
            QStandardItem(bname),
            QStandardItem(nodeid),
            NodeValueItem(""),
            QStandardItem(description),
            QStandardItem(dtype),
        ]
        if desc.NodeClass == ua.NodeClass.Object:
            if desc.TypeDefinition == ua.TwoByteNodeId(ua.ObjectIds.FolderType):
                item[0].setIcon(QIcon(":/folder.svg"))
            else:
                item[0].setIcon(QIcon(":/object.svg"))
        elif desc.NodeClass == ua.NodeClass.Variable:
            if desc.TypeDefinition == ua.TwoByteNodeId(ua.ObjectIds.PropertyType):
                item[0].setIcon(QIcon(":/property.svg"))
            else:
                item[0].setIcon(QIcon(":/variable.svg"))
        elif desc.NodeClass == ua.NodeClass.Method:
            item[0].setIcon(QIcon(":/method.svg"))
        elif desc.NodeClass == ua.NodeClass.ObjectType:
            item[0].setIcon(QIcon(":/object_type.svg"))
        elif desc.NodeClass == ua.NodeClass.VariableType:
            item[0].setIcon(QIcon(":/variable_type.svg"))
        elif desc.NodeClass == ua.NodeClass.DataType:
            item[0].setIcon(QIcon(":/data_type.svg"))
        elif desc.NodeClass == ua.NodeClass.ReferenceType:
            item[0].setIcon(QIcon(":/reference_type.svg"))

        if is_root:
            item[0].setData(node, Qt.UserRole)
        else:
            parent_node = parent.data(Qt.UserRole)
            item[0].setData(new_node(parent_node, desc.NodeId), Qt.UserRole)

        self.node_signal_dict[nodeid] = NodeSubscriptionSignal()
        self.node_signal_dict[nodeid].signal.connect(item[3].update_value)
        self.description_datatype_added.emit(node, item[4], item[5])
        if parent:
            return parent.appendRow(item)
        else:
            return self.appendRow(item)
