# Capture the time zone using timedatectl
TIMEZONE_INFO=$(timedatectl | grep "Time zone:" | cut -d : -f 2)

# Check if the command was successful
if [ $? -eq 0 ]; then
    #echo "Time Zone Information:"
    printf "%-20s %10s\n" "Time Zone Information=" "$TIMEZONE_INFO" 
else
    echo "Failed to retrieve time zone information."
fi
echo -e "-------------------------\n"

# Display a message indicating where the information has been saved
# echo "Time zone information has been written to $output_file."