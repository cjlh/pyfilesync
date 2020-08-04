pyfilesync

What it is
- Sync selected library directories between computers (e.g. books, music, config files) peer-to-peer

What it is not
- A VCS. No backup or change tracking facilities built in.

Setup:
- For existing remote dir
  * Specify non-existent target directory, will pull config into .{$name} folder and files
- For new local dir:
  * Specify target directory, will build per-dir config folder
  * Then follow above remote step for other PCs

Global config structure
- Aliases for remote machines

Per-dir config structure
- ?

- JSON config
- Remote names are required

- Maybe implement permissions?
  * Ability to add a folder from any of the clients, and designate write access to all/many/none
