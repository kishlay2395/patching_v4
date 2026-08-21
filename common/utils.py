import boto3
import csv
import subprocess
import psycopg2
import os
import logging
import json
import time
from configparser import ConfigParser
import os_upgrade

pid = os_upgrade.pid

def get_cloudwatch_params(section_name="cloudwatch"):
    filename = os.getcwd() + "/config/cloudwatchlog.ini"
    parser = ConfigParser()
    parser.optionxform = str
    parser.read(filename)
    cloudwatch = {}
    if parser.has_section(section_name):
        params = parser.items(section_name)
        for param in params:
            cloudwatch[param[0]] = param[1].strip("'")
    else:
        raise Exception("Section {0} not found in file: {1}".format(section_name, filename))
    return cloudwatch


cw_config =get_cloudwatch_params()
LOG_GROUP = cw_config["LOG_GROUP"]
LOG_STREAM = cw_config["LOG_STREAM"]

def get_profiles():
    profileList = ['default', 'healthcare', 'denso']
    return(profileList)

def get_regions():
    regionsList = []
    region_client = boto3.client('ec2')
    response = region_client.describe_regions()
    regions = response.get('Regions')
    for region in regions:
        regionsList.append(region['RegionName'])
    return(regionsList)

def get_db_params(db_details):
    filename = os.getcwd() + "/config/db_cfg.ini"
    parser = ConfigParser()
    parser.read(filename)
    db = {}
    if parser.has_section(db_details):
        params = parser.items(db_details)
        for param in params:
            db[param[0]] = param[1]
    else:
        raise Exception ("Section {0} not found in file: {1}".format(db_details, filename))
    return db

def run_select_sql(db_details, select_sql):
    try:
        params = get_db_params(db_details)
        message = ("Connecting to Postgres database...")
        log_level = "INFO"
        write_cw_logs(pid, log_level, message)
        connection = psycopg2.connect(**params)
        cursor = connection.cursor()
        cursor.execute(select_sql)
        retrieved_records = cursor.fetchall()
        #print(retrieved_records)
        cursor.close()
        return(retrieved_records)
    except Exception as error:
        #print(error)
        message = (error)
        log_level = "ERROR"
        write_cw_logs(pid, log_level, message)
    finally:
        if connection is not None:
            connection.close()
            #print ("Database connection closed.")

def bulk_insert(db_details, insert_statement, records):
    try:
        params = get_db_params(db_details)
        message = ("Connecting to Postgres database...")
        log_level = "INFO"
        write_cw_logs(pid, log_level, message)
        connection = psycopg2.connect(**params)
        cursor = connection.cursor()
        result = cursor.executemany(insert_statement, records)
        connection.commit()
        cursor.close()
        message = (cursor.rowcount, "Record(s) inserted successfully into table")
        log_level = "INFO"
        write_cw_logs(pid, log_level, message)
    except Exception as error:
       # print(error)
        message = error
        log_level = "ERROR"
        write_cw_logs(pid, log_level, message)
    finally:
        if connection:
            cursor.close()
            connection.close()

def run_cmd(command):
    #Make sure command is in a list
    cmd = command.split()
    output = subprocess.run(cmd, stdout=subprocess.PIPE)
    output = output.stdout.decode('utf-8')
    return (output)

def execute_shell_command(command):
    output = None
    error = None
    # print (command)
    command = command.split()
    message = ("Executing command: ", command)
    log_level = "INFO"
    write_cw_logs(pid, log_level, message)
    try:
        process = subprocess.Popen(
            command,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        )
        out, err = process.communicate()
        if out:
            output = out.decode('utf-8')
            # print (output)
            message = ("Executed command Output: ", output)
            log_level = "INFO"
            write_cw_logs(pid, log_level, message)
            output = json.loads(output)
            return(output, error)
        if err:
            error = err.decode('utf-8')
            #print (error)
            message = ("Executed command Error: ", error)
            log_level = "INFO"
            write_cw_logs(pid, log_level, message)
        return(output, error)
    except Exception as e:
        error = e
    # logger.info("Executed command Output: ", output)
    message = ("Executed command Error: ", error)
    log_level = "INFO"
    write_cw_logs(pid, log_level, message)
    return(output, error)

def write_cw_logs(pid, log_level, message):  
    cwclient = boto3.client('logs') ## Add this in your utils file
    cw_message = {
        "pid": pid,
        "logger_level": log_level,
        "message": message
    }
    json_message = json.dumps(cw_message)
    response = cwclient.put_log_events(
        logGroupName = LOG_GROUP,
        logStreamName = LOG_STREAM,
        logEvents = [
            {
                "timestamp": int(round(time.time() * 1000)),
                "message": json_message
            }
        ]
    )
    return (response)

