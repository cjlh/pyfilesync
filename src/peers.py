import socket
import json


class Peer():
    def __init__(self, name, ip_address, port):
        self.name = name
        self.ip_address = ip_address
        self.port = port

    def _get_response_size(self, sock, lpad=''):
        """Receives and parses size of response to recv from server"""
        metadata = b''
        while not(len(metadata) > 2 and metadata.decode('utf-8')[0] == '{' and
                  metadata.decode('utf-8')[-1] == '}'):
            metadata += sock.recv(1)
        metadata = metadata.decode('utf-8')
        try:
            metadata = json.loads(metadata)
        except json.decoder.JSONDecodeError:
            print(f'{lpad}Error: Response {metadata} could not be parsed as JSON. Abandoning.')
            # TODO: throw exception?
            return None
        if not('response_size' in metadata and type(metadata['response_size']) == int):
            print(f'{lpad}Error: Response size could not be parsed from server response.')
            # TODO: throw exception?
            return None
        return metadata['response_size']

    def recv_file_index(self, remote_name, lpad=''):
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.connect((self.ip_address, self.port))
        req_data = f'{{"request_type": 0, "remote_name": "{remote_name}"}}'.encode(
            'utf-8')
        print(f'{lpad}[send] request to {self.name} at ({self.ip_address}, {self.port}): '
              f'{req_data}')
        sock.sendall(req_data)
        response_size = self._get_response_size(sock, lpad=lpad)
        if response_size is None:
            return None
        res_data = sock.recv(response_size).decode('utf-8')
        print(f'{lpad}[recv] response: {res_data}')
        try:
            res_json = json.loads(res_data)
        except json.decoder.JSONDecodeError:
            print(f'{lpad}Error: Received FileIndex could not be parsed as JSON.')
            # TODO: throw exception?
            return None
        return res_json

    def recv_file_data(self, remote_name, filepath, lpad=''):
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.connect((self.ip_address, self.port))
        req_data = f'{{"request_type": 1, "remote_name": "{remote_name}", ' \
                   f'"filepath": "{filepath}"}}'.encode('utf-8')
        print(f'{lpad}[send] request to {self.name} at ({self.ip_address}, {self.port}): '
              f'{req_data}')
        sock.sendall(req_data)
        response_size = self._get_response_size(sock, lpad=lpad)
        if response_size is None:
            return None
        # receive raw bytes
        res_data = sock.recv(response_size)
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
