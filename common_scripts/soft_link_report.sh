echo "========================================"
echo "Searching for symbolic links in the root directory (/):"
echo "========================================"


# Use temporary files to store links
ALL_LINKS_FILE=$(mktemp)
VALID_LINKS_FILE=$(mktemp)
INVALID_LINKS_FILE=$(mktemp)

# Find all symbolic links and save to temporary file
#printf "%-40s %-50s\n" "Link Name" "Target" > "$ALL_LINKS_FILE"

 find / -maxdepth 1 -type l | while read -r LINK_NAME; 
do 
    TARGET=$(readlink -f "${LINK_NAME}") 
    printf "%-40s %-50s\n" "$LINK_NAME" "$TARGET" 
done >> "$ALL_LINKS_FILE"

# Find valid links and save to temporary file
#printf "%-40s %-50s\n" "Link Name" "Target" > "$VALID_LINKS_FILE"

 find / -maxdepth 1 -type l | while read -r LINK_NAME; do 
    TARGET=$(readlink -e "${LINK_NAME}") 
    [ -n "$LINK_NAME" ] && [ -n "$TARGET" ] && printf "%-40s %-50s\n" "$LINK_NAME" "$TARGET"
done >> "$VALID_LINKS_FILE"

# Sort the files
 sort "$ALL_LINKS_FILE" -o "$ALL_LINKS_FILE"
 sort "$VALID_LINKS_FILE" -o "$VALID_LINKS_FILE"

# Find invalid links by comparing all_links and valid_links
 comm -13 "$VALID_LINKS_FILE" "$ALL_LINKS_FILE" > "$INVALID_LINKS_FILE"

# Count links
ALL_LINK_COUNT=$(wc -l < "$ALL_LINKS_FILE")
VALID_LINK_COUNT=$(wc -l < "$VALID_LINKS_FILE")
INVALID_LINK_COUNT=$(wc -l < "$INVALID_LINKS_FILE")

# Display counts and details
if [ "$ALL_LINK_COUNT" -eq 0 ]; then
    echo "No symbolic links found in the root directory."
else
    echo "Total Number of symbolic links found: $ALL_LINK_COUNT"
    echo "Details of symbolic links:"
     cat "$ALL_LINKS_FILE"
    echo "-----------------------------------------------------"

    if [ "$VALID_LINK_COUNT" -eq 0 ]; then
        echo "No active (valid) symbolic links found."
    else
        echo "Total Number of active (valid) symbolic links: $VALID_LINK_COUNT"
        #echo "Details of active (valid) symbolic links:" |  tee -a "$output_file"
		echo "Details of active (valid) symbolic links:" 
        cat "$VALID_LINKS_FILE"
		#grep "/data" "$VALID_LINKS_FILE" |  tee -a "$output_file"
		grep "/data" "$VALID_LINKS_FILE" 
        echo "-----------------------------------------------------"
    fi

    if [ "$INVALID_LINK_COUNT" -gt 0 ]; then
        echo "Number of inactive (invalid) symbolic links: $INVALID_LINK_COUNT"
        echo "Details of inactive (invalid) symbolic links:"
         cat "$INVALID_LINKS_FILE"
        echo "-----------------------------------------------------"
    fi
fi


# Clean up temporary files (This checks if the variable is non-empty,if the file specified by the variable exists,removed the file specified by the variable
[ -n "${ALL_LINKS_FILE}" ] && [ -f "${ALL_LINKS_FILE}" ] &&  rm -f "${ALL_LINKS_FILE}"
[ -n "${VALID_LINKS_FILE}" ] && [ -f "${VALID_LINKS_FILE}" ] &&  rm -f "${VALID_LINKS_FILE}"
[ -n "${INVALID_LINKS_FILE}" ] && [ -f "${INVALID_LINKS_FILE}" ] &&  rm -f "${INVALID_LINKS_FILE}"