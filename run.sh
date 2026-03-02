#!/bin/bash
cd /tmp/amplihack-workstreams/ws-258
unset CLAUDECODE  # Allow nested Claude sessions
# Propagate session tree context so child recipes obey depth limits
export AMPLIHACK_TREE_ID=d80de4bf
export AMPLIHACK_SESSION_DEPTH=1
export AMPLIHACK_MAX_DEPTH=3
export AMPLIHACK_MAX_SESSIONS=10
exec python3 launcher.py
