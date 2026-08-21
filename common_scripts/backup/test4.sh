#!/bin/bash

Input_File1="$1"
Input_File2="$2"

print_app_status_details() {
    local title="Application Process Details"

    # Header
	printf "\n%-40s | %-20s | %-20s | %-20s | %-20s | %-20s\n" \
    "URL Address" "Pre-Check-Status" "Post-Check-Status" "StatusCmp" "Pre_Http_Code" "Post_Http_Code"

	# Print a separator line
	printf "%-40s | %-20s | %-20s | %-20s | %-20s | %-20s\n" \
    "----------------------------------------" "--------------------" "--------------------" "--------------------" "--------------------" "--------------------"

    # Declare associative arrays
    declare -A file1_status file2_status file1_code file2_code

    # Parse File 1
    awk '
        /^PID/ { found_header=1; next }
        /^-+/ && found_header { 
            if (found) exit;  
            found=1;
            next;
        }
        found { print $6, $7, $8}
    ' "$Input_File2" | while read -r field6 field7 field8; 
	do
        file1_status["$field6"]="$field7"
        file1_code["$field6"]="$field8"
    done

    # Parse File 2
	awk '
        /^PID/ { found_header=1; next }
        /^-+/ && found_header { 
            if (found) exit;  
            found=1;
            next;
        }
        found { print $6, $7, $8}
    ' "$Input_File2" | while read -r field6 field7 field8; 
	do
        file1_status["$field6"]="$field7"
        file1_code["$field6"]="$field8"
    done


    # Compare and display results
    for key in "${!file1_status[@]}"; do
        status1="${file1_status[$key]}"
        status2="${file2_status[$key]}"
        code1="${file1_code[$key]}"
        code2="${file2_code[$key]}"

        status_cmp="MATCH"
        [[ "$status1" != "$status2" ]] && status_cmp="MISMATCH"

        code_cmp="match"
        [[ "$code1" != "$code2" ]] && code_cmp="mismatch"

        printf "%-40s | %-20s | %-20s | %-20s | %-20s | %-20s\n" \
            "$key" "$status1" "$status2" "$status_cmp" "$code1" "$code2"
    done
}

print_app_status_details
