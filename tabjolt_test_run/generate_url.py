import requests
import xml.etree.ElementTree as ET

# Replace these variables with your Tableau Server details and credentials
SERVER_URL = "https://gbprodwb.glassbeam.com"
API_VERSION = "3.10"
USERNAME = "administrator"
PASSWORD = "gla55beam"
SITE_NAME = "nypnypprod"

# Common headers
headers = {
    "Accept": "application/xml"
}

# Authenticate and get the authentication token
def authenticate():
    url = f"{SERVER_URL}/api/{API_VERSION}/auth/signin"
    payload = {
        "credentials": {
            "name": USERNAME,
            "password": PASSWORD,
            "site": {"contentUrl": SITE_NAME}
        }
    }
    response = requests.post(url, json=payload, headers=headers)
    
    if response.status_code != 200:
        print(f"Failed to authenticate. Status code: {response.status_code}")
        print(f"Response text: {response.text}")
        response.raise_for_status()
    
    try:
        root = ET.fromstring(response.text)
    except ET.ParseError as e:
        print(f"Failed to parse XML: {e}")
        print(f"Response text: {response.text}")
        raise

    auth_token = root.find('.//{http://tableau.com/api}credentials').get('token')
    site_id = root.find('.//{http://tableau.com/api}site').get('id')
    return auth_token, site_id

# Get all workbooks for the site
def get_workbooks(auth_token, site_id):
    url = f"{SERVER_URL}/api/{API_VERSION}/sites/{site_id}/workbooks"
    auth_headers = headers.copy()
    auth_headers["X-Tableau-Auth"] = auth_token
    response = requests.get(url, headers=auth_headers)
    
    if response.status_code != 200:
        print(f"Failed to get workbooks. Status code: {response.status_code}")
        print(f"Response text: {response.text}")
        response.raise_for_status()
    
    try:
        root = ET.fromstring(response.text)
    except ET.ParseError as e:
        print(f"Failed to parse XML: {e}")
        print(f"Response text: {response.text}")
        raise

    workbooks = root.findall('.//{http://tableau.com/api}workbook')
    return workbooks

# Get all views for each workbook
def get_views(auth_token, site_id, workbook_id):
    url = f"{SERVER_URL}/api/{API_VERSION}/sites/{site_id}/workbooks/{workbook_id}/views"
    auth_headers = headers.copy()
    auth_headers["X-Tableau-Auth"] = auth_token
    response = requests.get(url, headers=auth_headers)
    
    if response.status_code != 200:
        print(f"Failed to get views for workbook {workbook_id}. Status code: {response.status_code}")
        print(f"Response text: {response.text}")
        response.raise_for_status()
    
    try:
        root = ET.fromstring(response.text)
    except ET.ParseError as e:
        print(f"Failed to parse XML: {e}")
        print(f"Response text: {response.text}")
        raise

    views = root.findall('.//{http://tableau.com/api}view')
    return views

# Main function to get all views and their URLs from the site
def get_all_view_urls_from_site():
    auth_token, site_id = authenticate()
    workbooks = get_workbooks(auth_token, site_id)
    all_view_urls = []
    for workbook in workbooks:
        workbook_id = workbook.get('id')
        views = get_views(auth_token, site_id, workbook_id)
        for view in views:
            view_url = f"{SERVER_URL}/t/{SITE_NAME}/views/{view.get('contentUrl')}"
            all_view_urls.append(view_url)
    return all_view_urls

# Run the script
if __name__ == "__main__":
    try:
        view_urls = get_all_view_urls_from_site()
        for url in view_urls:
            print(url)
    except requests.exceptions.RequestException as e:
        print(f"Request failed: {e}")
