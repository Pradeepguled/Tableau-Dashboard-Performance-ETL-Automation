import subprocess
import time
from datetime import datetime
import json
import os
import shutil
import csv
import boto3
from botocore.exceptions import NoCredentialsError
import xml.etree.ElementTree as ET

# Function to load configuration from JSON file
def load_config(config_file):
    with open(config_file, 'r') as file:
        config = json.load(file)
    return config

# Function to copy vizpool.csv to the specified directory
def copy_vizpool_file(source_file, target_directory):
    if os.path.exists(source_file):
        shutil.copy(source_file, target_directory)
        print(f'Copied {source_file} to {target_directory}')
    else:
        print(f'vizpool.csv file not found at {source_file}')

# Function to find the latest folder containing wincounter.tsv and copy it to the target directory
def copy_latest_wincounter_file(results_directory, target_directory):
    latest_directory = max([os.path.join(results_directory, d) for d in os.listdir(results_directory)], key=os.path.getmtime)
    wincounter_file = os.path.join(latest_directory, 'wincounter.tsv')

    if os.path.exists(wincounter_file):
        output_file = os.path.join(target_directory, 'wincounter.tsv')
        current_date = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

        with open(wincounter_file, 'r') as infile, open(output_file, 'w') as outfile:
            for line in infile:
                line = line.strip()
                if line:
                    outfile.write(f"{line}\t{current_date}\n")

        print(f'Modified wincounter.tsv saved to {output_file}')
        return output_file
    else:
        print(f'No wincounter.tsv file found in the latest directory: {latest_directory}')
        return None

# Function to parse thread details and save them to a CSV file with appended date
def parse_threads_to_csv(log_file, output_csv):
    current_date = datetime.now().strftime('%d-%m-%Y')
    thread_details = []
    
    with open(log_file, 'r') as file:
        lines = file.readlines()
        for line in lines:
            line = line.strip()
            if line.startswith('#'):
                line_with_date = f"{line}"
                thread_details.append(line_with_date)

    with open(output_csv, 'w', newline='') as csvfile:
        csv_writer = csv.writer(csvfile)
        for detail in thread_details:
            csv_writer.writerow([detail])

    print(f'Thread details saved to {output_csv} with appended date {current_date}')

# Function to parse the summary line and save it in the required format
def parse_summary_line_to_csv(log_file, output_csv):
    current_date = datetime.now().strftime('%Y-%m-%d')
    with open(log_file, 'r') as file:
        lines = file.readlines()
        for line in lines:
            line = line.strip()
            if line.startswith('summary ='):
                parts = line.split()
                avg = parts[8].strip(',')
                min_val = parts[10].strip(',')
                max_val = parts[12].strip(',')
                err = parts[14] + " " + parts[15].strip('()')
                break

    with open(output_csv, 'w', newline='') as csvfile:
        csv_writer = csv.writer(csvfile)
        csv_writer.writerow(['Avg', f"{avg}", current_date])
        csv_writer.writerow(['Min', f"{min_val}", current_date])
        csv_writer.writerow(['Max', f"{max_val}", current_date])
        csv_writer.writerow(['Err', f"{err}", current_date])

    print(f'Summary line saved to {output_csv}')

# Function to parse result-inblrlt-collectorwin10-0.jtl and save it to workbook.csv
def parse_result_jtl_to_csv(jtl_file, output_csv):
    tree = ET.parse(jtl_file)
    root = tree.getroot()

    with open(output_csv, 'w', newline='') as csvfile:
        csv_writer = csv.writer(csvfile)
        csv_writer.writerow(['t', 'lt', 'ts', 's', 'lb', 'rc', 'rm', 'tn', 'dt', 'by', 'ng', 'na'])

        for sample in root.iter('sample'):
            t = sample.get('t')
            lt = sample.get('lt')
            ts = sample.get('ts')
            s = sample.get('s')
            lb = sample.get('lb')
            rc = sample.get('rc')
            rm = sample.get('rm')
            tn = sample.get('tn')
            dt = sample.get('dt')
            by = sample.get('by')
            ng = sample.get('ng')
            na = sample.get('na')
            
            csv_writer.writerow([t, lt, ts, s, lb, rc, rm, tn, dt, by, ng, na])

    print(f'Results from {jtl_file} saved to {output_csv}')

