#!/bin/bash
set -eux

export DB_CONNECTION="postgresql://asdf:asdf@localhost:2345/crdb"
python er_gui.py
