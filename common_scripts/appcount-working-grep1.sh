#!/bin/bash -xv
#-------------------------------------------
# Define Date and Host IP
DATE_TIME=$(date -u +%d-%b-%Y-%H:%M:%S)
Host_IP="$(hostname -I | awk '{print $1}')"
#-------------------------------------------

center() {
    local str="$1"
    local width="$2"
    local len=${#str}
    local pad=$(( (width - len) / 2 ))
    printf "%*s%s%*s\n" $pad "" "$str" $((width - len - pad)) ""
}

# Example usage
# center "Center" 20

# Count Java Processes with "Standalone"
Total_App_Process_Count=$(ps -aux | grep -w Standalone | grep -v grep | wc -l)

echo "-------------------------------------------------------------------------------"
echo "Total number of App processes on host ${Host_IP}: ${Total_App_Process_Count}"
echo "-------------------------------------------------------------------------------"

if [[ ${Total_App_Process_Count} -ne 0 ]]; then
    echo -e "\n********************** IP address: \"$Host_IP\" **********************"
    echo "-----------------------------------------------------------------------"
    echo "----------------------------------------------------------------------------------------------------------------------------------------------"
    #echo " PID       AppName      JbossVersion      Java-Name                 Port-No    URL         Status  Code    SSL-Status     App-Path"
	printf "%-8s %-15s %-15s %-25s %-8s %-20s %-6s %-6s %-12s %s\n" \
  "PID" "AppName" "JbossVersion" "Java-Name" "Port" "URL" "Status" "Code" "SSL-Status" "App-Path"

	#printf "%-8s  %-15s  %-14s  %-25s  %-8s  %-22s  %6s  %-6s  %-12s  %s\n" \
  #"$App_Pid" "$AppName" "$JbossVersion" "$App_Java_Name" "$AppPort_No" "$App_Url" "$Url_Status" "$Url_status_code" "$SSL_Status" #"$App_Path"

    echo "----------------------------------------------------------------------------------------------------------------------------------------------"

    ps aux --sort comm | egrep -w 'appadmin|root' | grep -w java | grep -w Standalone | while read -r line; do
        App_Pid=$(echo "$line" | awk '{print $2}')
        IFS='/' read -ra parts <<< "$line"

        for i in "${!parts[@]}"; do
            if [[ "${parts[$i]}" == "bin" ]]; then
                App_Java_Name=$(echo "${parts[$((i+1))]}" | cut -d " " -f 1)
                
                App_Path=$(ps -aux | grep -w "$App_Pid" | rev | cut -d '=' -f1 | rev | cut -d ' ' -f1 | grep /)
                AppName=$(find "$App_Path" -wholename "*/standalone/configuration" -exec ls -ld {} \; | rev | cut -d '/' -f 3 | rev | tail -1)
                AppBinPath=$(find "$App_Path" -wholename "*/standalone/configuration" -exec ls -ld {} \; | rev | cut -d '/' -f 3- | cut -d ' ' -f1 | rev | tail -1)/bin/
                
                #JbossVersion=$(echo "$AppBinPath" | grep -oh "jboss[0-9a-z]*")
				JbossVersion=$(echo "$AppBinPath" | grep -oh "jboss[0-9a-z]*\|wildfly[0-9a-z]*")
                
                if echo "$JbossVersion" | grep -Eq 'jboss71|jboss700eap|jboss72|jboss720eap|jboss730eap|jboss740eap|jboss800eap|biportal'; then
                    AppPort_No_Stand=$(grep 'name="http" port' "$App_Path/configuration/standalone.xml" | cut -d '"' -f 4 | cut -d ':' -f2 | cut -d '}' -f1)
                elif echo "$JbossVersion" | grep -Eq 'jboss61eap|jboss62eap'; then
                    AppPort_No_Stand=$(grep 'name="http" port' "$App_Path/configuration/standalone.xml" | cut -d '"' -f4)
                #elif echo "$JbossVersion" | grep -Eq 'wildfly1501|wildfly1801'; then
				else 				
                    AppPort_No_Stand=$(grep 'name="http" port' "$App_Path/configuration/standalone.xml" | cut -d ':' -f2 | cut -c1-5)
                fi

                # Validate using netstat
                App_Port_Netstat=$(netstat -anop 2>/dev/null | grep -w "$App_Pid" | grep -w tcp | grep LISTEN | awk '{print $4}' | cut -d ':' -f2)
                AppPort_No=${AppPort_No_Stand:-$App_Port_Netstat}

                # Check URL status
                App_Url="${Host_IP}:${AppPort_No}"
                Url_status_code=$(curl --max-time 5 -s -o /dev/null -w "%{http_code}" "$App_Url")

                if [[ "$Url_status_code" == "200" ]]; then
                    Url_Status="UP"
                else
                    Url_Status="Down"
                fi

                # Check SSL
                if grep -q '<https-listener name="https"' "$App_Path/configuration/standalone.xml"; then
                    SSL_Status="Enabled"
                else
                    SSL_Status="Disabled"
                fi

                printf "%-8s %-15s %-15s %-25s %-8s %-20s %-6s %-6s %-12s %s\n" \
                    "$App_Pid" "$AppName" "$JbossVersion" "$App_Java_Name" "$AppPort_No" "$App_Url" "$Url_Status"  "$Url_status_code" "$SSL_Status" "$App_Path"
				
				#printf "%-10s %-16s %-12s %-25s %-6s %6s %-6s %-6s %-10s %10s" $App_Pid_java_process_name $AppName $JbossVersion $App_Java_process_name $AppPort_No $App_Url $Url_Status $Url_status_code $SSL_Status $App_Standalone_path				

                break
            fi
        done
    done
else
    echo "No JBoss applications are currently running on this server."
fi

echo "-------------------------------------------------------------------------------"
