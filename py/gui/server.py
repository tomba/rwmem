#!/usr/bin/python3

import socket
import sys
from typing import ParamSpecArgs

import rwmem as rw

from net import recv_pickle, send_pickle

class Client:
    def __init__(self, conn) -> None:
        self.conn = conn
        self.targets = {}

        self.cmds = {
            'new-target': self.handle_cmd_new_target,
            'read': self.handle_cmd_read,
        }

    def handle(self, data):
        cmd, data = data

        reply = self.cmds[cmd](data)

        return reply

    def check_pm_active(self, target_name):
        target_data = self.targets[target_name]

        if not target_data['pm_status']:
            return True

        s = open(target_data['pm_status']).readline().strip()

        return s == 'active'

    def handle_cmd_new_target(self, data):
        target_type = data['type']
        name = data['name']

        if target_type == 'mmap':
            target = rw.MMapTarget(data['file'], data['address'], data['length'],
                                   rw.Endianness.Default, 4)
            pm_status = data['dev_path'] + '/power/runtime_status'
        elif target_type == 'i2c':
            i2c_addr_len = data['address_length']
            i2c_data_len = data['data_length']
            target = rw.I2CTarget(data['adapter'], data['dev_address'],
                                  data['address'], data['length'],
                                  rw.Endianness.Big, i2c_addr_len, rw.Endianness.Big, i2c_data_len)
            pm_status = None
        else:
            raise RuntimeError()

        self.targets[name] = {
            'target': target,
            'pm_status': pm_status,
        }

        # We could set /sys/bus/platform/devices/30200000.dss/power/control to 'on''

        return True

    def handle_cmd_read(self, data):
        reply = {}

        #print('data', data)
        for target_name, addresses in data.items():
            if not self.check_pm_active(target_name):
                continue

            target_data = self.targets[target_name]
            target = target_data['target']

            if target_name not in reply:
                reply[target_name] = []

            for address, tag in addresses:
                reply[target_name].append( (address, target.read(address), tag) )

        #print('reply', reply)
        return reply


class Server:
    def run(self):
        HOST = '0.0.0.0'
        PORT = 50008

        s = socket.create_server((HOST, PORT))
        s.setsockopt(socket.SOL_TCP, socket.TCP_NODELAY, 1)
        s.listen()

        while True:
            print("Waiting for a connection...")

            conn, addr = s.accept()

            print('Connected', addr)

            self.run_client(conn)

    def run_client(self, conn):
        client = Client(conn)

        while True:
            data = recv_pickle(conn)
            if not data:
                break

            #print('recv', data)

            reply = client.handle(data)

            send_pickle(conn, reply)

def main():
    server = Server()

    server.run()

if __name__ == '__main__':
    sys.exit(main())
