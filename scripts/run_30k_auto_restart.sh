#!/bin/bash
#
# Auto-restarting wrapper for 30K LLM expansion.
# Restarts the process if it exits before reaching 30K articles.
#

TARGET=30000
DB_PATH="data/wikigr_30k.db"
LOG="logs/expansion_30k_auto.log"

while true; do
    # Check current progress
    PROCESSED=$(python3.10 -c "
import kuzu
db = kuzu.Database('$DB_PATH')
conn = kuzu.Connection(db)
conn.execute(\"MATCH (a:Article) WHERE a.expansion_state = 'claimed' SET a.expansion_state = 'discovered', a.claimed_at = NULL\")
r = conn.execute('MATCH (a:Article) WHERE a.expansion_state = \"processed\" RETURN COUNT(a) AS c')
print(int(r.get_as_df().iloc[0]['c']))
" 2>&1)

    if [ "$PROCESSED" -ge "$TARGET" ]; then
        echo "$(date): Target reached: $PROCESSED articles"
        exit 0
    fi

    echo "$(date): Progress $PROCESSED/$TARGET. Starting expansion..." >> $LOG

    # Run expansion (single-threaded, proven reliable)
    python3.10 scripts/run_30k_llm.py >> $LOG 2>&1
    EXIT_CODE=$?

    echo "$(date): Process exited with code $EXIT_CODE. Processed: $PROCESSED" >> $LOG

    # Wait a bit before restart
    sleep 10
done
