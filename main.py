import os
import argparse
import socket
import json
import hashlib
from functools import partial
import time
import tempfile
from threading import Thread

from notifypy import Notify


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

    def update(self, alias_store, lpad=''):
        # 1: connect to remote hosts, request json-ified FileIndex objects
        print(f'{lpad}Local FileIndex representation: {self.file_index.jsonify()}')
        file_indexes = {}
        for alias in self.peer_aliases:
            peer = alias_store.get_peer(alias)
            try:
                file_indexes[alias] = peer.recv_file_index(self.name, lpad=lpad)
            except (ConnectionRefusedError) as e:
                # TODO: use e?
                print(f'{lpad}Warning: Connection refused by peer `{peer.name}\' for '
                      f'remote `{self.name}\' at {peer.ip_address}:{peer.port}. Peer may '
                      'be offline.')
        if len(file_indexes) == 0:
            print(f'{lpad}No peers available for update. Abandoning.')
            return
        # 2: compute changes between dicts based on md5 hashes
        # iterate, combine into one dict with latest lm and peer
        latest_changes = {}
        for alias, file_index in file_indexes.items():
            for filename, details in file_index.items():
                # TODO: check filename is not exploitative
                # os.dir.join(self.path, filename) is subdir of self.path
                if (filename not in latest_changes or latest_changes[filename][
                        'last_modified'] < details['last_modified']):
                    latest_changes[filename] = {
                        'md5sum': details['md5sum'],
                        'last_modified': details['last_modified'],
                        'peer_alias': alias
                    }
            # all_filepaths = all_filepaths.union(set(file_index.keys()))
        print(f'{lpad}Latest changes from peers: {latest_changes}')
        # get all filenames
        all_filepaths = set(latest_changes.keys())
        for filepath, file in self.file_index.items():
            all_filepaths.add(filepath)
        print(f'{lpad}All files: {all_filepaths}')
        # get list of locally changed files to receive and peer to receive from
        changed_files = []
        for filepath in all_filepaths:
            if self.file_index.is_filepath_in_index(filepath):
                file = self.file_index.get_file(filepath)
                if (filepath in latest_changes and
                        latest_changes[filepath]['last_modified'] > file.get_lm_time() and
                        latest_changes[filepath]['md5sum'] != file.get_md5sum()):
                    changed_files.append(filepath)
            else:
                changed_files.append(filepath)
        if len(changed_files) == 0:
            print(f'{lpad}0 files to update. Done.')
            return
        else:
            print(f"{lpad}{len(changed_files)} "
                  f"{'file' if len(changed_files) == 1 else 'files'} to update: "
                  f"{changed_files}")
        # 3: download to temp folder
        temp_dir_root = tempfile.gettempdir()
        temp_dir = os.path.join(temp_dir_root, 'pyfilesync', self.dir_name,
                                str(get_timestamp()))
        os.makedirs(temp_dir, exist_ok=True)
        backup_dir = os.path.join(temp_dir, 'backup')
        os.makedirs(backup_dir)
        for filename in changed_files:
            # TODO: makedirs for files that are in a subdir
            target_peer = alias_store.get_peer(latest_changes[filename]['peer_alias'])
            file_data = target_peer.recv_file_data(self.name, filename, lpad=lpad)
            temp_path = os.path.join(temp_dir, filename)
            with open(temp_path, 'wb') as f:
                f.write(file_data)
            print(f'{lpad}Wrote updated file `{filename}\' to {temp_path} '
                  f'({len(file_data)} bytes).')
        # 4: move old files to temp backup folder, move new files to folder
        for filename in changed_files:
            # move old if exists
            target_path = os.path.join(self.path, filename)
            if os.path.exists(target_path):
                os.rename(target_path, os.path.join(backup_dir, filename))
            # move new
            os.rename(os.path.join(temp_dir, filename), target_path)
            print(f'{lpad}Updated file `{filename}.\'')
            update_message = f"{self.name}: Updated file {filename} from peer " \
                             f"{latest_changes[filename]['peer_alias']}"
            send_desktop_notification(update_message)
        # 5: update FileIndex
        self.file_index.update()


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

    def is_filepath_in_index(self, filepath):
        return filepath in self.files

    def get_file(self, filepath):
        return self.files[filepath]

    def items(self):
        for filepath, file in self.files.items():
            yield filepath, file

    def print_files(self, lpad=''):
        for path, file in self.files.items():
            print(f'{lpad}{path}: {file.get_lm_time()}, '
                  f'{file.get_md5sum()}')

    def jsonify(self):
        return json.dumps({k: v.to_dict() for k, v in self.files.items()})


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

    def read_data(self):
        with open(self.abs_path, 'rb') as f:
            return f.read()

    def update_md5sum(self):
        with open(self.abs_path, mode='rb') as f:
            d = hashlib.md5()
            for buf in iter(partial(f.read, 128), b''):
                d.update(buf)
        self.md5sum = d.hexdigest()

    def to_dict(self):
        return {
            'md5sum': self.get_md5sum(),
            'last_modified': self.get_lm_time()
        }

    def jsonify(self):
        return json.dumps(self.to_dict())


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
            print(f'  [recv] request: {parsed_data}')
            # TODO: validate request
            if 'remote_name' in parsed_data:
                print(f'  Updating FileIndex...')
                self.file_indexes[parsed_data['remote_name']].update()
            else:
                print('  Error: No remote name specified. Abandoning')
                conn.close()
                continue
            if parsed_data['request_type'] == 0:
                # request FileIndex
                remote_name = parsed_data['remote_name']
                response_data = self.file_indexes[remote_name].jsonify()
                print(f'  [send] response: {response_data}')
                conn.sendall(response_data.encode('utf-8'))
            elif parsed_data['request_type'] == 1:
                # request file data
                filepath = parsed_data['filepath']
                file_data = self.file_indexes[remote_name].get_file(filepath).read_data()
                print(f'  [send] reponse: {file_data}')
                conn.sendall(file_data)
            else:
                print('  Error: Unrecognised request type. Abandoning.')
            conn.close()


