#!/bin/bash

# Define input files
Input_File1="$1"
Input_File2="$2"

print_app_status_details() {
    local title="Application Process Details"

    # Print header
    printf "%-40s | %-40s | %-40s | %-20s\n" \
        "----------------------------------------" \
        "----------------------------------------" \
        "----------------------------------------" \
        "--------------------"
    printf "%-40s | %-40s | %-40s | %-20s\n" "$title" "File 1" "File 2" "Status"
    printf "%-40s | %-40s | %-40s | %-20s\n" \
        "----------------------------------------" \
        "----------------------------------------" \
        "----------------------------------------" \
        "--------------------"

    # Read values into arrays
    mapfile -t value1_array < <(awk '
        /^PID/ { found_header=1; next }
        /^-+/ && found_header { 
            if (found) exit;  
            found=1;
            next;
        }
        found { print $6, $7, $8 }
    ' "$Input_File1")

    mapfile -t value2_array < <(awk '
        /^PID/ { found_header=1; next }
        /^-+/ && found_header { 
            if (found) exit;  
            found=1;
            next;
        }
        found { print $6, $7, $8 }
    ' "$Input_File2")

    # Print parsed values from File 1
    echo "---- File 1 Entries ----"
    for entry in "${value1_array[@]}"; do
        read -r field6 field7 field8 <<< "$entry"
        echo "Field 6: $field6, Field 7: $field7, Field 8: $field8"
    done

    # Print parsed values from File 2
    echo "---- File 2 Entries ----"
    for entry in "${value2_array[@]}"; do
        read -r field6 field7 field8 <<< "$entry"
        echo "Field 6: $field6, Field 7: $field7, Field 8: $field8"
    done
}

# Call the function
print_app_status_details


   # # Convert values into arrays for multi-line handling
   # IFS=$'\n' read -d '' -r -a arr1 <<< "$value1"
   # IFS=$'\n' read -d '' -r -a arr2 <<< "$value2"
   #
   # # Combine both arrays for comparison
   # declare -A seen
   # for item in "${arr1[@]}"; do seen["$item"]=1; done
   # for item in "${arr2[@]}"; do seen["$item"]=$(( seen["$item"] + 2 )); done
   #
   # # Print process details with status comparison
   # for key in "${!seen[@]}"; do
   #     case ${seen[$key]} in
   #         1) printf "%-40s | %-40s | %-40s | %-20s\n" "App Process Name" "$key" "Not Found" "Missing After Patching" ;;
   #         2) printf "%-40s | %-40s | %-40s | %-20s\n" "App Process Name" "Not Found" "$key" "Missing Before Patching" ;;
   #         3) printf "%-40s | %-40s | %-40s | %-20s\n" "App Process Name" "$key" "$key" "Validated" ;;
   #     esac
   # done
	
	# Extract app process count from both files
#   local app_count1=$(awk '/Total number of App java process available is/ {print $NF}' "$Input_File1" | xargs)
#   #local app_count2=$(awk '/Total number of App java process available is/ {print $NF}' "$Input_File2" | xargs)
#
#    # Handle missing values
#    [[ -z "$app_count1" ]] && app_count1="Not Found"
#    [[ -z "$app_count2" ]] && app_count2="Not Found"
#	
#	
#	if [[ "$app_count1" == "$app_count2" ]]; then
#		status="Validated"
#	else	
#		status="Need Attention"
#	fi	
#
#    # Print app process count
#    printf "%-40s | %-40s | %-40s | %-20s\n" "App Processes Running" "$app_count1" "$app_count2" "$status"
#	printf "%-40s | %-40s | %-40s | %-20s\n" "----------------------------------------" "----------------------------------------" "----------------------------------------" #"--------------------"
}