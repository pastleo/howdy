#!/bin/bash

DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" >/dev/null 2>&1 && pwd )"
STATUS_FILE_PATH="/tmp/howdy-compare-$2"

/usr/bin/python3 "$DIR/compare.py" $1
echo $? > $STATUS_FILE_PATH
sh -c "sleep 5 && rm $STATUS_FILE_PATH" &
