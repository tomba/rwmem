#!/usr/bin/python3

from PyQt6 import QtCore, QtGui, QtWidgets

import os
import sys
import socket

import rwmem as rw

from net import send_command

COLUMN_VALUE = 4
COLUMN_VALUE_BIN = COLUMN_VALUE + 1
COLUMN_VALUE_OLD = COLUMN_VALUE_BIN + 1
COLUMN_VALUE_BIN_OLD = COLUMN_VALUE_OLD + 1

TARGETS = [
#    {
#        'name': 'dss',
#        'type': 'mmap',
#        'file': '/dev/mem',
#        'address': 0x30200000,
#        'length': 0x10000,
#        'dev_path': '/sys/bus/platform/devices/30200000.dss',
#    },

    {
        'name': 'max96712',
        'type': 'i2c',
        'adapter': 1,
        'dev_address': 0x49,
        'address': 0,
        'length': 0x2000,
        'address_length': 2,
        'data_length': 1,
    },

    {
        'name': 'max9295a',
        'type': 'i2c',
        'adapter': 6,
        'dev_address': 0x40,
        'address': 0,
        'length': 0x2000,
        'address_length': 2,
        'data_length': 1,
    },
]

REGS = {
    'max96712': '/home/tomba/Documents/Encoders/Analog Devices/max96712/max96712.regs',
    'max9295a': '/home/tomba/Documents/Encoders/Analog Devices/max9295a/max9295a.regs',
}

class MainWindow(QtWidgets.QMainWindow):
    def __init__(self):
        super().__init__()

        HOST = 'buildroot.lab'
        PORT = 50008

        s = socket.create_connection((HOST, PORT))
        s.setsockopt(socket.SOL_TCP, socket.TCP_NODELAY, 1)
        self.conn = s

        for t in TARGETS:
            data = ('new-target', t)
            reply = send_command(self.conn, data)
            assert reply == True

        layout = QtWidgets.QVBoxLayout()

        button = QtWidgets.QPushButton('Refresh')
        button.clicked.connect(self.refresh_button_clicked)
        layout.addWidget(button)

        checkbox = QtWidgets.QCheckBox('Only changed')
        checkbox.clicked.connect(self.refresh_item_visibility)
        layout.addWidget(checkbox)
        self.checkbox = checkbox

        tree = QtWidgets.QTreeWidget()
        tree.setHeaderLabels(('Target', 'Block', 'Name', 'Address', 'Value', 'Binary', 'Old Value', 'Old Binary'))
        self.tree = tree

        fixedFont = QtGui.QFontDatabase.systemFont(QtGui.QFontDatabase.SystemFont.FixedFont)
        tree.setFont(fixedFont)

        self.gen_items(tree)

        layout.addWidget(tree)

        widget = QtWidgets.QWidget()
        widget.setLayout(layout)
        self.setCentralWidget(widget)

        #self.refresh()

    def refresh_item_visibility(self):
        show_only_changed = self.checkbox.isChecked()

        for i in range(self.tree.topLevelItemCount()):
            item = self.tree.topLevelItem(i)
            assert item

            if show_only_changed:
                changed = item.data(COLUMN_VALUE, QtCore.Qt.ItemDataRole.UserRole + 1)
                item.setHidden(not changed)
            else:
                item.setHidden(False)

    def gen_items(self, tree):
        def create_reg_treeitem(target_name, block_name, r: rw.Register):
            item = QtWidgets.QTreeWidgetItem(tree, (target_name, block_name, r.name, hex(r.offset)))
            item.setData(0, QtCore.Qt.ItemDataRole.UserRole, (target_name, r.offset))

            for f in r.values():
                subitem = QtWidgets.QTreeWidgetItem(item, (None, None, f.name, f'{f.high}:{f.low}'))
                subitem.setData(0, QtCore.Qt.ItemDataRole.UserRole, (f.high, f.low))

        for t in TARGETS:
            regs_path = REGS[t['name']]

            rf = rw.RegisterFile(regs_path)

            for rb in rf.values():
                for r in rb.values():
                    create_reg_treeitem(rf.name, rb.name, r)

    def refresh(self):
        tree = self.tree

        # collect items

        read_targets = {}

        for i in range(tree.topLevelItemCount()):
            item = tree.topLevelItem(i)
            assert item

            target_name, address = item.data(0, QtCore.Qt.ItemDataRole.UserRole)
            tag = i

            if target_name not in read_targets:
                read_targets[target_name] = []

            read_targets[target_name].append((address, tag))

        data = ('read', read_targets)
        reply = send_command(self.conn, data)
        #print('reply', reply)

        for target_name,addresses in reply.items():
            for address, value, tag in addresses:
                item = tree.topLevelItem(tag)
                assert item

                valuestr = hex(value)

                changed = item.text(COLUMN_VALUE) != valuestr
                item.setData(COLUMN_VALUE, QtCore.Qt.ItemDataRole.UserRole + 1, changed)

                self.set_item_w_change(item, COLUMN_VALUE_OLD, item.text(COLUMN_VALUE))
                self.set_item_w_change(item, COLUMN_VALUE_BIN_OLD, item.text(COLUMN_VALUE_BIN))

                self.set_item_w_change(item, COLUMN_VALUE, hex(value))
                self.set_item_w_change(item, COLUMN_VALUE_BIN, bin(value))

                self.refresh_fields(item, value)

        self.refresh_item_visibility()

    def refresh_fields(self, regitem: QtWidgets.QTreeWidgetItem, regvalue):
        for i in range(regitem.childCount()):
            item = regitem.child(i)
            assert item is not None

            high, low = item.data(0, QtCore.Qt.ItemDataRole.UserRole)

            mask = rw.helpers.genmask(high, low)
            value = (regvalue & mask) >> low

            self.set_item_w_change(item, COLUMN_VALUE_OLD, item.text(COLUMN_VALUE))
            self.set_item_w_change(item, COLUMN_VALUE_BIN_OLD, item.text(COLUMN_VALUE_BIN))

            self.set_item_w_change(item, COLUMN_VALUE, hex(value))
            self.set_item_w_change(item, COLUMN_VALUE_BIN, bin(value))

    def set_item_w_change(self, item: QtWidgets.QTreeWidgetItem, column:int, value: str):
        changed = value != item.text(column)
        brush = QtCore.Qt.GlobalColor.red if changed else QtCore.Qt.GlobalColor.black
        item.setText(column, value)
        item.setForeground(column, brush)

    def refresh_button_clicked(self):
        self.refresh()

    def keyPressEvent(self, event):
        if type(event) == QtGui.QKeyEvent:
            if event.key() == QtCore.Qt.Key.Key_F5:
                self.refresh()
            if event.key() == QtCore.Qt.Key.Key_Escape:
                #app = QtWidgets.QApplication.instance()
                self.close()


def main():
    app = QtWidgets.QApplication(sys.argv)

    window = MainWindow()
    window.resize(1280, 600)
    window.show()

    app.exec()

if __name__ == '__main__':
    sys.exit(main())
