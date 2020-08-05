import socket
import json


class Peer():
    def __init__(self, name, ip_address, port):
        self.name = name
        self.ip_address = ip_address
        self.port = port

    def recv_file_index(self, remote_name, lpad=''):
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.connect((self.ip_address, self.port))
        req_data = f'{{"request_type": 0, "remote_name": "{remote_name}"}}'.encode(
            'utf-8')
        print(f'{lpad}[send] request to {self.name} at ({self.ip_address}, {self.port}): '
              f'{req_data}')
        sock.sendall(req_data)
        res_data = sock.recv(1024).decode('utf-8')
        print(f'{lpad}[recv] response: {res_data}')
        return json.loads(res_data)

    def recv_file_data(self, remote_name, filepath, lpad=''):
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.connect((self.ip_address, self.port))
        req_data = f'{{"request_type": 1, "remote_name": "{remote_name}", ' \
                   f'"filepath": "{filepath}"}}'.encode('utf-8')
        print(f'{lpad}[send] request to {self.name} at ({self.ip_address}, {self.port}): '
              f'{req_data}')
        sock.sendall(req_data)
        # receive raw bytes
        res_data = sock.recv(1024)
        print(f'{lpad}[recv] response: {res_data}')
        return res_data


class AliasStore():
    def __init__(self, aliases):
        self.aliases = aliases

    def is_known(self, alias):
        return alias in self.aliases

    def get_peer(self, alias):
        if self.is_known(alias):
            return self.aliases[alias]
        else:
            # TODO: key error?
            return None

    @classmethod
    def from_alias_list(cls, peers):
        aliases = {}
        for peer in peers:
            aliases[peer['name']] = Peer(peer['name'], peer['ip_address'],
                                         peer['port'])
        return cls(aliases)
