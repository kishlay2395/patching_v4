#!/bin/bash

# Script to compare services with status details (including failed services) before and after server restart
echo "========================================"
echo "Comparing services with status details before and after restart..."
echo "========================================"

# Define filenames for storing service lists
BEFORE_FILE="services_before_restart.txt"
AFTER_FILE="services_after_restart.txt"
FAILED_LOG="failed_services.log"

# Function to generate a detailed list of services
generate_service_list() {
    local output_file=$1

    # Clear the output file
    > "$output_file"

    # Get all services with their status details
    echo "Generating detailed service list..."
    systemctl list-unit-files --type=service --no-pager | awk '{print $1, $2}' > "$output_file"

    # Add active/inactive status for each service
    while read -r service status; do
        if [[ $service == "UNIT" || $service == "" ]]; then
            continue  # Skip header or empty lines
        fi
        active_status=$(systemctl is-active "$service" 2>/dev/null)
        echo "$service $status ($active_status)" >> "$output_file"

        # Check for failed services
        if [[ $active_status == "failed" ]]; then
            echo "WARNING: Service $service is in a FAILED state!" >> "$FAILED_LOG"
        fi
    done < "$output_file"

    echo "Service list saved to $output_file."
}

# Step 1: Generate a list of services before restart
rm -f "$FAILED_LOG"  # Clear the failed services log
generate_service_list "$BEFORE_FILE"

# Step 2: Generate a list of services after restart
generate_service_list "$AFTER_FILE"

# Step 3: Compare the two lists
echo "Comparing services before and after restart..."
diff_output=$(diff "$BEFORE_FILE" "$AFTER_FILE")

if [[ -z "$diff_output" ]]; then
    echo "No changes detected in services."
else
    echo "Changes detected in services:"
    echo "$diff_output"
fi

# Step 4: Report failed services
if [[ -s "$FAILED_LOG" ]]; then
    echo ""
    echo "Failed services detected. Details logged in $FAILED_LOG:"
    cat "$FAILED_LOG"
else
    echo "No failed services detected."
fi

echo ""
echo "Comparison completed."
echo "========================================"