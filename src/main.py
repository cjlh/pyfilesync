import os
import argparse
import json
import time

from utils import graceful_exit
from peers import AliasStore
from files import FileServer
from remotes import Remote


def load_config(config_path):
    try:
        with open(config_path) as f:
            config = json.load(f)
    except (FileNotFoundError) as e:
        # TODO: use e?
        print(f'Error: Could not load config file `{config_path}\'.')
        graceful_exit(1)

    defaults = {
        'update_interval': 15,
        'port': 6688
    }

    # set default update interval if not specified
    if 'update_interval' not in config:
        print("Warning: Update interval not specified in config, using default value "
              f"{defaults['update_interval']}.")
        config['update_interval'] = defaults['update_interval']

    # set default port if not specified
    if 'port' not in config:
        print("Warning: Port not specified in config, using default value "
              f"{defaults['port']}.")
        config['port'] = defaults['port']

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
        print(f'Checking for updates on {remote.name}...')
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
