# Project-503 : Blog Page Application (Django) deployed on Azure App Service with Auto Scaling, Blob Storage, Azure Database for MySQL, VNet Components, Table Storage and Azure CDN with Traffic Manager (AZURE STUDENT SOLUTION)

## Description

The Blog Page Application aims to deploy a Django web application on Microsoft Azure Cloud Infrastructure. This infrastructure uses Azure App Service with built-in Auto Scaling and Load Balancing, Azure Database for MySQL Flexible Server (equivalent of RDS), all inside a custom Virtual Network (VNet). Azure CDN and Azure Traffic Manager services are placed in front of the architecture and manage traffic securely. Users are able to upload pictures on their blog pages and these are kept in Azure Blob Storage (equivalent of S3). Event logging is handled by Azure Functions (equivalent of Lambda) writing to Azure Table Storage (equivalent of DynamoDB). This architecture will be created by the DevOps team.

## AWS → Azure Service Mapping

| AWS Service | Azure Equivalent |
|---|---|
| VPC | Azure Virtual Network (VNet) |
| Public / Private Subnet | VNet Subnet |
| Internet Gateway | Built into VNet (automatic) |
| NAT Instance | Azure NAT Gateway |
| VPC Endpoint (S3) | Service Endpoint (Blob Storage) |
| Security Group | Network Security Group (NSG) |
| EC2 + Auto Scaling Group | Azure App Service + Auto Scale |
| Application Load Balancer | App Service built-in Load Balancer |
| IAM Role | Managed Identity |
| ACM Certificate | App Service Managed Certificate |
| RDS MySQL | Azure Database for MySQL Flexible Server |
| S3 Bucket | Azure Blob Storage (Container) |
| CloudFront | Azure CDN |
| Route 53 + Health Check + Failover | Azure Traffic Manager (Priority routing) |
| S3 Static Website | Azure Blob Static Website |
| DynamoDB | Azure Table Storage |
| Lambda | Azure Functions |
| S3 Event Trigger | Azure Function Blob Trigger |

---

## Steps to Solution

### Step 1: Create Resource Group

A Resource Group is a logical container for all Azure resources (similar to an AWS CloudFormation stack boundary).

