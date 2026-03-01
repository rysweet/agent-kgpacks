#!/bin/bash
cd /tmp/amplihack-workstreams/ws-237
unset CLAUDECODE  # Allow nested Claude sessions
# Propagate session tree context so child recipes obey depth limits
export AMPLIHACK_TREE_ID=470fa9d9
export AMPLIHACK_SESSION_DEPTH=1
export AMPLIHACK_MAX_DEPTH=3
export AMPLIHACK_MAX_SESSIONS=10
exec python3 launcher.py
