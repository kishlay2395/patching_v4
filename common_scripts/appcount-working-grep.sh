#! /bin/sh -xv
#-------------------------------------------
#Define Colors in the variables. 

DATE_TIME=$(date -u +%d-%b-%Y-%H:%M:%S)
#-------------------------------------------

# Check if an argument is provided
# if [ $# -ne 1 ]; then
#    echo "Usage: $0 <check argument value>"
#    exit 1
#fi

##Assign the argument to the variable Host_IP
Host_IP="$(hostname -I | awk '{print $1}')"

# Using top command to identify the java process 
Total_App_Process_Count=$(ps -aux | grep -w Standalone | grep -v grep |wc -l)

echo "-------------------------------------------------------------------------------";
echo -e "Total number of App process running on this host" ${Host_IP} 
echo -e "Total number of App java process available is ${Total_App_Process_Count}"
echo "-------------------------------------------------------------------------------";


if [[ ${Total_App_Process_Count} != '0' ]]
then 
	echo -e "\n \n********************** IP address is \"$Host_IP\"**********************" 
	echo -e "-----------------------------------------------------------------------" 
	
	echo -e "----------------------------------------------------------------------------------------------------------------------------------------------"  
	echo -e " PID       AppName      JbossVersion  Java-Name              Port-No        	 URL     Status  SSL-Status   	App-Path% " 
	echo -e "----------------------------------------------------------------------------------------------------------------------------------------------" 
	
	#ps -aux | grep -w appadmin | grep java | head -n 1|  while read value
	ps aux --sort comm | egrep -w 'appadmin|root'| grep -w java | grep -w Standalone  |while read value	
		do
			# To print the selected line value 
			# echo $value
			App_Pid_java_process_name=$(echo $value | awk '{print $2}')
			
			IFS='/' read -ra myAppArray <<< "$value"
			j=0;
			for i in "${!myAppArray[@]}"; 
				do
					if [[ "${myAppArray[$i]}" == "bin" ]]
					then
						j=$((i+1))			
						App_Java_process_name=$(echo ${myAppArray[$j]} | cut -d " " -f 1)
						#Storing value into array. 
						
						App_Standalone_path=$(ps -aux | grep -w ${App_Pid_java_process_name} | rev | cut -d = -f 1 | rev | cut -d " " -f 1 | grep /)					
						
						AppName=$(find $App_Standalone_path -wholename "*/standalone/configuration" -exec ls -ld {} \; | rev | cut -d "/" -f 3 | rev | tail -1)
						
						AppBinpath=$(find $App_Standalone_path -wholename "*/standalone/configuration" -exec ls -ld {} \; | rev | cut -d "/" -f 3- | cut -d " " -f 1 | rev  | tail -1)/bin/ 
						
						#Temp_JbossVersion=$(find $App_Standalone_path ! -path '*/.*' -wholename "*/standalone/configuration" -exec ls -ld {} \; | rev | cut -d "/" -f 4 | rev  | tail -1)
						JbossVersion=$(echo ${AppBinpath} | grep -oh "jboss\w*")
						
						#checking jboss7 related version details
						Jboss_Version_7_Check=$(echo ${JbossVersion} | grep -E 'jboss71|jboss700eap|jboss72|jboss720eap|jboss730eap|jboss740eap|*biportal|biportal*|*biportal*')
	
						#Checking above command gets ouptut or not. 
						Jboss_Version_7_Check=$(echo "$?")
	
						Jboss_Version_6_Check=$(echo ${JbossVersion} | grep -E 'jboss61eap|jboss62eap')
						Jboss_Version_6_Check=$(echo "$?")
						
						if [[ $Jboss_Version_7_Check == 0 ]]
						then
							#echo -e "\n"
							#echo "Instance is either Jboss72 or Jboss720eap or Jboss730eap or Jboss740eap"
							AppPort_No_Stand=$(grep \name\=\"http\"\ port ${App_Standalone_path}/configuration/standalone.xml | cut -d '"' -f 4 | cut -d ':' -f 2 | cut -d '}' -f 1)
						else
							#echo " Instance is jboss62 or wildfly related"
							if [[ $Jboss_Version_6_Check ==  0 ]]
							then
								AppPort_No_Stand=$(grep \name\=\"http\"\ port ${App_Standalone_path}/configuration/standalone.xml | cut -d '"' -f 4)
							else
								#instance is configured in wildfly
								AppPort_No_Stand=$(grep \name\=\"http\"\ port ${App_Standalone_path}/configuration/standalone.xml |  cut -d ':' -f 2 | cut -c 1-5 )
							fi 
						fi				
						
						# validate port using netstat command
						App_Port_Netstat=$(netstat -anop 2>/dev/null | grep -w ${App_Pid_java_process_name} | grep -w tcp | grep -w "LISTEN" |awk {'print $4'} |cut -d : -f 2 )
					
					
										
						if [[ "${AppPort_No_Stand}" == "80" ]]  
						then							
							
							AppPort_No=${AppPort_No_Stand}							
							
						else [[ "${AppPort_No_Stand}" == "${App_Port_Netstat}" ]]																
							AppPort_No=${AppPort_No_Stand}								
						fi
							
						
													
						#App-URL-Related
						
						App_Url="${Host_IP}:${AppPort_No}"
						
						#status_code=$(curl -sI -w "%{http_code}" ${App_Url} | tail -1)
						Url_status_code=$(curl -s -o /dev/null -w "%{http_code}" "$App_Url")
						
						if [ "${Url_status_code}" == "200" ]
						then
							Url_Status="UP"
							Url_status_code="${Url_status_code}"
						else
							Url_Status="Down"
							Url_status_code="${Url_status_code}"
						fi
						
						echo "Checked URL: $App_Url - Status Code: $status_code - Status: $Url_Status"

						
						#checking ssl enabled or disbaled details

						SSL_check=$(grep -r '<https-listener name="https"' ${App_Standalone_path}/configuration/standalone.xml )
						
						#Checking above command gets ouptut or not. 
						SSL_validation=$(echo "$?")
						
						if [[ $SSL_validation == 0 ]]
						then
							#echo "SSL is enabled to this instnace" 
							SSL_Status="Enabled";
						else 
							#echo "SSL is not enabled to this instnace" 
							SSL_Status="Disabled";
						fi
						
	
						printf "%-10s %-16s %-12s %-25s %-6s %6s %-6s %-10s %10s" $App_Pid_java_process_name $AppName $JbossVersion $App_Java_process_name $AppPort_No $App_Url $Url_Status $Url_status_code $SSL_Status $App_Standalone_path
						printf "\n"
						break
					fi			
				done
		done
else
	echo -e "Jboss applications are not running on this server" 
fi
echo "-------------------------------------------------------------------------------";