- Go to [portal.azure.com](https://portal.azure.com)
- Search for **Resource Groups** → click **+ Create**

```text
Subscription    : Azure for Students
Resource group  : azure-capstone-RG
Region          : East US
click Review + Create → Create
```

---

### Step 2: Create VNet and All Components

#### VNet

- Search for **Virtual Networks** → **+ Create**

```text
Resource group  : azure-capstone-RG
Name            : azure-capstone-VNet
Region          : East US
click Next: IP Addresses
```

- On the **IP Addresses** tab:

```text
IPv4 address space : 10.10.0.0/16
Delete the default subnet if one was auto-created
```

#### Subnets

Add the following 4 subnets one by one by clicking **+ Add subnet**:

```text
Subnet 1 (Public - Zone 1):
    Name            : azure-capstone-public-subnet-1
    Subnet range    : 10.10.10.0/24

Subnet 2 (Private - Zone 1):
    Name            : azure-capstone-private-subnet-1
    Subnet range    : 10.10.11.0/24

Subnet 3 (Public - Zone 2):
    Name            : azure-capstone-public-subnet-2
    Subnet range    : 10.10.20.0/24

Subnet 4 (Private - Zone 2):
    Name            : azure-capstone-private-subnet-2
    Subnet range    : 10.10.21.0/24
```

- Click **Review + Create** → **Create**

#### Public IP for NAT Gateway

- Search for **Public IP addresses** → **+ Create**

```text
Resource group          : azure-capstone-RG
Name                    : azure-capstone-NAT-PIP
Region                  : East US
SKU                     : Standard
Assignment              : Static
Availability zone       : Zone-redundant
click Review + Create → Create
```

#### NAT Gateway (equivalent of NAT Instance)

A NAT Gateway allows resources in private subnets to access the internet (for pulling packages, GitHub, etc.).

- Search for **NAT gateways** → **+ Create**

```text
Resource group          : azure-capstone-RG
Name                    : azure-capstone-NAT-Gateway
Region                  : East US
Availability zone       : No zone

Outbound IP tab:
    Public IP addresses : azure-capstone-NAT-PIP

Subnet tab:
    Virtual network     : azure-capstone-VNet
    Subnet name         : azure-capstone-private-subnet-1
                          azure-capstone-private-subnet-2
                          (add both private subnets)

click Review + Create → Create
```

#### Service Endpoint for Blob Storage (equivalent of VPC Endpoint for S3)

- Go to **Virtual Networks** → **azure-capstone-VNet** → **Subnets**
- Click **azure-capstone-private-subnet-1** → under **Service endpoints** → **+ Add**

```text
Service     : Microsoft.Storage
Subnets     : azure-capstone-private-subnet-1
click Add
```

- Repeat the same for **azure-capstone-private-subnet-2**

---

### Step 3: Create Network Security Groups (NSG)

NSGs are equivalent to AWS Security Groups. We need two NSGs.

#### 1. App Service Integration NSG

- Search for **Network security groups** → **+ Create**

```text
Resource group  : azure-capstone-RG
Name            : azure-capstone-AppService-NSG
Region          : East US
click Review + Create → Create
```

After creation, go to **azure-capstone-AppService-NSG** → **Inbound security rules** → **+ Add**:

```text
Rule 1:
    Source                  : Any
    Source port ranges      : *
    Destination             : Any
    Destination port ranges : 80
    Protocol                : TCP
    Action                  : Allow
    Priority                : 100
    Name                    : Allow-HTTP

Rule 2:
    Source                  : Any
    Source port ranges      : *
    Destination             : Any
    Destination port ranges : 443
    Protocol                : TCP
    Action                  : Allow
    Priority                : 110
    Name                    : Allow-HTTPS
```

Outbound rules → **+ Add**:

```text
Rule 1:
    Source                  : Any
    Source port ranges      : *
    Destination             : Any
    Destination port ranges : 3306
    Protocol                : TCP
    Action                  : Allow
    Priority                : 100
    Name                    : Allow-MySQL-Outbound
```

#### 2. MySQL NSG (equivalent of RDS Security Group)

- Search for **Network security groups** → **+ Create**

```text
Resource group  : azure-capstone-RG
Name            : azure-capstone-MySQL-NSG
Region          : East US
click Review + Create → Create
```

After creation → **Inbound security rules** → **+ Add**:

```text
Rule 1:
    Source                  : Service Tag
    Source service tag      : AppService  ← This allows only App Service traffic
    Source port ranges      : *
    Destination             : Any
    Destination port ranges : 3306
    Protocol                : TCP
    Action                  : Allow
    Priority                : 100
    Name                    : Allow-MySQL-from-AppService
```

---

### Step 4: Create Azure Database for MySQL Flexible Server

This is the equivalent of AWS RDS MySQL.

First create a subnet delegation for MySQL:

- Go to **Virtual Networks** → **azure-capstone-VNet** → **Subnets** → click **azure-capstone-private-subnet-1**

```text
Under "Delegate subnet to a service":
    Delegation  : Microsoft.DBforMySQL/flexibleServers
click Save
```

Now create the database:

- Search for **Azure Database for MySQL flexible servers** → **+ Create** → **Flexible server**

```text
Resource group          : azure-capstone-RG
Server name             : azure-capstone-mysql   ← must be globally unique
Region                  : East US
MySQL version           : 8.0
Workload type           : For development or hobby projects
Availability zone       : 1

Authentication:
    Admin username      : admin
    Password            : REMOVED-PASSWORD

Compute + Storage:
    Compute tier        : Burstable
    Compute size        : Standard_B1ms (1 vCore, 2 GB RAM) ← cheapest option
    Storage             : 20 GB
    Enable Storage Auto Growth : Yes (up to 40 GB)
```

- Click **Next: Networking**

```text
Connectivity method     : Private access (VNet Integration)
Virtual network         : azure-capstone-VNet
Subnet                  : azure-capstone-private-subnet-1
Private DNS zone        : (auto-created) azure-capstone-mysql.private.mysql.database.azure.com
```

- Click **Next: Security** → keep defaults
- Click **Next: Additional** 

```text
Initial database name   : database1
Backup retention period : 7 days
Backup window           : 03:00 (UTC), Duration: 1 hour
Geo-redundant backup    : Disabled (student plan)
```

- Click **Review + Create** → **Create** (takes 3–5 minutes)

> **Note your MySQL host:** `azure-capstone-mysql.mysql.database.azure.com`  
> You will need this in Step 9.

---

### Step 5: Create Azure Blob Storage and Static Website

This is the equivalent of the two AWS S3 buckets.

#### 5a. Create Storage Account

- Search for **Storage accounts** → **+ Create**

```text
Resource group          : azure-capstone-RG
Storage account name    : azurecapstoneblob<yourname>  ← globally unique, lowercase, no hyphens
Region                  : East US
Performance             : Standard
Redundancy              : LRS (Locally-redundant storage)  ← cheapest option for student

Advanced tab:
    Allow Blob anonymous access : Enabled

Networking tab:
    Network access              : Enable public access from selected virtual networks and IP addresses
    Virtual network             : azure-capstone-VNet
    Subnets                     : azure-capstone-private-subnet-1
                                  azure-capstone-private-subnet-2
    (Add both private subnets as exceptions so App Service can access storage)
    
    Also add your current IP address to allow portal access

click Review + Create → Create
```

#### 5b. Create Blob Containers (equivalent of S3 Bucket objects/folders)

After the storage account is created, go to **Data storage** → **Containers** → **+ Container**:

```text
Container 1:
    Name                : static
    Public access level : Blob (anonymous read access for blobs only)
    click Create

Container 2:
    Name                : media
    Public access level : Blob (anonymous read access for blobs only)
    click Create
```

#### 5c. Create Static Website for Failover (equivalent of S3 Static Website)

- Go to **Data management** → **Static website** → set to **Enabled**

```text
Index document name     : index.html
Error document path     : index.html
click Save
```

- Note the **Primary endpoint** URL that appears (e.g., `https://azurecapstoneblob<yourname>.z13.web.core.windows.net`). You will need this in Step 15.

- Now go to **Containers** → select the **$web** container → **Upload**
  - Upload `index.html` and `sorry.jpg` from the `S3_Static_Website/` folder in the project

#### 5d. Get Storage Account Key

- Go to **Security + networking** → **Access keys** → **key1** → click **Show** next to **Key** and **Connection string**
- Copy and save the **Key** and **Connection string** — you will need these in Step 9.

---

### Step 6: Copy Files from Project Repository

```text
Copy all project files (src/, requirements.txt, startup.sh, azure_function/, etc.)
into your working directory or clone the repository directly.

For the Azure deployment, use the files from the azure/ folder:
    azure/src/cblog/settings.py   → replaces src/cblog/settings.py
    azure/src/cblog/storages.py   → replaces src/cblog/storages.py
    azure/requirements.txt        → replaces requirements.txt
    azure/startup.sh              → add to repo root
```

---

### Step 7: Prepare Your GitHub Repository

- Create a **private** repository on your GitHub account and clone it locally.
- Copy all project files (including the modified Azure files from Step 6) into this repository.
- Commit and push to your private GitHub repository.

```bash
git init
git add .
git commit -m "Initial Azure capstone deployment"
git remote add origin https://github.com/<YOUR_USERNAME>/<YOUR_REPO_NAME>.git
git push -u origin main
```

---

### Step 8: Prepare startup.sh (equivalent of EC2 userdata.sh)

This file replaces the EC2 Launch Template userdata script. Azure App Service runs this script on startup.

```bash
#!/bin/bash
# Azure App Service startup script

pip install -r /home/site/wwwroot/requirements.txt

cd /home/site/wwwroot/src

python3 manage.py collectstatic --noinput
python3 manage.py makemigrations
python3 manage.py migrate

gunicorn --bind=0.0.0.0:8000 --timeout=600 --workers=2 cblog.wsgi:application
```

Save this file as `startup.sh` in the root of your repository and push it to GitHub.

---

### Step 9: Write MySQL Endpoint and Blob Storage Credentials into Settings File

Please follow and apply the instructions below (equivalent of developer_notes.txt).

```text
- Picture and media files are kept in Azure Blob Storage named azurecapstoneblob<yourname> as objects.
  You must fill in the following variables in "src/cblog/settings.py" (the Azure version):
    a. AZURE_ACCOUNT_NAME   → your storage account name (e.g. azurecapstoneblob<yourname>)
    b. AZURE_ACCOUNT_KEY    → copied from Step 5d (Access keys → key1 → Key)
    
- Users credentials and blog contents are kept in Azure Database for MySQL Flexible Server.
  To connect App Service to MySQL, fill in the following variables in "src/cblog/settings.py":
    a. DB_NAME     → database1
    b. DB_USER     → admin
    c. DB_HOST     → azure-capstone-mysql.mysql.database.azure.com
    d. DB_PORT     → 3306
    e. DB_PASSWORD → must be written in "src/.env" file (do NOT put it in settings.py)
```

Open `src/cblog/settings.py` (the Azure version from `azure/src/cblog/settings.py`) and fill in:

```python
# Azure Blob Storage — fill these values
AZURE_ACCOUNT_NAME = 'azurecapstoneblob<yourname>'  # ← your storage account name
AZURE_ACCOUNT_KEY  = '<your-account-key-from-step-5d>'  # ← paste key here

# Database — fill these values
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.mysql',
        'NAME': 'database1',
        'USER': 'admin',
        'PASSWORD': config('PASSWORD'),     # ← comes from .env file
        'HOST': 'azure-capstone-mysql.mysql.database.azure.com',  # ← your MySQL host
        'PORT': '3306',
        'OPTIONS': {
            'ssl': {'ssl-ca': '/etc/ssl/certs/DigiCertGlobalRootCA.crt.pem'},
        },
    }
}
```

Create the `src/.env` file:

```text
SECRET_KEY=<run: python -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())">
DB_PASSWORD=<YOUR-DB-PASSWORD>
DB_HOST=<your-mysql-server>.mysql.database.azure.com
DB_NAME=lerniablog
DB_USER=adminuser
AZURE_APP_HOSTNAME=<your-app>.azurewebsites.net
AZURE_STORAGE_ACCOUNT_NAME=<your-storage-account>
AZURE_STORAGE_ACCOUNT_KEY=<your-storage-key>
```

Also update `ALLOWED_HOSTS` in `src/cblog/settings.py` — add your App Service hostname:

```python
ALLOWED_HOSTS = ['azure-capstone-app.azurewebsites.net', 'www.<YOUR DNS NAME>']
```

Commit and push all changes to your private GitHub repository.

---

### Step 10: Create Managed Identity (equivalent of IAM Role for EC2)

Before creating the App Service, create a Managed Identity so the App Service can securely access Blob Storage.

- Search for **Managed Identities** → **+ Create**

```text
Resource group  : azure-capstone-RG
Region          : East US
Name            : azure-capstone-identity
click Review + Create → Create
```

After creation, assign the **Storage Blob Data Contributor** role:

- Go to your storage account **azurecapstoneblob<yourname>** → **Access Control (IAM)** → **+ Add** → **Add role assignment**

```text
Role        : Storage Blob Data Contributor
Members tab : + Select members → search for "azure-capstone-identity" → Select
click Review + assign
```

---

### Step 11: Create App Service Plan and Web App (equivalent of Launch Template + ALB + ASG)

#### 11a. Create App Service Plan

- Search for **App Service plans** → **+ Create**

```text
Resource group      : azure-capstone-RG
Name                : azure-capstone-plan
Operating System    : Linux
Region              : East US
Pricing tier        : B1 (1 core, 1.75 GB RAM) ← Student plan: ~$13/month
                      (click "Explore pricing plans" → "Basic" → B1)
click Review + Create → Create
```

#### 11b. Create Web App

- Search for **App Services** → **+ Create** → **Web App**

```text
Resource group      : azure-capstone-RG
Name                : azure-capstone-app  ← must be globally unique
Publish             : Code
Runtime stack       : Python 3.8
Operating System    : Linux
Region              : East US
App Service Plan    : azure-capstone-plan

click Next: Deployment

GitHub Actions settings:
    Continuous deployment   : Enable
    GitHub account          : (authorize with your GitHub account)
    Organization            : <your github username>
    Repository              : <your private repo name>
    Branch                  : main

click Review + Create → Create
```

> Azure automatically creates a GitHub Actions workflow file in your repository that builds and deploys on every push.

#### 11c. Configure VNet Integration (private access to MySQL)

After the Web App is created:

- Go to **azure-capstone-app** → **Settings** → **Networking** → **VNet Integration** → **+ Add VNet**

```text
Virtual Network : azure-capstone-VNet
Subnet          : azure-capstone-private-subnet-2  ← use a dedicated subnet for App Service
click Connect
```

> The App Service can now reach resources (MySQL) in the private VNet.

#### 11d. Assign Managed Identity to App Service

- Go to **azure-capstone-app** → **Settings** → **Identity** → **User assigned** tab → **+ Add**

```text
Select: azure-capstone-identity
click Add
```

#### 11e. Set Environment Variables (Application Settings)

- Go to **azure-capstone-app** → **Settings** → **Configuration** → **Application settings** → **+ New application setting**

Add each variable:

```text
SECRET_KEY          : <your-django-secret-key>
DB_PASSWORD         : <YOUR-DB-PASSWORD>
DB_NAME             : lerniablog
DB_USER             : adminuser
DB_HOST             : <your-mysql-server>.mysql.database.azure.com
DB_PORT             : 3306
AZURE_STORAGE_ACCOUNT_NAME : azurecapstoneblob<yourname>
AZURE_STORAGE_ACCOUNT_KEY  : <your-account-key-from-step-5d>
AZURE_APP_HOSTNAME  : azure-capstone-app.azurewebsites.net
```

Click **Save** → **Continue**

#### 11f. Set Startup Command

- Go to **Settings** → **Configuration** → **General settings**

```text
Startup Command : bash /home/site/wwwroot/startup.sh
click Save
```

#### 11g. Verify Deployment

- Go to **azure-capstone-app** → **Deployment** → **Deployment Center** → check that deployment is successful (green checkmark)
- Open `https://azure-capstone-app.azurewebsites.net` — the blog homepage should appear
- Check logs: **Monitoring** → **Log stream** to see startup logs

---

### Step 12: Configure Auto Scale for App Service (equivalent of Auto Scaling Group)

- Go to **azure-capstone-plan** → **Settings** → **Scale out (App Service plan)**

```text
Choose: Custom autoscale
Autoscale setting name  : azure-capstone-autoscale
Resource group          : azure-capstone-RG

Default scale condition:
    Scale mode              : Scale based on a metric
    Minimum instance count  : 2
    Maximum instance count  : 4
    Default instance count  : 2

Add a rule (Scale out):
    Metric source           : Current resource (azure-capstone-plan)
    Metric name             : CPU Percentage
    Operator                : Greater than
    Threshold               : 70
    Duration (minutes)      : 5
    Action                  : Increase count by 1
    Cool down (minutes)     : 5

Add a rule (Scale in):
    Metric source           : Current resource (azure-capstone-plan)
    Metric name             : CPU Percentage
    Operator                : Less than
    Threshold               : 30
    Duration (minutes)      : 5
    Action                  : Decrease count by 1
    Cool down (minutes)     : 5

click Save
```

---

### Step 13: Create SSL Certificate (equivalent of ACM Certificate)

Azure App Service provides free managed SSL certificates.

- Go to **azure-capstone-app** → **Settings** → **TLS/SSL settings** → **Private Key Certificates (.pfx)** → **+ Create App Service Managed Certificate**

```text
Select the custom domain you want to secure (after DNS is configured in Step 15).
If you don't have a custom domain yet, App Service provides HTTPS by default
on *.azurewebsites.net — no certificate creation needed for that.
```

For custom domain HTTPS:

```text
Domain          : www.<YOUR DNS NAME>
click Create
```

After creation:

- Go to **TLS/SSL bindings** → **+ Add TLS/SSL binding**

```text
Custom domain       : www.<YOUR DNS NAME>
Private certificate : (select the managed certificate just created)
TLS/SSL type        : SNI SSL
click Add Binding
```

---

### Step 14: Create Azure CDN (equivalent of CloudFront)

- Search for **CDN profiles** → **+ Create**

```text
Resource group  : azure-capstone-RG
Name            : azure-capstone-cdn
Pricing tier    : Standard Microsoft
click Review + Create → Create
```

After CDN profile is created → **+ Endpoint**:

```text
Name                : azure-capstone-endpoint
Origin type         : Web App
Origin hostname     : azure-capstone-app.azurewebsites.net
Protocol            : HTTPS only
click Add
```

Configure caching rules:

- Go to **azure-capstone-endpoint** → **Rules engine** → **+ Add rule**

```text
Rule name           : ForwardAll
Match condition     : (none — apply to all requests)
Action              : Cache override → Bypass cache

Rule name           : RedirectHTTP
If                  : Request protocol equals HTTP
Action              : URL redirect → HTTPS, 301 Permanent
```

Configure custom domain on CDN:

- Go to **azure-capstone-endpoint** → **+ Custom domain**

```text
Custom hostname     : www.<YOUR DNS NAME>
```

Enable HTTPS on custom domain:

```text
Custom domain HTTPS : On
Certificate management type : CDN managed
Minimum TLS version : TLS 1.2
```

---

### Step 15: Create Azure Traffic Manager and DNS Zone (equivalent of Route 53 + Failover)

#### 15a. Create Azure DNS Zone

- Search for **DNS zones** → **+ Create**

```text
Resource group  : azure-capstone-RG
Name            : <YOUR DNS NAME>  (e.g. clarusway.us)
click Review + Create → Create
```

After creation, note the **4 Name Servers** listed. Go to your domain registrar and update the nameservers to these Azure nameservers.

#### 15b. Create Traffic Manager Profile (equivalent of Route 53 Failover record)

- Search for **Traffic Manager profiles** → **+ Create**

```text
Name            : azure-capstone-traffic
Routing method  : Priority  ← This is the failover equivalent
Resource group  : azure-capstone-RG
click Create
```

After creation → **Settings** → **Configuration**:

```text
DNS time to live (TTL)  : 300
Protocol                : HTTPS
Port                    : 443
Path                    : /
Probing interval        : 30 seconds
Tolerated failures      : 3
Probe timeout           : 10 seconds
click Save
```

#### 15c. Add Endpoints to Traffic Manager

Go to **Settings** → **Endpoints** → **+ Add**

**Primary Endpoint (CDN — Priority 1):**

```text
Type                    : External endpoint
Name                    : primary-cdn-endpoint
Fully-qualified domain name (FQDN) : azure-capstone-endpoint.azureedge.net
Priority                : 1
click Add
```

**Secondary Endpoint (Blob Static Website — Failover, Priority 2):**

```text
Type                    : External endpoint
Name                    : failover-static-website
Fully-qualified domain name (FQDN) : azurecapstoneblob<yourname>.z13.web.core.windows.net
                                     ← Use the Static Website Primary Endpoint from Step 5c
Priority                : 2
click Add
```

#### 15d. Create DNS Records

Go to **DNS zone** for `<YOUR DNS NAME>` → **+ Record set**:

**CNAME record for www subdomain → Traffic Manager:**

```text
Name        : www
Type        : CNAME
TTL         : 300
Alias       : azure-capstone-traffic.trafficmanager.net
click OK
```

**Verify:**  
After DNS propagation (~5 minutes), open `https://www.<YOUR DNS NAME>` — it should route to the blog via CDN → App Service.

To test failover: Stop the App Service → wait 90 seconds → `https://www.<YOUR DNS NAME>` should show the static failover page from Blob Storage.

---

### Step 16: Create Azure Table Storage (equivalent of DynamoDB)

Azure Table Storage is included in the Storage Account created in Step 5. No separate service creation is needed.

Create the table:

- Go to **azurecapstoneblob<yourname>** storage account → **Data storage** → **Tables** → **+ Table**

```text
Table name  : azurecapstoneDynamo
click OK
```

> This table is equivalent to the DynamoDB table `awscapstoneDynamo`.  
> It will store blob event logs written by the Azure Function.  
> Primary key structure:
> - PartitionKey = "blob" (equivalent of DynamoDB partition key)
> - RowKey = filename (equivalent of DynamoDB `id` attribute)
> - Additional columns: Timestamp, Event, FullPath, SizeBytes

---

### Step 17–18: Create Azure Function and Blob Trigger (equivalent of Lambda + S3 Event)

#### Step 17: Create Azure Function App

Before creating the Function App, create a storage account for the function's internal use (or reuse the existing one):

- Search for **Function App** → **+ Create**

```text
Resource group      : azure-capstone-RG
Function App name   : azure-capstone-lambda  ← globally unique name
Publish             : Code
Runtime stack       : Python
Version             : 3.8
Region              : East US
Operating System    : Linux
Hosting plan        : Consumption (Serverless)  ← equivalent of Lambda pay-per-use, very cheap

Storage:
    Storage account : azurecapstoneblob<yourname>  ← use our existing storage account

Monitoring:
    Enable Application Insights : Yes
    Application Insights        : (auto-created)

click Review + Create → Create
```

#### Step 17–18: Create Function with Blob Trigger (equivalent of S3 Event trigger for Lambda)

Go to the Function App **azure-capstone-lambda** → **Functions** → **+ Create**

```text
Development environment : Develop in portal
Template                : Azure Blob Storage trigger
New Function name       : BlobTriggerFunction
Path                    : media/{name}   ← triggers when a file is uploaded to the 'media' container
                                            (equivalent of S3 Prefix: media/)
Storage account connection : AzureWebJobsStorage
click Create
```

#### Set Environment Variables for the Function

Go to **azure-capstone-lambda** → **Settings** → **Configuration** → **Application settings** → **+ New application setting**:

```text
STORAGE_CONNECTION_STRING : <Connection string from Step 5d — Access keys → key1 → Connection string>
```

Click **Save**

#### Write the Azure Function Code (equivalent of lambda_function.py)

Go to **azure-capstone-lambda** → **Functions** → **BlobTriggerFunction** → **Code + Test**

Remove the default code and paste the following:

```python
import azure.functions as func
import logging
import os
from azure.data.tables import TableServiceClient
from datetime import datetime, timezone


def main(myblob: func.InputStream):
    logging.info(f"Blob trigger fired. Name: {myblob.name}, Size: {myblob.length} bytes")

    conn_str = os.environ["STORAGE_CONNECTION_STRING"]
    table_service = TableServiceClient.from_connection_string(conn_str=conn_str)
    table_client = table_service.get_table_client(table_name="azurecapstoneDynamo")

    # Create table if it doesn't exist yet
    try:
        table_client.create_table()
    except Exception:
        pass  # Table already exists

    filename = myblob.name.split("/")[-1]
    timestamp = datetime.now(timezone.utc).isoformat()

    entity = {
        "PartitionKey": "blob",          # equivalent of DynamoDB partition key
        "RowKey": filename,              # equivalent of DynamoDB 'id' primary key
        "Timestamp": timestamp,          # equivalent of DynamoDB 'timestamp'
        "Event": "BlobCreated",          # equivalent of DynamoDB 'Event'
        "FullPath": myblob.name,
        "SizeBytes": myblob.length,
    }

    table_client.upsert_entity(entity=entity)
    logging.info(f"Written to Table Storage: {filename}")
```

Click **Save**

Now go to **azure-capstone-lambda** → **Functions** → **+ Create** a second function for **delete events**:

```text
Template                : Azure Event Grid trigger
New Function name       : BlobDeleteTriggerFunction
click Create
```

> **Note:** Azure Blob Trigger only detects create/update events. To also log delete events (equivalent of AWS `All object delete events` trigger), you use Azure Event Grid. For simplicity in student projects, the Blob Trigger for creates is sufficient. To enable delete event logging, configure an Event Grid subscription on the storage account pointing to this Function App.

Click **Deploy** (or Save) — all is set. Go to the website, add a new blog post with a photo, then check the `azurecapstoneDynamo` table in Table Storage to confirm the record was written.

---

## Verification Checklist

| Test | Expected Result |
|---|---|
| `https://azure-capstone-app.azurewebsites.net/` | Blog homepage loads |
| Register new user | Registration succeeds, profile created |
| Create blog post with image | Image uploaded to `media` container in Blob Storage |
| Check `azurecapstoneDynamo` table | New row appears with RowKey = image filename |
| `https://azure-capstone-endpoint.azureedge.net/` | Blog loads via CDN |
| `https://www.<YOUR DNS NAME>/` | Blog loads via Traffic Manager → CDN |
| Stop App Service → visit `www.<YOUR DNS NAME>` | Failover static page from Blob Storage shows |
| Restart App Service → visit `www.<YOUR DNS NAME>` | Blog homepage returns (within ~2 minutes) |

---

## Cost Estimate (Azure Student Account — $100 Credit)

| Service | Tier | Estimated Monthly Cost |
|---|---|---|
| App Service Plan | B1 (1 core, 1.75 GB) | ~$13.00 |
| Azure Database for MySQL | Flexible Server B1ms | ~$12.00 |
| Azure Blob Storage | LRS, ~5 GB | ~$0.10 |
| Azure Functions | Consumption (first 1M free) | ~$0.00 |
| Azure Table Storage | (included in Storage Account) | ~$0.01 |
| Azure CDN | Standard Microsoft | ~$0.08/GB |
| Traffic Manager | DNS Queries | ~$0.54/1M queries |
| Public IP | Standard Static | ~$3.65 |
| NAT Gateway | | ~$3.24 |
| **Total** | | **~$33/month** |

> With $100 student credit you can run this for approximately **3 months**.  
> Downgrade to **F1 (Free)** App Service plan to reduce to ~$19/month (but F1 has CPU/memory limits and no custom domain HTTPS).

---

## WE ALL SET

Congratulations! You have finished your Azure Capstone Project, which is the full equivalent of the AWS deployment but running entirely on Microsoft Azure.

**Summary of what you built:**
- Custom VNet with public/private subnets across 2 availability zones
- NAT Gateway for private subnet internet access
- Azure Database for MySQL Flexible Server in a private subnet (equivalent of RDS)
- Azure Blob Storage with `static` and `media` containers + failover static website (equivalent of S3)
- Azure App Service with built-in load balancing, auto scale (min 2 / max 4 instances), and VNet Integration (equivalent of EC2 ASG + ALB)
- Managed Identity for secure access to Blob Storage (equivalent of IAM Role)
- Free managed SSL certificate (equivalent of ACM)
- Azure CDN in front of App Service (equivalent of CloudFront)
- Azure Traffic Manager with priority failover to static website (equivalent of Route 53 failover)
- Azure DNS Zone with CNAME record pointing to Traffic Manager
- Azure Table Storage table `azurecapstoneDynamo` (equivalent of DynamoDB)
- Azure Function with Blob Trigger writing events to Table Storage (equivalent of Lambda + S3 Event)
