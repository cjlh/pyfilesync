#!/bin/bash
set -e
trap "kill 0" EXIT

# Note: Run in new terminal with bash with no env sourced
# TODO: rewrite in Python?

script_dir=`dirname "$BASH_SOURCE"`
cd $script_dir

# setup
if [ -d "test_data" ]; then rm -r "test_data"; fi
mkdir test_data
mkdir test_data/server_1
mkdir test_data/server_2

# create files for testing
# server 1
echo 'abcdefghijklmnopqrstuvwxyz' > test_data/server_1/alphabet.txt
echo 'this_will_be_overwritten' > test_data/server_1/a_file
# server 2
# mkdir test_data/server_2/notes
# echo 'foo' > test_data/server_2/notes/1.txt
# echo 'bar' > test_data/server_2/notes/2.txt
# echo 'baz' > test_data/server_2/notes/3.txt
# echo 'qux' >> test_data/server_2/notes/3.txt
# echo 'newer_note' > test_data/server_2/a_file
# print contents
echo 'test dir contents:'
echo 'server 1:'
tree test_data/server_1
echo 'server 2:'
tree test_data/server_2

# build config files
sed 's?${path}?'`pwd`'/test_data/server_1?' config_1.template.json > test_data/config_1.json
sed 's?${path}?'`pwd`'/test_data/server_2?' config_2.template.json > test_data/config_2.json

# start servers
source ../venv/bin/activate
python3 ../src/main.py --config test_data/config_1.json &
proc_1=$!
sleep 2
python3 ../src/main.py --config test_data/config_2.json &
proc_2=$!

# sleep to accommodate transfer then kill
sleep 2
kill $proc_1
kill $proc_2
sleep 1
echo ''

# compare contents
if [[ $(diff -r test_data/server_1 test_data/server_2) ]]; then
    echo "TESTS FAILED: Directory contents differ."
else
    echo "TESTS PASSED!"
fi

wait
