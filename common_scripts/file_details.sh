#!/bin/bash

IMPL_NAME=$1
MYAPP_PATH=$(pwd)  # Get current working directory
MYAPP_PATH_OUTPATH="$(realpath "${MYAPP_PATH}/../output")"  # Convert to absolute path
MYDATE="$(date -u +"%Y-%m-%d")"
MYDATETIME="$(date -u +%Y-%m-%d-%H-%M-%S)"
OUTPUT_DIR="${MYAPP_PATH_OUTPATH}/${IMPL_NAME}"

# Ensure directory exists
if [ ! -d "$OUTPUT_DIR" ]; then
    echo "Error: OUTPUT_DIR $OUTPUT_DIR does not exist!"
    exit 1
fi

# Get list of files
files=$(find "$OUTPUT_DIR" -type f -printf "%f\n")

# Extract unique IP addresses
IP_ADDRESSES=$(echo "$files" | awk -F'-' '{print $1}' | sort -u)

echo "Checking for latest files for each IP address..."
echo "-----------------------------------------------"

# Loop through each unique IP
for IP in $IP_ADDRESSES; do
    # Find latest matching files
    LATEST_FILE_AFTER_PATCH=$(echo "$files" | grep "^${IP}-.*AfterPatching" | sort -t'-' -k3,4 -r | head -n 1)
    LATEST_FILE_BEFORE_PATCH=$(echo "$files" | grep "^${IP}-.*BeforePatching" | sort -t'-' -k3,4 -r | head -n 1)

    # Validation
    if [ -z "$LATEST_FILE_AFTER_PATCH" ]; then
        echo "No AfterPatching file found for IP $IP"
        continue
    fi

    if [ -z "$LATEST_FILE_BEFORE_PATCH" ]; then
        echo " No BeforePatching file found for IP $IP"
        continue
    fi

    # Output matched files
    echo "IP $IP:"
    echo " Latest AfterPatching:  $LATEST_FILE_AFTER_PATCH"
    echo " Latest BeforePatching: $LATEST_FILE_BEFORE_PATCH"
    echo "-----------------------------------------------"

    # Call comparison script
    bash "$MYAPP_PATH/final_output.sh" \
        "${OUTPUT_DIR}/${LATEST_FILE_BEFORE_PATCH}" \
        "${OUTPUT_DIR}/${LATEST_FILE_AFTER_PATCH}"
done
