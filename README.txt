pyfilesync

Status:
- DO NOT USE. Will only sync top-level files.

What it is:
- Sync selected library directories between computers (e.g. books, music, config files) peer-to-peer.

What it isn't:
- A VCS. No versioning facilities built in.
  * Note old files are moved to temp directory on update.

Setup:
- Setup virtualenv, e.g.:
  * virtualenv -p python3 venv && source venv/bin/activate
  * pip install -r requirements.txt
- To pull new dir from peers:
  * Specify non-existent or empty target directory, will pull from peers
- To copy new dir to peers:
  * Specify local dir as target directory
  * Follow remote step for other PCs
