import os
import socket
import json
import hashlib
from functools import partial
from threading import Thread


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
