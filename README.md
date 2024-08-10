# Tableau-Dashboard-Performance-ETL-Automation

### Overview
This project automates the ETL (Extract, Transform, Load) process for performance testing of Tableau dashboards using TabJolt. The project ensures efficient data logging, transformation, storage, and performance monitoring, providing continuous insights and alerts for any performance deviations.

### Features
Automated Performance Testing (Extract): Retrieves all views from a Tableau site and runs performance tests using TabJolt.
Data Transformation (Transform): Extracts performance logs, transforms them into the required CSV format, and stores the files in an S3 bucket.
Automated Data Loading and Reporting (Load): Loads the transformed data into a Vertica database and sends daily performance trend reports via email.
Performance Alerts: Automatically flags and sends red alerts if any dashboard view takes more than 20% of the average performance time.

### Prerequisites
Python 3.x
TabJolt: For running performance tests on Tableau views.
AWS CLI: For interacting with S3 buckets.
Vertica Database: For storing and querying performance data.
Matplotlib: For generating performance trend graphs.
SMTP: For sending email reports.
