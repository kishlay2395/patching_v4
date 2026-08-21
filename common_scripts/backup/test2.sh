#!/bin/bash

# Define input files
Input_File1="$1"
Input_File2="$2"

print_app_status_details() {
    local title="Application Process Details"

    # Print header
    printf "%-40s | %-40s | %-40s | %-20s\n" "----------------------------------------" "----------------------------------------" "----------------------------------------" "--------------------"
    printf "%-40s | %-40s | %-40s | %-20s\n" "$title" "File 1" "File 2" "Status"
    printf "%-40s | %-40s | %-40s | %-20s\n" "----------------------------------------" "----------------------------------------" "----------------------------------------" "--------------------"

    local App_URL_value1=$(awk '
        /PID       AppName      JbossVersion  Java-Name/ { found_header=1; next }
        /^-+/ && found_header { 
            if (found) exit;  
            found=1;
            next;
        }
        found { print $6}
    ' "$Input_File1")

    local App_URL_value2=$(awk '
        /PID       AppName      JbossVersion  Java-Name/ { found_header=1; next }
        /^-+/ && found_header { 
            if (found) exit;  
            found=1;
            next;
        }
        found { print $6}
    ' "$Input_File2")
	
	local App_URL_Status_value1=$(awk '
        /PID       AppName      JbossVersion  Java-Name/ { found_header=1; next }
        /^-+/ && found_header { 
            if (found) exit;  
            found=1;
            next;
        }
        found { print $7}
    ' "$Input_File1")

    local App_URL_Status_value2=$(awk '
        /PID       AppName      JbossVersion  Java-Name/ { found_header=1; next }
        /^-+/ && found_header { 
            if (found) exit;  
            found=1;
            next;
        }
        found { print $7}
    ' "$Input_File2")
	
	local App_URL_Status_Code_value1=$(awk '
        /PID       AppName      JbossVersion  Java-Name/ { found_header=1; next }
        /^-+/ && found_header { 
            if (found) exit;  
            found=1;
            next;
        }
        found { print $8}
    ' "$Input_File1")

    local App_URL_Status_Code_value2=$(awk '
        /PID       AppName      JbossVersion  Java-Name/ { found_header=1; next }
        /^-+/ && found_header { 
            if (found) exit;  
            found=1;
            next;
        }
        found { print $8}
    ' "$Input_File2")
	
	

    IFS=$'\n' read -d '' -r -a arr1 <<< "$App_URL_value1" "$App_URL_Status_value1" "$App_URL_Status_Code_value1"
    IFS=$'\n' read -d '' -r -a arr2 <<< "$App_URL_value2" "$App_URL_Status_value2" "$App_URL_Status_Code_value2"

    declare -A seen
    for item in "${arr1[@]}"; do seen["$item"]=1; done
    for item in "${arr2[@]}"; do seen["$item"]=$(( seen["$item"] + 2 )); done

    for key in "${!seen[@]}"; do
        case ${seen[$key]} in
            1) printf "%-40s | %-40s | %-40s | %-20s\n" "App Process Name" "$key" "Not Found" "Missing After Patching" ;;
            2) printf "%-40s | %-40s | %-40s | %-20s\n" "App Process Name" "Not Found" "$key" "Missing Before Patching" ;;
            3) printf "%-40s | %-40s | %-40s | %-20s\n" "App Process Name" "$key" "$key" "Validated" ;;
        esac
    done

    local app_count1=$(awk '/Total number of App java process available is/ {print $NF}' "$Input_File1" | xargs)
    local app_count2=$(awk '/Total number of App java process available is/ {print $NF}' "$Input_File2" | xargs)

    [[ -z "$app_count1" ]] && app_count1="Not Found"
    [[ -z "$app_count2" ]] && app_count2="Not Found"

    if [[ "$app_count1" == "$app_count2" ]]; then
        status="Validated"
    else
        status="Need Attention"
    fi

    printf "%-40s | %-40s | %-40s | %-20s\n" "App Processes Running" "$app_count1" "$app_count2" "$status"
    printf "%-40s | %-40s | %-40s | %-20s\n" "----------------------------------------" "----------------------------------------" "----------------------------------------" "--------------------"

    #### NEW SECTION: Endpoint Health Check Comparison ####

    local endpoints1=$(grep -Eo '[0-9]+\.[0-9]+\.[0-9]+\.[0-9]+:[0-9]+ [A-Z]+ [0-9]+' "$Input_File1")
    local endpoints2=$(grep -Eo '[0-9]+\.[0-9]+\.[0-9]+\.[0-9]+:[0-9]+ [A-Z]+ [0-9]+' "$Input_File2")

    IFS=$'\n' read -d '' -r -a arr_ep1 <<< "$endpoints1"
    IFS=$'\n' read -d '' -r -a arr_ep2 <<< "$endpoints2"

    declare -A endpoint_map1
    declare -A endpoint_map2

    for line in "${arr_ep1[@]}"; do
        key=$(echo "$line" | awk '{print $1}')
        value=$(echo "$line" | awk '{print $2 " " $3}')
        endpoint_map1["$key"]="$value"
    done

    for line in "${arr_ep2[@]}"; do
        key=$(echo "$line" | awk '{print $1}')
        value=$(echo "$line" | awk '{print $2 " " $3}')
        endpoint_map2["$key"]="$value"
    done

    # Collect all unique keys
    all_keys=("${!endpoint_map1[@]}" "${!endpoint_map2[@]}")
    unique_keys=($(printf "%s\n" "${all_keys[@]}" | sort -u))

    # Print comparison
    for key in "${unique_keys[@]}"; do
        val1=${endpoint_map1[$key]:-"Not Found"}
        val2=${endpoint_map2[$key]:-"Not Found"}

        if [[ "$val1" == "$val2" ]]; then
            ep_status="Validated"
        else
            ep_status="Need Attention"
        fi

        printf "%-40s | %-40s | %-40s | %-20s\n" "Endpoint $key" "$val1" "$val2" "$ep_status"
    done

    printf "%-40s | %-40s | %-40s | %-20s\n" "----------------------------------------" "----------------------------------------" "----------------------------------------" "--------------------"
}



print_app_status_details