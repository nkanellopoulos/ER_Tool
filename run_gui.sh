#!/bin/bash
set -eux

export DB_CONNECTION="postgresql://asdf:asdf@localhost:2345/crdb"
export TABLE_PREFIX="CyberRange_RESTAPI_"
python ER_Tool.py