# Function to run TabJolt test cases
def run_tabjolt_test(config):
    command = config["command"]
    directory = config["directory"]

    timestamp = datetime.now().strftime('%Y%m%d%H%M%S')
    output_file = f'tabjolt_output_{timestamp}.txt'
    error_file = f'error_log_{timestamp}.txt'

    print('Starting TabJolt test cases...')
    start_time = time.time()

    try:
        process = subprocess.Popen(command, cwd=directory, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, encoding='utf-8')
        stdout, stderr = process.communicate()

        with open(output_file, 'w') as file:
            file.write(stdout)

        if stderr:
            with open(error_file, 'w') as err_file:
                err_file.write(stderr)

        print(f'TabJolt test cases completed. Output written to {output_file}')

        end_time = time.time()
        elapsed_time = end_time - start_time
        print(f'Time taken: {elapsed_time:.2f} seconds')

        # Copy the latest wincounter.tsv file and add current date
        wincounter_file = copy_latest_wincounter_file(config["results_directory"], config["target_directory"])

        if wincounter_file:
            # Parse thread details and save to CSV
            parse_threads_to_csv(output_file, 'thread_details.csv')
            
            # Parse summary line and save to CSV
            parse_summary_line_to_csv(output_file, 'summary_line.csv')
            
            # Parse result-inblrlt-collectorwin10-0.jtl and save to workbook.csv
            latest_directory = max([os.path.join(config["results_directory"], d) for d in os.listdir(config["results_directory"])], key=os.path.getmtime)
            jtl_file = os.path.join(latest_directory, 'result-inblrlt-collectorwin10-0.jtl')
            parse_result_jtl_to_csv(jtl_file, 'workbook.csv')
            
            # Modify workbook.csv to add additional column with Site value
            modify_workbook_csv('workbook.csv', 'modified_workbook.csv')
            
            # Upload files to S3
            upload_to_s3(wincounter_file, config["s3_bucket"],config["folder_name"], 'wincounter.tsv', config["aws_access_key_id"], config["aws_secret_access_key"])
            upload_to_s3('thread_details.csv', config["s3_bucket"], config["folder_name"],'thread_details.csv', config["aws_access_key_id"], config["aws_secret_access_key"])
            upload_to_s3('summary_line.csv', config["s3_bucket"], config["folder_name"],'summary_line.csv', config["aws_access_key_id"], config["aws_secret_access_key"])
            upload_to_s3('modified_workbook.csv', config["s3_bucket"], config["folder_name"],'modified_workbook.csv', config["aws_access_key_id"], config["aws_secret_access_key"])
            upload_to_s3(output_file, config["s3_bucket"], config["folder_name"],f'tabjolt_output_{timestamp}.txt', config["aws_access_key_id"], config["aws_secret_access_key"])

    except subprocess.CalledProcessError as e:
        print(f'Error: Command "{command}" returned non-zero exit status {e.returncode}.')

# Function to upload a file to S3
def upload_to_s3(file_name, bucket,folder_name, s3_file_name, aws_access_key, aws_secret_key):
    s3 = boto3.client('s3', aws_access_key_id=aws_access_key, aws_secret_access_key=aws_secret_key)
    try:
        s3_key = f'{folder_name}/{s3_file_name}'

        s3.upload_file(file_name, bucket,s3_key)
        print(f'File uploaded successfully to S3: {folder_name}/{s3_file_name}')
        return True
    except FileNotFoundError:
        print(f'The file {file_name} was not found.')
        return False
    except NoCredentialsError:
        print('Credentials not available.')
        return False

# Function to modify workbook.csv to add additional column with Site value
def modify_workbook_csv(input_csv, output_csv):
    lines = []
    with open(input_csv, 'r', newline='') as infile:
        reader = csv.reader(infile)
        lines = list(reader)

    if not lines:
        print(f'No data found in {input_csv}')
        return

    current_site_value = None
    modified_lines = []

    for i in range(len(lines)):
        if lines[i][6].startswith('Site'):
            current_site_value = lines[i][6]
        if current_site_value:
            modified_lines.append(lines[i] + [current_site_value])
        else:
            modified_lines.append(lines[i] + [''])

    with open(output_csv, 'w', newline='') as outfile:
        writer = csv.writer(outfile)
        writer.writerows(modified_lines)

    print(f'Modified workbook saved to {output_csv}')

# Main function to execute the TabJolt automation process
def main():
    config = load_config('C:\\Tabjolt_python_scripts\\tabjolt_repo_bmi\\config.json')
    copy_vizpool_file(config["vizpool_source_file"], config["vizpool_target_directory"])
    run_tabjolt_test(config)

if __name__ == "__main__":
    main()
