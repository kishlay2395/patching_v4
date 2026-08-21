#!/bin/bash

MyDateTime="$(date -u +"%Y-%m-%d-%H-%M-%S-%3N")"

# Script to compare services before and after patching
ACTION=$1
ServerIP=$2
ServerUsername=$3
ServerPassword=$4

# Define filenames for storing service lists
BEFORE_FILE="services_before_patching_${MyDateTime}.txt"
AFTER_FILE="services_after_patching_${MyDateTime}.txt"
FAILED_LOG="failed_services.log"

# Function to generate a detailed list of services
generate_service_list() {
    local output_file="$1"
    local temp_file
    temp_file=$(mktemp)

    # Optionally define a failed services log
    : "${FAILED_LOG:=/tmp/failed_services.log}"
    > "$FAILED_LOG"

    echo "Generating detailed service list on $ServerIP..."

    sshpass -p "$ServerPassword" ssh -o StrictHostKeyChecking=no "$ServerUsername@$ServerIP" "
        systemctl list-unit-files --type=service --no-pager |
        tail -n +2 |
        awk '{\$1=\$1; print \$1, substr(\$0, length(\$1)+2)}' |
        while read -r service_name state; do
            active_status=\$(systemctl is-active \$service_name 2>/dev/null)
            echo \"\$service_name \$state (\$active_status)\"
            if [[ \$active_status == 'failed' ]]; then
                echo \"\$service_name is in a FAILED state!\" >&2
            fi
        done
    " > "$temp_file" 2> "$FAILED_LOG"

    mv "$temp_file" "$output_file"
    echo "Service list saved to $output_file."
    [[ -s "$FAILED_LOG" ]] && echo "Warnings saved to $FAILED_LOG."
}

# Main logic based on action
if [[ "$ACTION" == "before" ]]; then
    rm -f "$FAILED_LOG"  # Clear the failed services log
    generate_service_list "$BEFORE_FILE"
elif [[ "$ACTION" == "after" ]]; then
    generate_service_list "$AFTER_FILE"

    # Compare the two lists
    echo "Comparing services before and after patching..."
    diff_output=$(diff "$BEFORE_FILE" "$AFTER_FILE")

    if [[ -z "$diff_output" ]]; then
        echo "No changes detected in services."
    else
        echo "Changes detected in services:"
        echo "$diff_output"
    fi

    # Report failed services
    if [[ -s "$FAILED_LOG" ]]; then
        echo ""
        echo "Failed services detected. Details logged in $FAILED_LOG:"
        cat "$FAILED_LOG"
    else
        echo "No failed services detected."
    fi
else
    echo "Invalid action. Use 'before' or 'after'."
    exit 1
fi