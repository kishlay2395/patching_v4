#!/bin/bash

Input_File1="$1"
Input_File2="$2"

print_app_status_details() {
    local title="Application Process Details"

    # Header
    printf "\n%-40s | %-20s | %-20s | %-20s | %-20s | %-20s\n" \
        "URL Address" "Pre-Check-Status" "Post-Check-Status" "StatusCmp" "Pre_Http_Code" "Post_Http_Code"
    printf "%-40s | %-20s | %-20s | %-20s | %-20s | %-20s\n" \
        "----------------------------------------" "--------------------" "--------------------" "--------------------" "--------------------" "--------------------"

    declare -A file1_status file2_status file1_code file2_code

    # Parse Input_File1 (Pre-check)
    while read -r url status code; do
        file1_status["$url"]="$status"
        file1_code["$url"]="$code"
    done < <(awk '
        /^PID/ { found_header=1; next }
        /^-+/ && found_header { if (found) exit; found=1; next }
        found { print $6, $7, $8 }
    ' "$Input_File1")

    # Parse Input_File2 (Post-check)
    while read -r url status code; do
        file2_status["$url"]="$status"
        file2_code["$url"]="$code"
    done < <(awk '
        /^PID/ { found_header=1; next }
        /^-+/ && found_header { if (found) exit; found=1; next }
        found { print $6, $7, $8 }
    ' "$Input_File2")

    # Compare and display results
    for url in "${!file1_status[@]}"; do
        status1="${file1_status[$url]}"
        status2="${file2_status[$url]}"
        code1="${file1_code[$url]}"
        code2="${file2_code[$url]}"

        status_cmp="MATCH"
        [[ "$status1" != "$status2" ]] && status_cmp="MISMATCH"

        printf "%-40s | %-20s | %-20s | %-20s | %-20s | %-20s\n" \
            "$url" "$status1" "$status2" "$status_cmp" "$code1" "$code2"
    done
}

print_app_status_details
