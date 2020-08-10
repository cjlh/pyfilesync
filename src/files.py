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
        self.lm_time = None

    def update_lm_time(self):
        self.lm_time = os.path.getmtime(self.abs_path)

    def update_md5sum(self):
        with open(self.abs_path, mode='rb') as f:
            d = hashlib.md5()
            for buf in iter(partial(f.read, 128), b''):
                d.update(buf)
        self.md5sum = d.hexdigest()

    def get_lm_time(self):
        if self.lm_time is None:
            self.update_lm_time()
            return self.lm_time
        else:
            return self.lm_time

    def get_md5sum(self):
        if self.md5sum is None:
            self.update_md5sum()
            return self.md5sum
        else:
            return self.md5sum

    def read_data(self):
        with open(self.abs_path, 'rb') as f:
            return f.read()

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
        # TODO: think about an operation queue like this
        self.op_queue = []
        self.build()

    def build(self):
        for path, _, filenames in os.walk(self.root_dir):
            for filename in filenames:
                filepath = os.path.join(path,
                                        filename)[len(self.root_dir) + 1:]
                self.files[filepath] = File(self.root_dir, filepath)

    def update(self):
        for path, _, filenames in os.walk(self.root_dir):
            for filename in filenames:
                filepath = os.path.join(path,
                                        filename)[len(self.root_dir) + 1:]
                if filepath in self.files:
                    if (os.path.getmtime(os.path.join(self.root_dir, filepath)) >
                            self.files[filepath].get_lm_time()):
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
            # We know requests will be <1024
            data = conn.recv(1024).decode('utf-8')
            try:
                parsed_data = json.loads(data)
            except json.decoder.JSONDecodeError:
                print('  Error: Request could not be parsed as JSON. Abandoning.')
                conn.close()
                continue
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
                response_data = self.file_indexes[remote_name].jsonify().encode('utf-8')
                response_size_data = f'{{"response_size": {len(response_data)}}}'.encode(
                    'utf-8')
                print(f'  [send] response size: {response_size_data}')
                conn.sendall(response_size_data)
                print(f'  [send] response: {response_data}')
                conn.sendall(response_data)
            elif parsed_data['request_type'] == 1:
                # request file data
                filepath = parsed_data['filepath']
                file_data = self.file_indexes[remote_name].get_file(filepath).read_data()
                response_size_data = f'{{"response_size": {len(file_data)}}}'.encode(
                    'utf-8')
                print(f'  [send] response size: {response_size_data}')
                conn.sendall(response_size_data)
                print(f'  [send] reponse: {file_data}')
                conn.sendall(file_data)
            else:
                print('  Error: Unrecognised request type. Abandoning.')
            conn.close()
