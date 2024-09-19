import socket, pickle

def recv_all(s: socket.socket, num_bytes: int):
    buffer = bytearray(num_bytes)
    mview = memoryview(buffer)

    bytes_received = 0

    while bytes_received < num_bytes:
        l = s.recv_into(mview[bytes_received:], num_bytes - bytes_received)
        if not l:
            return None
        bytes_received += l

    return buffer

def recv_pickle(s: socket.socket) -> object:
    len_bytes = recv_all(s, 4)
    if not len_bytes:
        return None

    l = int.from_bytes(len_bytes, 'big', signed=False)

    data_bytes = recv_all(s, l)
    if not data_bytes:
        return None

    data = pickle.loads(data_bytes)

    return data

def send_pickle(s: socket.socket, o: object):
    data_bytes = pickle.dumps(o)
    l = len(data_bytes)
    len_bytes = l.to_bytes(4, 'big', signed=False)

    s.sendall(len_bytes)
    s.sendall(data_bytes)

def send_command(s: socket.socket, cmd):
    send_pickle(s, cmd)
    return recv_pickle(s)
