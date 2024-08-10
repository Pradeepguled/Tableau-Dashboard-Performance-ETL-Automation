import vertica_python
import os
import json
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.image import MIMEImage
import matplotlib.pyplot as plt
import boto3
from botocore.exceptions import NoCredentialsError

def load_config(config_file):
    with open(config_file, 'r') as f:
        config = json.load(f)
    return config

def download_from_s3(bucket_name,folder_path, s3_key, local_path, aws_access_key_id, aws_secret_access_key, region_name):
    try:
        s3 = boto3.client(
            's3',
            aws_access_key_id=aws_access_key_id,
            aws_secret_access_key=aws_secret_access_key,
            region_name=region_name
        )
        full_s3_key = f"{folder_path}/{s3_key}"
        s3.download_file(bucket_name, full_s3_key, local_path)
        print(f"Downloaded {full_s3_key} from S3 to {local_path}")
    except NoCredentialsError:
        print("Credentials not available")
    except Exception as e:
        print(f"Error downloading {full_s3_key} from S3: {e}")

def load_file_to_vertica(file_path, table_name, delimiter, skip_header=False, conn_info=None):
    file_path = file_path.replace('\\', '/')
    skip_header_clause = "SKIP 1" if skip_header else ""
    copy_command = (
        "COPY {} FROM LOCAL '{}' DELIMITER '{}' {} REJECTED DATA 'rejected.txt';".format(
            table_name, file_path, delimiter, skip_header_clause
        )
    )

    try:
        with vertica_python.connect(**conn_info) as connection:
            cur = connection.cursor()
            try:
                cur.execute(copy_command)
                print(f"Data loaded successfully into {table_name} table.")
                connection.commit()
                print("Changes committed.")
            except vertica_python.errors.QueryError as e:
                print(f"Query error: {e}")
                connection.rollback()
            finally:
                cur.close()
    except vertica_python.errors.ConnectionError as e:
        print(f"Connection error: {e}")

def execute_queries_with_messages(queries_with_messages, conn_info):
    query_results = []

    try:
        with vertica_python.connect(**conn_info) as connection:
            cur = connection.cursor()
            try:
                for query, message in queries_with_messages:
                    cur.execute(query)
                    results = cur.fetchall()
                    query_result = f"{message}\n"
                    for result in results:
                        query_result += f"{result[0]}\n"
                    query_results.append(query_result)
            except vertica_python.errors.QueryError as e:
                print(f"Query error: {e}")
            finally:
                cur.close()
    except vertica_python.errors.ConnectionError as e:
        print(f"Connection error: {e}")

    return query_results

def create_average_time_graph(conn_info):
    try:
        with vertica_python.connect(**conn_info) as connection:
            cur = connection.cursor()
            try:
                cur.execute("SELECT summary_timestamp, summary_value FROM tabjolt.summary_line WHERE summary_metrix = 'Avg' ORDER BY summary_timestamp;")
                results = cur.fetchall()
                if results:
                    dates = [result[0] for result in results]
                    values = [int(result[1]) for result in results]

                    plt.figure(figsize=(10, 6))

                    dates, values = zip(*sorted(zip(dates, values)))

                    plt.plot(dates, values, marker='o', linestyle='-')
                    plt.xlabel('Date')
                    plt.ylabel('Average Time (ms)')
                    plt.title('Average Time Taken for Tabjolt Run (Day Wise)')
                    plt.xticks(rotation=45)

                    max_value = max(values)
                    plt.yticks(range(1000, (int(max_value / 1000) + 1) * 1000 + 1000, 1000))

                    for i, (date, value) in enumerate(zip(dates, values)):
                        plt.annotate(f'{value}', (date, value), textcoords="offset points", xytext=(0,10), ha='center')

                    plt.tight_layout()

                    graph_path = '/ebs/pradeep/tabjolt/genral/average_time_graph.png'
                    plt.savefig(graph_path)
                    plt.close()
                    
                    return graph_path
                else:
                    print("No results found for the average time.")
            except vertica_python.errors.QueryError as e:
                print(f"Query error: {e}")
            finally:
                cur.close()
    except vertica_python.errors.ConnectionError as e:
        print(f"Connection error: {e}")