def get_timestamp():
    return int(round(time.time() * 1000))


def send_desktop_notification(message):
    notification = Notify()
    notification.title = 'pyfilesync'
    notification.message = message
    notification.send()


def graceful_exit(status=0):
    print('Exiting.')
    exit(status)


def load_config(config_path):
    try:
        with open(config_path) as f:
            config = json.load(f)
    except (FileNotFoundError) as e:
        # TODO: use e?
        print(f'Error: Could not load config file `{config_path}\'.')
        graceful_exit(1)

    # set default update interval if not specified
    if 'update_interval' not in config:
        default_update_interval = 15
        print('Warning: Update interval not specified in config, using default value '
              f'{default_update_interval}.')
        config['update_interval'] = default_update_interval

    # ensure config format valid
    # ensure all remotes are named and there are no duplicates
    remote_names = set()
    for remote in config['remotes']:
        if remote['name'] is None or remote['name'] == '':
            print('Error: Unnamed remote found in config.')
            graceful_exit(1)
        elif remote['name'] in remote_names:
            print(f"Error: Duplicate remote name `{remote['name']}' found.")
            graceful_exit(1)
        remote_names.add(remote['name'])

    return config


def main(config_path):
    # 1: load config
    config = load_config(config_path)

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
        remote.update(alias_store, lpad='  ')

    # 5: open thread to listen for update requests
    file_indexes = {}
    for remote in remotes:
        file_indexes[remote.name] = remote.file_index
    print(f"Starting FileServer on port {config['port']}.")
    FileServer(file_indexes, config['port'])

    # 6: start update loop
    while True:
        time.sleep(60 * config['update_interval'])
        for remote in remotes:
            remote.file_index.update()
            remote.update(alias_store, lpad='  ')


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--config', type=str, help='load custom config file')
    args = parser.parse_args()
    config_path = args.config if args.config else 'config.json'
    try:
        main(config_path)
    except KeyboardInterrupt:
        graceful_exit(0)
