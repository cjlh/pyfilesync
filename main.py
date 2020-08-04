import os
import socket
import json
import hashlib
from functools import partial
import tempfile
from threading import Thread


class Peer():
    def __init__(self, name, ip_address, port):
        self.name = name
        self.ip_address = ip_address
        self.port = port

    def recv_file_index(self):
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.connect((self.ip_address, self.port))
        req_data = f'{{"remote_name": "{self.name}"}}'.encode('utf-8')
        print(f'(send) request: {req_data}')
        sock.sendall(req_data)
        res_data = sock.recv(1024).decode('utf-8')
        print(f'(recv) response: {res_data}')
        return json.loads(res_data)


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


class Remote():
    def __init__(self, local_path, peers, name=None):
        self.name = name
        self.peer_aliases = peers
        self.path = local_path
        self.dir_name = os.path.basename(local_path)
        self.file_index = FileIndex(local_path)
    
    def get_name_string(self):
        return f"remote `{self.name}'" if \
            self.name is not None else 'unnamed remote'
    
    def update(self, alias_store):
        # 1: connect to remote hosts, request json-ified FileIndex objects
        print('Local FileIndex representation:\n  '
             f'{self.file_index.jsonify()}')
        file_indexes = {}
        for alias in self.peer_aliases:
            peer = alias_store.get_peer(alias)
            try:
                file_indexes[alias] = peer.recv_file_index()
            except (ConnectionRefusedError) as e:
                print(f'Warning: Connection refused by peer {peer.name} for '
                      f'remote {self.name} at {peer.ip_address}:{peer.port}')
        # convert to dicts
        pass
        # 2: compute changes
        # get set of all keys from dicts
        pass
        # iterate, combine into one dict with latest lm
        pass
        # get list of locally changed files to receive
        changed_files = []
        # 3: move old files to temp e.g. /tmp/pyfilesync/{self.dir_name}/
        tempdir = tempfile.gettempdir()
        # TODO: exist_ok?
        os.makedirs(os.path.join(tempdir, 'pyfilesync', self.dir_name),
                    exist_ok=True)
        for file in changed_files:
            # mv
            pass
        pass
        # 4: exchange files as necessary (use L3 proj code) and write
        pass


class FileIndex():
    def __init__(self, root_dir):
        self.root_dir = root_dir
        self.files = {}
        self.update()

    def update(self):
        for path, _, filenames in os.walk(self.root_dir):
            for filename in filenames:
                filepath = os.path.join(path,
                                        filename)[len(self.root_dir) + 1:]
                self.files[filepath] = File(self.root_dir, filepath)

    def print_files(self, lpad=''):
        for path, file in self.files.items():
            print(f'{lpad}{path}: {file.get_lm_time()}, '
                  f'{file.get_md5sum()}')
    
    def jsonify(self):
        return json.dumps({k: v.jsonify() for k, v in self.files.items()})


class File():
    def __init__(self, root_dir, rel_path):
        self.abs_path = os.path.join(root_dir, rel_path)
        self.rel_path = rel_path
        self.md5sum = None
    
    def get_lm_time(self):
        return os.path.getmtime(self.abs_path)
    
    def get_md5sum(self):
        if self.md5sum is None:
            self.update_md5sum()
            return self.md5sum
        else:
            return self.md5sum
    
    def update_md5sum(self):
        with open(self.abs_path, mode='rb') as f:
            d = hashlib.md5()
            for buf in iter(partial(f.read, 128), b''):
                d.update(buf)
        self.md5sum = d.hexdigest()
    
    def jsonify(self):
        return json.dumps({
            'md5sum': self.get_md5sum(),
            'last_modified': self.get_lm_time()
        })
    

class FileServer(Thread):
    def __init__(self, file_indexes, port):
        Thread.__init__(self)
        self.daemon = True

        self.port = port
        # TODO: mutex on fileindex?
        # file_indexes is a dict {remote_name: file_index}
        self.file_indexes = file_indexes

        self.start()
    
    def run(self):
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        server_addr = ('localhost', self.port)
        sock.bind(server_addr)
        sock.listen(1)
        while True:
            print('Waiting for connection...')
            conn, client_addr = sock.accept()
            print(f'Connection from {client_addr}')
            data = conn.recv(1024).decode('utf-8')
            parsed_data = json.loads(data)
            print(f'(recv) request: {parsed_data}')
            # TODO: validate request
            remote_name = parsed_data['remote_name']
            response_data = self.file_indexes[remote_name].jsonify()
            print(f'(send) response: {response_data}')
            conn.sendall(response_data.encode('utf-8'))
            conn.close()


def graceful_exit(status=0):
    print('Exiting.')
    exit(status)


def main():
    try:
        with open('config.json') as f:
            config = json.load(f)
    except (FileNotFoundError) as e:
        print('Error: Could not load config.json.')
        graceful_exit(1)

    # 1: ensure config format valid
    # TODO: validate
    # ensure all remotes are named and there are no duplicates
    remote_names = set()
    for remote in config['remotes']:
        if remote['name'] == None or remote['name'] == '':
            print('Error: Unnamed remote found in config.json.')
            graceful_exit(1)
        elif remote['name'] in remote_names:
            print(f"Error: Duplicate remote name `{remote['name']}` found.")
            graceful_exit(1)
        remote_names.add(remote['name'])

    # 2: Build alias store
    alias_store = AliasStore.from_alias_list(config['aliases'])

    # 3: ensure local dirs exist and peers are known, build file indexes
    remotes = []
    for remote in config['remotes']:
        # remote_name = f"remote `{remote['name']}'" if \
        #     remote['name'] is not None else 'unnamed remote'
        remote_name = remote['name']
        if os.path.isdir(remote['local_path']):
            print(f"✓ Local directory exists for {remote_name} at "
                  f"{remote['local_path']}")
            for peer in remote['peers']:
                if not alias_store.is_known(peer):
                    print(f"Error: Unknown peer `{peer}' in config for "
                        f"{remote_name}")
                    graceful_exit(1)
            print('Building index...', end='', flush=True)
            remotes.append(Remote(remote['local_path'], remote['peers'],
                                  name=remote['name']))
            print(' Done')
        else:
            print(f"✗ Local directory does not exist for {remote_name} at "
                  f"{remote['local_path']}")
            graceful_exit(1)

    # 4: check for updates
    for remote in remotes:
        print(f'Checking for updates on {remote.get_name_string()}...')
        # remote.file_index.print_files(lpad='  ')
        remotes[0].update(alias_store)
    
    # 5: open thread to listen for update requests
    file_indexes = {}
    for remote in remotes:
        file_indexes[remote.name] = remote.file_index
    print(f"Starting FileServer on port {config['port']}.")
    FileServer(file_indexes, config['port'])

    # 6: start update loop
    while True:
        pass


if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        graceful_exit(0)