def send_email_with_graph(subject, query_results, graph_path, performance_samples_query,performance_samples_avg, performance_less_avg,conn_info, smtp_config):
    sender = smtp_config['sender_email']
    smtp_username = smtp_config['smtp_username']
    smtp_password = smtp_config['smtp_password']
    smtp_server = smtp_config['smtp_server']
    smtp_port = smtp_config['smtp_port']
    recipients = smtp_config['recipient_emails']

    msg = MIMEMultipart()
    msg['From'] = sender
    msg['To'] = ', '.join(recipients)
    msg['Subject'] = subject

    html_table = f"""
    <html>
    <head>
        <style>
            table {{
                border-collapse: collapse;
                width: 100%;
                font-family: Roboto, sans-serif;
            }}
            th, td {{
                border: 1px solid #dddddd;
                text-align: left;
                padding: 8px;
            }}
            th {{
                background-color: #d3f9d8; /* Fixed header color */
                color: black;
            }}
            h1 {{
                color: #333;
            }}
            .note {{
                font-size: 0.8em;
                color: #555;
            }}
        </style>
    </head>
    <body>
        <h1>{subject}</h1>
        <p>Hi,</p>
        <p style="font-size: 15px; font-weight: bold; text-align: center;">Here are the results from the latest Tabjolt run:</p>
        <table>
            <thead>
                <tr>
                    <th>Metric</th>
                    <th>Value</th>
                </tr>
            </thead>
            <tbody>
    """

    for result in query_results:
        lines = result.split('\n')
        if len(lines) > 1:
            metric = lines[0].strip()
            value = lines[1].strip()

            html_table += f"""
            <tr>
                <td>{metric}</td>
                <td>{value}</td>
            </tr>
            """
    
    html_table += """
            </tbody>
        </table>
        <p>Attached is the graph showing the average time taken (day wise) for the Tabjolt run:</p>
        <img src="cid:graph_cid" alt="Average Time Graph" style="display: block; margin: 20px auto;">
    """



    html_table += """
    <p style="font-size: 15px; font-weight: bold; text-align: center;">Here are the performance samples where Elapsed time is more than average:</p>
    <table>
        <thead>
            <tr>
                <th style="color:Black;">AVG_Elapsed_time_ms</th>
                <th style="color:Black;">Current_Elapsed_time</th>
                <th style="color:Black;">Response message</th>
                <th style="color:Black;">Percentage difference</th>
            </tr>
        </thead>
        <tbody>
    """

    try:
        with vertica_python.connect(**conn_info) as connection:
            cur = connection.cursor()
            cur.execute(performance_samples_avg)
            results = cur.fetchall()
            for row in results:
                avg_elapsed_ms, current_elapsed_ms, response_message, percentage_difference = row
                
                # Determine cell text color
                text_color = "color: red;" if percentage_difference > 20.0 else ""
                
                html_table += "<tr>"
                for col in row:
                    # Format the percentage difference to 2 decimal places
                    if isinstance(col, float):
                        col = f"{col:.2f}%"
                    html_table += f"<td style='{text_color}'>{col}</td>"
                html_table += "</tr>"
    except vertica_python.errors.QueryError as e:
        print(f"Error fetching performance samples: {e}")
    finally:
        cur.close()

    html_table += """
        </tbody>
    </table>
    </body>
    </html>
    """




    # Add table for performance samples data
    html_table += """
        <p style="font-size: 15px; font-weight: bold; text-align: center;">Here are the performance samples data:</p>
        <table>
            <thead>
                <tr>
                    <th>Elapsed_time_ms</th>
                    <th>Latency_time_ms</th>
                    <th>Success_indicator</th>
                    <th>Request_label</th>
                    <th>Response_message</th>
                    <!-- Add more headers as per your performance samples table structure -->
                </tr>
            </thead>
            <tbody>
    """

    try:
        with vertica_python.connect(**conn_info) as connection:
            cur = connection.cursor()
            cur.execute(performance_samples_query)
            results = cur.fetchall()
            for row in results:
                html_table += "<tr>"
                for col in row:
                    html_table += f"<td>{col}</td>"
                html_table += "</tr>"
    except vertica_python.errors.QueryError as e:
        print(f"Error fetching performance samples: {e}")
    finally:
        cur.close()

    html_table += """
            </tbody>
        </table>
    </body>
    </html>
    """

    html_table += """
        <p style="font-size: 15px; font-weight: bold; text-align: center;">Sites that are taking more than 50% less time compared to the average time:</p>
        <table>
            <thead>
                <tr>
                <th style="color:Red;">AVG_Elapsed_time_ms</th>
                <th style="color:Red;">Current_Elapsed_time</th>
                <th style="color:Red;">Response message</th>
                <th style="color:Red;">Percentage difference</th>
                    <!-- Add more headers as per your performance samples table structure -->
                </tr>
            </thead>
            <tbody>
    """

    try:
        with vertica_python.connect(**conn_info) as connection:
            cur = connection.cursor()
            cur.execute(performance_less_avg)
            results = cur.fetchall()
            for row in results:
                html_table += "<tr>"
                for col in row:
                    html_table += f"<td>{col}</td>"
                html_table += "</tr>"
    except vertica_python.errors.QueryError as e:
        print(f"Error fetching performance samples: {e}")
    finally:
        cur.close()

    html_table += """
            </tbody>
        </table>
    </body>
    </html>
    """

    # Add table for performance samples data
    


    msg.attach(MIMEText(html_table, 'html'))

    with open(graph_path, 'rb') as f:
        img = MIMEImage(f.read())
        img.add_header('Content-ID', '<graph_cid>')
        img.add_header('Content-Disposition', 'inline', filename=os.path.basename(graph_path))
        msg.attach(img)

    try:
        server = smtplib.SMTP_SSL(smtp_server, smtp_port)
        server.login(smtp_username, smtp_password)
        text = msg.as_string()
        server.sendmail(sender, recipients, text)
        server.quit()
        print("Email sent successfully.")
    except Exception as e:
        print(f"Failed to send email: {e}")

