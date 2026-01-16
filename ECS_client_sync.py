import requests
import json

# --- CONFIG ---
JIRA_BASE_URL = "https://chghealthcare.atlassian.net"  # adjust if different
JIRA_EMAIL = "jamie.gordon@chghealtcare.com"
JIRA_API_TOKEN = "ATATT3xFfGF0efSLl59JqokaZnxSvOacQUoXQjyAt8SqkO4QpUYZF7Aapg6i98U_2frq3XnVA7ITTixGjArdgatKTFZqFj3MVGuVg8NTbs58wru22zSyTJNFtr10CKkhG330CsGRhGudu6AtxLe5Gjp6dqmaxo6h3nXLwByTMaF9RFHiSI2_biU=CF87B06E"
JIRA_FIELD_ID = "customfield_20690"
JIRA_CONTEXT_ID = "22636"

SMARTSHEET_BASE_URL = "https://api.smartsheet.com/2.0"
SMARTSHEET_TOKEN = "cc2vFfElPjLmK7h5aM2zoYR8A7oNsCg38I4KCt"
SMARTSHEET_SHEET_ID = "V2fFqggWHcXhqqHwvmQxVQ539vMxWP7pqfM539w1"
CLIENT_COLUMN_ID = 2012512791095172  # column ID for Client Name

jira_auth = (JIRA_EMAIL, JIRA_API_TOKEN)
jira_headers = {
    "Accept": "application/json",
    "Content-Type": "application/json"
}

smartsheet_headers = {
    "Authorization": f"Bearer {SMARTSHEET_TOKEN}",
    "Accept": "application/json"
}

# --- 1. Get Clients from Smartsheet ---
sheet_url = f"{SMARTSHEET_BASE_URL}/sheets/{SMARTSHEET_SHEET_ID}"
sheet_resp = requests.get(sheet_url, headers=smartsheet_headers)
sheet_resp.raise_for_status()
sheet = sheet_resp.json()

smartsheet_clients = set()
for row in sheet["rows"]:
    for cell in row["cells"]:
        if cell.get("columnId") == CLIENT_COLUMN_ID and "value" in cell:
            name = str(cell["value"]).strip()
            if name:
                smartsheet_clients.add(name)

# --- 2. Get existing Jira options (with pagination) ---
options_url = f"{JIRA_BASE_URL}/rest/api/3/field/{JIRA_FIELD_ID}/context/{JIRA_CONTEXT_ID}/option"

jira_options = {}
start_at = 0
max_results = 100

while True:
    params = {"startAt": start_at, "maxResults": max_results}
    resp = requests.get(options_url, headers=jira_headers, auth=jira_auth, params=params)
    resp.raise_for_status()
    data = resp.json()
    for opt in data.get("values", []):
        jira_options[opt["value"]] = opt

    if data.get("isLast", True):
        break
    start_at += max_results

# --- 3. Compute differences ---
to_add = [name for name in smartsheet_clients if name not in jira_options]
to_disable = [
    opt for (val, opt) in jira_options.items()
    if val not in smartsheet_clients and not opt["disabled"]
]

# --- 4. Add missing options ---
if to_add:
    payload = {
        "options": [{"value": name, "disabled": False} for name in to_add]
    }
    resp = requests.post(options_url, headers=jira_headers, auth=jira_auth,
                         data=json.dumps(payload))
    resp.raise_for_status()
    print(f"Added {len(to_add)} options.")

# --- 5. Disable stale options (optional) ---
if to_disable:
    # Can chunk if many
    chunk_size = 50
    for i in range(0, len(to_disable), chunk_size):
        chunk = to_disable[i:i+chunk_size]
        payload = {
            "options": [
                {
                    "id": opt["id"],
                    "value": opt["value"],
                    "disabled": True
                } for opt in chunk
            ]
        }
        resp = requests.put(options_url, headers=jira_headers, auth=jira_auth,
                            data=json.dumps(payload))
        resp.raise_for_status()
        print(f"Disabled {len(chunk)} options.")

print("Sync complete.")