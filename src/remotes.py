import os
import tempfile

from utils import get_timestamp, send_desktop_notification
from files import FileIndex


class Remote():
    def __init__(self, local_path, peers, name):
        self.name = name
        self.peer_aliases = peers
        self.path = local_path
        self.dir_name = os.path.basename(local_path)
        self.file_index = FileIndex(local_path)

    def update(self, alias_store, lpad=''):
        # 1: connect to remote hosts, request json-ified FileIndex objects
        print(f'{lpad}Local FileIndex representation: {self.file_index.jsonify()}')
        file_indexes = {}
        for alias in self.peer_aliases:
            peer = alias_store.get_peer(alias)
            try:
                peer_file_index = peer.recv_file_index(self.name, lpad=lpad)
                if peer_file_index is not None:
                    file_indexes[alias] = peer_file_index
            except (ConnectionRefusedError) as e:
                # TODO: use e?
                print(f'{lpad}Warning: Connection refused by peer `{peer.name}\' for '
                      f'remote `{self.name}\' at {peer.ip_address}:{peer.port}. Peer may '
                      'be offline.')
        if len(file_indexes) == 0:
            print(f'{lpad}No peers available for update.')
            return
        # 2: compute changes between dicts based on md5 hashes
        # iterate, combine into one dict with latest lm and peer
        latest_changes = {}
        for alias, file_index in file_indexes.items():
            for filepath, details in file_index.items():
                # TODO: check filepath is not exploitative
                # os.dir.join(self.path, filepath) is subdir of self.path
                if (filepath not in latest_changes or latest_changes[filepath][
                        'last_modified'] < details['last_modified']):
                    latest_changes[filepath] = {
                        'md5sum': details['md5sum'],
                        'last_modified': details['last_modified'],
                        'peer_alias': alias
                    }
            # all_filepaths = all_filepaths.union(set(file_index.keys()))
        print(f'{lpad}Latest changes from peers: {latest_changes}')
        # get all filepaths
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
        for filepath in changed_files:
            # TODO: makedirs for files that are in a subdir
            target_peer = alias_store.get_peer(latest_changes[filepath]['peer_alias'])
            file_data = target_peer.recv_file_data(self.name, filepath, lpad=lpad)
            temp_path = os.path.join(temp_dir, filepath)
            with open(temp_path, 'wb') as f:
                f.write(file_data)
            print(f'{lpad}Wrote updated file `{filepath}\' to {temp_path} '
                  f'({len(file_data)} bytes).')
        # 4: move old files to temp backup folder, move new files to folder
        for filepath in changed_files:
            # move old if exists
            target_path = os.path.join(self.path, filepath)
            if os.path.exists(target_path):
                os.rename(target_path, os.path.join(backup_dir, filepath))
            # move new
            os.rename(os.path.join(temp_dir, filepath), target_path)
            print(f'{lpad}Updated file `{filepath}.\'')
            update_message = f"{self.name}: Updated file {filepath} from peer " \
                             f"{latest_changes[filepath]['peer_alias']}"
            send_desktop_notification(update_message)
        # 5: update FileIndex
        self.file_index.update()