if __name__ == "__main__":
    config = load_config('config.json')
    vertica_config = config['vertica']
    smtp_config = config['smtp']
    s3_config = config['s3']

    files_to_download = [
        ('wincounter.tsv', '/ebs/pradeep/tabjolt/genral/wincounter.tsv'),
        ('summary_line.csv', '/ebs/pradeep/tabjolt/genral/summary_line.csv'),
        ('thread_details.csv', '/ebs/pradeep/tabjolt/genral/thread_details.csv'),
        ('modified_workbook.csv', '/ebs/pradeep/tabjolt/genral/modified_workbook.csv')
    ]

    for s3_key, local_path in files_to_download:
        download_from_s3(s3_config['bucket_name'], s3_config['folder_path'],s3_key, local_path, s3_config['aws_access_key_id'], s3_config['aws_secret_access_key'], s3_config['region_name'])

    files_to_load = [
        ('/ebs/pradeep/tabjolt/genral/wincounter.tsv', 'tabjolt.wincounter', '\t'),
        ('/ebs/pradeep/tabjolt/genral/summary_line.csv', 'tabjolt.summary_line', ','),
        ('/ebs/pradeep/tabjolt/genral/thread_details.csv', 'tabjolt.thread_details', '\t'),
        ('/ebs/pradeep/tabjolt/genral/modified_workbook.csv', 'tabjolt.performance_samples', ',')
    ]

    for file_path, table_name, delimiter in files_to_load:
        if os.path.exists(file_path):
            load_file_to_vertica(file_path, table_name, delimiter, skip_header=False, conn_info=vertica_config)
        else:
            print(f"File not found: {file_path}")

    queries_with_messages = [
        ("SELECT summary_value FROM tabjolt.summary_line WHERE summary_timestamp = CURRENT_DATE AND summary_metrix = 'Avg';", "Average time taken for tabjolt run (values are in ms):"),
        ("SELECT summary_value FROM tabjolt.summary_line WHERE summary_timestamp = CURRENT_DATE AND summary_metrix = 'Max';", "Maximum time taken for tabjolt run (values are in ms):"),
        ("SELECT summary_value FROM tabjolt.summary_line WHERE summary_timestamp = CURRENT_DATE AND summary_metrix = 'Min';", "Minimum time taken for tabjolt run (values are in ms):"),
        ("SELECT max(summary_timestamp) from tabjolt.wincounter;", "Tabjolt test cases executed at "),
        ("SELECT CAST(AVG(summary_value) AS INTEGER) AS average_summary_value FROM tabjolt.summary_line WHERE summary_metrix = 'Avg';", "Average Historic time taken for tabjolt run (values are in ms):")
    ]

    performance_samples_query = (
    "SELECT CAST(elapsed_time_ms AS INTEGER) AS elapsed_time,latency_time_ms,success_indicator,request_label,response_message FROM tabjolt.performance_samples WHERE REGEXP_LIKE(timestamp_ms, '^[0-9]+$') AND TO_TIMESTAMP(CAST(timestamp_ms AS BIGINT) / 1000) >= CURRENT_DATE AND response_message ILIKE '%site%' AND response_message NOT ILIKE '%null%' ORDER BY elapsed_time DESC;")

    performance_samples_avg = ("SELECT avg_elapsed_ms, current_elapsed_ms, response_message, CASE WHEN avg_elapsed_ms = 0 THEN NULL ELSE ((current_elapsed_ms - avg_elapsed_ms) / avg_elapsed_ms) * 100.0 END AS percentage_difference FROM ( SELECT * FROM (SELECT AVG(elapsed_time_ms::INT) AS avg_elapsed_ms, response_message AS response FROM tabjolt.performance_samples WHERE REGEXP_LIKE(elapsed_time_ms, '^[0-9]+$') AND response_message ILIKE '%site%' AND response_message NOT ILIKE '%null%' GROUP BY response_message ) aa LEFT OUTER JOIN (SELECT elapsed_time_ms::INT AS current_elapsed_ms, response_message FROM tabjolt.performance_samples WHERE REGEXP_LIKE(timestamp_ms, '^[0-9]+$') AND REGEXP_LIKE(elapsed_time_ms, '^[0-9]+$') AND TO_TIMESTAMP(CAST(timestamp_ms AS BIGINT) / 1000) >= CURRENT_DATE AND response_message ILIKE '%site%' AND response_message NOT ILIKE '%null%' ) bb ON aa.response = bb.response_message ) ll WHERE avg_elapsed_ms < current_elapsed_ms ORDER BY percentage_difference DESC;")

    performance_less_avg=("SELECT avg_elapsed_ms, current_elapsed_ms, response_message, percentage_difference FROM (SELECT avg_elapsed_ms, current_elapsed_ms, response_message, CASE WHEN avg_elapsed_ms = 0 THEN NULL ELSE ((current_elapsed_ms - avg_elapsed_ms) / avg_elapsed_ms) * 100.0 END AS percentage_difference FROM (SELECT * FROM (SELECT AVG(elapsed_time_ms::INT) AS avg_elapsed_ms, response_message AS response FROM tabjolt.performance_samples WHERE REGEXP_LIKE(elapsed_time_ms, '^[0-9]+$') AND response_message ILIKE '%site%' AND response_message NOT ILIKE '%null%' GROUP BY response_message) aa LEFT OUTER JOIN (SELECT elapsed_time_ms::INT AS current_elapsed_ms, response_message FROM tabjolt.performance_samples WHERE REGEXP_LIKE(timestamp_ms, '^[0-9]+$') AND REGEXP_LIKE(elapsed_time_ms, '^[0-9]+$') AND TO_TIMESTAMP(CAST(timestamp_ms AS BIGINT) / 1000) >= CURRENT_DATE - interval '3 days' AND response_message ILIKE '%site%' AND response_message NOT ILIKE '%null%') bb ON aa.response = bb.response_message) ll WHERE avg_elapsed_ms > current_elapsed_ms ORDER BY percentage_difference DESC) fin WHERE percentage_difference < -40.0;")

    query_results = execute_queries_with_messages(queries_with_messages, vertica_config)

    graph_path = create_average_time_graph(vertica_config)

    if query_results and graph_path:
        send_email_with_graph("Tabjolt Daily Run Summary for site genral on gbprodwb.glassbeam.com", query_results, graph_path, performance_samples_query, performance_samples_avg,performance_less_avg,vertica_config, smtp_config)







