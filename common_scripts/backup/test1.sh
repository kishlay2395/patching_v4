

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
        /^PID/ { found_header=1; next }
        /^-+/ && found_header { 
            if (found) exit;  
            found=1;
            next;
        }
        found { print $6}
    ' "$Input_File1")

    local App_URL_value2=$(awk '
        /^PID/ { found_header=1; next }
        /^-+/ && found_header { 
            if (found) exit;  
            found=1;
            next;
        }
        found { print $6}
    ' "$Input_File2")
	
	local App_URL_Status_value1=$(awk '
        /^PID/ { found_header=1; next }
        /^-+/ && found_header { 
            if (found) exit;  
            found=1;
            next;
        }
        found { print $7}
    ' "$Input_File1")

    local App_URL_Status_value2=$(awk '
        /^PID/ { found_header=1; next }
        /^-+/ && found_header { 
            if (found) exit;  
            found=1;
            next;
        }
        found { print $7}
    ' "$Input_File2")
	
	local App_URL_Status_Code_value1=$(awk '
        /^PID/ { found_header=1; next }
        /^-+/ && found_header { 
            if (found) exit;  
            found=1;
            next;
        }
        found { print $8}
    ' "$Input_File1")

    local App_URL_Status_Code_value2=$(awk '
        /^PID/ { found_header=1; next }
        /^-+/ && found_header { 
            if (found) exit;  
            found=1;
            next;
        }
        found { print $8}
    ' "$Input_File2")
	
	

    #IFS=$'\n' read -d '' -r -a arr1 <<< "$App_URL_value1" "$App_URL_Status_value1" "$App_URL_Status_Code_value1"
    #IFS=$'\n' read -d '' -r -a arr2 <<< "$App_URL_value2" "$App_URL_Status_value2" "$App_URL_Status_Code_value2"
	
	IFS=$'\n' read -d '' -r -a arr_ep1 <<< "$(echo -e "$App_URL_value1\t$App_URL_Status_value1\t$App_URL_Status_Code_value1")"
	IFS=$'\n' read -d '' -r -a arr_ep2 <<< "$(echo -e "$App_URL_value2\t$App_URL_Status_value2\t$App_URL_Status_Code_value2")"

	
	for item1 in "${arr_ep1[@]}"; 
	do
		echo $item1;
	done
	
	for item2 in "${arr_ep2[@]}"; 
	do
		echo $item2;
	done
	
	#declare -A seen
    #for item in "${arr1[@]}"; do seen["$item"]=1; done
    #for item in "${arr2[@]}"; do seen["$item"]=$(( seen["$item"] + 2 )); done
	##for item1 in "${seen[@]}"; 
	##do
	##	echo $item1;
	##done
	#
    #    for line in "${arr_ep1[@]}"; do
    #    key=$(echo "$line" | awk '{print $1}')
    #    value=$(echo "$line" | awk '{print $2 " " $3}')
    #    endpoint_map1["$key"]="$value"
	#	echo $key $value $endpoint 
    #done
	#
    #for line in "${arr_ep2[@]}"; do
    #    key=$(echo "$line" | awk '{print $1}')
    #    value=$(echo "$line" | awk '{print $2 " " $3}')
    #    endpoint_map2["$key"]="$value"
	#	echo $key $value $endpoint 
    #done
}

print_app_status_details