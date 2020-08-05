pyfilesync

What it is:
- Sync selected library directories between computers (e.g. books, music, config files) peer-to-peer

What it isn't:
- A VCS. No backup or change tracking facilities built in.

Setup:
- Setup virtualenv, e.g.:
  * virtualenv -p python3 venv && source venv/bin/activate
  * pip install -r requirements.txt
- For existing remote dir
  * Specify non-existent target directory, will pull config into .{$name} folder and files
- For new local dir:
  * Specify target directory, will build per-dir config folder
  * Then follow above remote step for other PCs
