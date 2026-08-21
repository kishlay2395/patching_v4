#!/bin/bash

# Script to check CUPS-related details
echo "========================================"
echo "Checking CUPS configuration and status..."
echo "========================================"

# Function to check if a service is installed and running
check_service_status() {
    local service_name=$1
    if systemctl list-unit-files | grep -qw "$service_name"; then
        echo "The $service_name service is installed."
        if systemctl is-active --quiet "$service_name"; then
            echo "The $service_name service is running."
        else
            echo "The $service_name service is not running."
            echo "You can start it using: sudo systemctl start $service_name"
        fi
    else
        echo "The $service_name service is not installed."
    fi
}

# Check if CUPS service is installed and running
echo "Checking CUPS Server service..."
check_service_status "cups"
echo -e "-------------------------\n"

# Define the CUPS URL (update this with your actual CUPS server URL)
CUPS_URL=${1:-"http://localhost:631"}
CUPS_PRINTERS_URL=${2:-"${CUPS_URL}/printers/"}

# Function to check the status of the URL
check_cups_status() {
    local URL="$1"
    # Use curl to send a HEAD request and capture the HTTP status code
    HTTP_STATUS=$(curl -o /dev/null -s -w "%{http_code}" "$URL" 2>/dev/null)

    # Check if curl failed
    if [[ $? -ne 0 ]]; then
        echo "Failed to connect to $URL. Please check your network or server configuration."
        return
    fi

    # Check the HTTP status code and display the result
    case $HTTP_STATUS in
        200)
            echo "CUPS server is running and accessible at $URL. Status Code: $HTTP_STATUS"
            ;;
        401)
            echo "CUPS server is running but requires authentication at $URL. Status Code: $HTTP_STATUS"
            ;;
        404)
            echo "CUPS server is running but the requested resource was not found at $URL. Status Code: $HTTP_STATUS"
            ;;
        503)
            echo "CUPS server is unavailable at $URL. Status Code: $HTTP_STATUS"
            ;;
        *)
            echo "Unable to connect to the CUPS server at $URL. Status Code: $HTTP_STATUS"
            ;;
    esac
}

# Main script execution
echo "Checking the status of the CUPS server at $CUPS_URL..."
check_cups_status "${CUPS_URL}"
check_cups_status "${CUPS_PRINTERS_URL}"

# Summary
echo ""
echo "CUPS status check completed."
echo "========================================"