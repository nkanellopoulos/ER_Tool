#!/bin/bash
set -eux

export ER_DB_CONNECTION="postgresql://asdf:asdf@localhost:2345/crdb"
export TABLE_PREFIX=""
python ER_Tool.py
