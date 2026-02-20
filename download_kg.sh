#!/bin/bash
# Download WikiGR Knowledge Graph database using azlin
#
# This downloads the 3GB knowledge graph database from the Azure VM to your local machine.
#
# Prerequisites:
# - azlin installed (gh extension install rysweet/azlin)
# - Authenticated to Azure

VM_NAME="seldon-dev"
RESOURCE_GROUP="your-resource-group"  # Update this
REMOTE_PATH="/home/azureuser/src/wikigr/backups/wikigr_30k_final.db"
LOCAL_PATH="./wikigr_30k.db"

echo "Downloading 3GB knowledge graph database..."
echo "This may take 5-10 minutes depending on your connection."

azlin cp "${VM_NAME}:${REMOTE_PATH}" "${LOCAL_PATH}"

echo ""
echo "Download complete: ${LOCAL_PATH}"
echo "Database contains:"
echo "  - 31,777 articles"
echo "  - 87,500 entities"
echo "  - 54,393 semantic relationships"
echo "  - 105,388 facts"
echo "  - 6.2M article links"
