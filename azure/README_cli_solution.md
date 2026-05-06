# Azure CLI Çözüm Rehberi — Django Blog App

Tüm adımlar **Azure CLI** ile yapılır. Portal adımı yoktur.

---

## Kaynak Adları (Senin Hesabında Oluşturulan)

```bash
RG="lernia-rg"
LOCATION="swedencentral"
VNET="lernia-vnet"
MYSQL_SERVER="lernia-mysql1573458637"
STORAGE="lerniablob869090428"
DB_NAME="lerniablog"
DB_USER="adminuser"
DB_PASSWORD="<YOUR-DB-PASSWORD>"
APP_PLAN="lernia-plan"
APP_NAME="lernia-app"
FUNC_APP="lernia-func"
CDN_PROFILE="lernia-cdn"
CDN_ENDPOINT="lernia-endpoint"
```

> Bu değişkenleri terminalde çalıştır — sonraki komutlar bunları kullanır.

---

## ✅ Adım 1 — Resource Group (TAMAMLANDI)

```bash
az group create --name $RG --location $LOCATION
```

---

## ✅ Adım 2 — Virtual Network + Subnet (TAMAMLANDI)

```bash
az network vnet create \
  --resource-group $RG \
  --name $VNET \
  --address-prefix 10.0.0.0/16 \
  --location $LOCATION

az network vnet subnet create \
  --resource-group $RG \
  --vnet-name $VNET \
  --name public-subnet \
  --address-prefix 10.0.1.0/24

az network vnet subnet create \
  --resource-group $RG \
  --vnet-name $VNET \
  --name private-subnet \
  --address-prefix 10.0.2.0/24
```

---

## ✅ Adım 3 — Azure Database for MySQL Flexible Server (TAMAMLANDI)

```bash
az mysql flexible-server create \
  --resource-group $RG \
  --name $MYSQL_SERVER \
  --location $LOCATION \
  --admin-user $DB_USER \
  --admin-password $DB_PASSWORD \
  --sku-name Standard_B1ms \
  --tier Burstable \
  --version 8.0.21 \
  --vnet $VNET \
  --subnet private-subnet \
  --private-dns-zone privatelink.mysql.database.azure.com \
  --yes
```

### Veritabanı Oluşturma

```bash
az mysql flexible-server db create \
  --resource-group $RG \
  --server-name $MYSQL_SERVER \
  --database-name $DB_NAME
```

### MySQL FQDN'yi Al (settings.py için lazım)

```bash
az mysql flexible-server show \
  --resource-group $RG \
  --name $MYSQL_SERVER \
  --query "fullyQualifiedDomainName" -o tsv
```

> Çıktı şuna benzer: `lernia-mysql1573458637.mysql.database.azure.com`  
> Bunu `src/cblog/settings.py` içindeki `HOST` alanına yaz.

---

## ✅ Adım 4 — Azure Blob Storage (TAMAMLANDI)

```bash
az storage account create \
  --name $STORAGE \
  --resource-group $RG \
  --location $LOCATION \
  --sku Standard_LRS \
  --kind StorageV2
```

### 4a. Container'ları Oluştur

```bash
# Storage key'i al
STORAGE_KEY=$(az storage account keys list \
  --account-name $STORAGE \
  --resource-group $RG \
  --query "[0].value" -o tsv)

# static container (Django CSS/JS)
az storage container create \
  --name static \
  --account-name $STORAGE \
  --account-key $STORAGE_KEY \
  --public-access blob

# media container (kullanıcı yüklemeleri)
az storage container create \
  --name media \
  --account-name $STORAGE \
  --account-key $STORAGE_KEY \
  --public-access blob

# failover container (Traffic Manager yedek site)
az storage container create \
  --name failover \
  --account-name $STORAGE \
  --account-key $STORAGE_KEY \
  --public-access blob
```

### 4b. Static Website (Failover Sayfası) Etkinleştir

```bash
az storage blob service-properties update \
  --account-name $STORAGE \
  --account-key $STORAGE_KEY \
  --static-website \
  --index-document index.html

# Failover index.html yükle
az storage blob upload \
  --account-name $STORAGE \
  --account-key $STORAGE_KEY \
  --container-name '$web' \
  --file src/S3_Static_Website/index.html \
  --name index.html

az storage blob upload \
  --account-name $STORAGE \
  --account-key $STORAGE_KEY \
  --container-name '$web' \
  --file src/S3_Static_Website/sorry.jpg \
  --name sorry.jpg
```

### 4c. Storage Key'i Al ve .env'e Yaz

```bash
echo $STORAGE_KEY
```

> Bu key'i `src/.env` dosyasındaki `AZURE_STORAGE_KEY` satırına yapıştır.

---

## ✅ Adım 5 — Django Ayarlarını Yapılandır (TAMAMLANDI)

### 5a. `src/cblog/settings.py` — Dolduruldu ✅

```python
ALLOWED_HOSTS = [
    config('AZURE_APP_HOSTNAME', default=''),
]

DATABASES = {
    'default': {
        'NAME': config('DB_NAME', default='lerniablog'),
        'USER': config('DB_USER', default='adminuser'),
        'PASSWORD': config('DB_PASSWORD'),
        'HOST': config('DB_HOST'),
        ...
    }
}

AZURE_ACCOUNT_NAME = config('AZURE_STORAGE_ACCOUNT_NAME')
```

### 5b. `src/.env` — STORAGE_KEY Ekle ⚠️

Storage key'i al ve `src/.env` dosyasına yapıştır:

```bash
az storage account keys list \
  --account-name $STORAGE \
  --resource-group $RG \
  --query "[0].value" -o tsv
```

Çıktıyı `src/.env` dosyasındaki `AZURE_STORAGE_KEY` satırına yapıştır:

```
SECRET_KEY=<python -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())">
DB_PASSWORD=<YOUR-DB-PASSWORD>
AZURE_STORAGE_ACCOUNT_KEY=<yukarıdaki komutun çıktısı>
```

---

## Adım 6 — Azure App Service (EC2 Auto Scaling Karşılığı)

### 6a. App Service Plan Oluştur

```bash
az appservice plan create \
  --name $APP_PLAN \
  --resource-group $RG \
  --location $LOCATION \
  --is-linux \
  --sku B1
```

### 6b. Web App Oluştur

```bash
az webapp create \
  --name $APP_NAME \
  --resource-group $RG \
  --plan $APP_PLAN \
  --runtime "PYTHON:3.12"
```

### 6c. Environment Variables Ayarla (App Service Configuration)

```bash
az webapp config appsettings set \
  --name $APP_NAME \
  --resource-group $RG \
  --settings \
    SECRET_KEY="$SECRET_KEY" \
    DB_PASSWORD="$DB_PASSWORD" \
    DB_HOST="$MYSQL_SERVER.mysql.database.azure.com" \
    DB_NAME="lerniablog" \
    DB_USER="adminuser" \
    AZURE_APP_HOSTNAME="$APP_NAME.azurewebsites.net" \
    AZURE_STORAGE_ACCOUNT_NAME="$STORAGE" \
    AZURE_STORAGE_ACCOUNT_KEY="$STORAGE_KEY"
```

### 6d. Startup Script Ayarla

```bash
az webapp config set \
  --name $APP_NAME \
  --resource-group $RG \
  --startup-file "bash /home/site/wwwroot/startup.sh"
```

### 6e. VNet Integration (App Service → MySQL private bağlantı)

> **Not:** `private-subnet` MySQL'e delegated — App Service için ayrı subnet gerekir.

```powershell
# App Service için ayrı subnet oluştur
az network vnet subnet create `
  --resource-group $RG `
  --vnet-name $VNET `
  --name app-subnet `
  --address-prefix 10.0.3.0/24 `
  --delegations Microsoft.Web/serverFarms

# VNet Integration ekle
az webapp vnet-integration add `
  --name $APP_NAME `
  --resource-group $RG `
  --vnet $VNET `
  --subnet app-subnet
```

### 6f. GitHub'dan Deploy Et

```bash
az webapp deployment source config \
  --name $APP_NAME \
  --resource-group $RG \
  --repo-url https://github.com/Muhammet-Gokmen/lernia-blog \
  --branch main \
  --manual-integration
```

> **Alternatif — ZIP Deploy:**
> ```bash
> cd lernia_project
> Compress-Archive -Path . -DestinationPath app.zip -Force
> az webapp deployment source config-zip \
>   --resource-group $RG \
>   --name $APP_NAME \
>   --src app.zip
> ```

### 6g. App Service URL'ini Kontrol Et

```bash
az webapp show \
  --name $APP_NAME \
  --resource-group $RG \
  --query "defaultHostName" -o tsv
```

---

## Adım 7 — Azure Function App (Lambda Karşılığı)

### 7a. Function App Oluştur

> **Not:** Azure for Students'ta Consumption (Serverless) plan kullanılamıyor.  
> Bunun yerine mevcut App Service Plan (`lernia-plan`) üzerinde çalıştırıyoruz.

```bash
az functionapp create \
  --name $FUNC_APP \
  --resource-group $RG \
  --storage-account $STORAGE \
  --plan $APP_PLAN \
  --runtime python \
  --runtime-version 3.9 \
  --functions-version 4 \
  --os-type linux
```

### 7b. Function App Connection String Ayarla

```bash
CONN_STR=$(az storage account show-connection-string \
  --name $STORAGE \
  --resource-group $RG \
  --query connectionString -o tsv)

az functionapp config appsettings set \
  --name $FUNC_APP \
  --resource-group $RG \
  --settings \
    AzureWebJobsStorage="$CONN_STR" \
    STORAGE_CONNECTION_STRING="$CONN_STR"
```

### 7c. Blob Trigger Function Deploy Et

```bash
cd azure/azure_function

# Azure Functions Core Tools kur (bir kez)
npm install -g azure-functions-core-tools@4 --unsafe-perm true

# Deploy et
func azure functionapp publish $FUNC_APP --python
```

### 7d. Function'ı Doğrula

```bash
# Table Storage'da BlobEvents tablosunu kontrol et
az storage entity query \
  --account-name $STORAGE \
  --account-key $STORAGE_KEY \
  --table-name BlobEvents \
  --output table
```

---

## Adım 8 — Azure CDN (CloudFront Karşılığı)

### 8a. CDN Profili Oluştur

```bash
az cdn profile create \
  --name $CDN_PROFILE \
  --resource-group $RG \
  --location global \
  --sku Standard_Microsoft
```

### 8b. CDN Endpoint Oluştur

```bash
az cdn endpoint create \
  --name $CDN_ENDPOINT \
  --profile-name $CDN_PROFILE \
  --resource-group $RG \
  --origin lernia-app.azurewebsites.net \
  --origin-host-header lernia-app.azurewebsites.net \
  --enable-compression true
```

### 8c. CDN URL'ini Al

```bash
az cdn endpoint show \
  --name $CDN_ENDPOINT \
  --profile-name $CDN_PROFILE \
  --resource-group $RG \
  --query "hostName" -o tsv
```

> Çıktı: `lernia-endpoint.azureedge.net`

---

## Adım 9 — Azure Traffic Manager (Route 53 Failover Karşılığı)

### 9a. Traffic Manager Profile Oluştur

```bash
az network traffic-manager profile create \
  --name lernia-traffic \
  --resource-group $RG \
  --routing-method Priority \
  --unique-dns-name lernia-traffic \
  --ttl 30 \
  --protocol HTTPS \
  --port 443 \
  --path "/"
```

### 9b. Primary Endpoint Ekle (App Service)

```bash
APP_ID=$(az webapp show \
  --name $APP_NAME \
  --resource-group $RG \
  --query id -o tsv)

az network traffic-manager endpoint create \
  --name primary-endpoint \
  --profile-name lernia-traffic \
  --resource-group $RG \
  --type azureEndpoints \
  --target-resource-id $APP_ID \
  --priority 1 \
  --endpoint-status Enabled
```

### 9c. Failover Endpoint Ekle (Static Website)

```bash
# Static Website URL'ini al
STATIC_URL=$(az storage account show \
  --name $STORAGE \
  --resource-group $RG \
  --query "primaryEndpoints.web" -o tsv | sed 's|https://||' | sed 's|/||')

az network traffic-manager endpoint create \
  --name failover-endpoint \
  --profile-name lernia-traffic \
  --resource-group $RG \
  --type externalEndpoints \
  --target $STATIC_URL \
  --priority 2 \
  --endpoint-status Enabled
```

### 9d. Traffic Manager URL'ini Al

```bash
az network traffic-manager profile show \
  --name lernia-traffic \
  --resource-group $RG \
  --query "dnsConfig.fqdn" -o tsv
```

> Çıktı: `lernia-traffic.trafficmanager.net`

---

## Doğrulama (Verification)

### Tüm Kaynakları Listele

```bash
az resource list --resource-group $RG -o table
```

### App Service Loglarını İzle

```bash
az webapp log tail --resource-group $RG --name $APP_NAME
```

### Blob Storage İçeriğini Kontrol Et

```bash
az storage blob list \
  --account-name $STORAGE \
  --account-key $STORAGE_KEY \
  --container-name static \
  --output table
```

### MySQL Bağlantısını Test Et

```bash
az mysql flexible-server connect \
  --name $MYSQL_SERVER \
  --admin-user $DB_USER \
  --admin-password $DB_PASSWORD \
  --database-name $DB_NAME
```

### Uçtan Uca Test

| Test | Komut / URL |
|---|---|
| App Service | `curl https://lernia-app.azurewebsites.net/` |
| CDN | `curl https://lernia-endpoint.azureedge.net/` |
| Traffic Manager | `curl https://lernia-traffic.trafficmanager.net/` |
| Failover testi | `az webapp stop --name $APP_NAME --resource-group $RG` |
| App'i geri aç | `az webapp start --name $APP_NAME --resource-group $RG` |

---

## Sorun Giderme

### MySQL Bağlantı Hatası

```bash
# Private DNS zone VNet'e bağlı mı?
az network private-dns link vnet list \
  --resource-group $RG \
  --zone-name privatelink.mysql.database.azure.com \
  -o table

# Bağlı değilse ekle:
az network private-dns link vnet create \
  --resource-group $RG \
  --zone-name privatelink.mysql.database.azure.com \
  --name lernia-dns-link \
  --virtual-network $VNET \
  --registration-enabled false
```

### Static Files 404 Hatası

```bash
# collectstatic çalıştı mı? Log'a bak:
az webapp log tail --resource-group $RG --name $APP_NAME | grep -i "static"

# Manuel collectstatic:
az webapp ssh --name $APP_NAME --resource-group $RG
# SSH içinde:
cd /home/site/wwwroot/src && python manage.py collectstatic --noinput
```

### App Service Yeniden Başlat

```bash
az webapp restart --name $APP_NAME --resource-group $RG
```

---

## Mevcut Kaynakların Özeti (Ekran Görüntüsünden)

| Kaynak | Ad | Durum |
|---|---|---|
| MySQL Flexible Server | `lernia-mysql1573458637` | ✅ Oluşturuldu |
| Virtual Network | `lernia-vnet` | ✅ Oluşturuldu |
| Storage Account | `lerniablob869090428` | ✅ Oluşturuldu |
| Private DNS Zone | `privatelink.mysql.database.azure.com` | ✅ Oluşturuldu |
| App Service Plan | `lernia-plan` | ⬜ Adım 6 |
| Web App | `lernia-app` | ⬜ Adım 6 |
| Function App | `lernia-func` | ⬜ Adım 7 |
| CDN Profile | `lernia-cdn` | ⬜ Adım 8 |
| Traffic Manager | `lernia-traffic` | ⬜ Adım 9 |

---

*Tüm CLI komutları PowerShell ve Bash'te çalışır. PowerShell'de `\` yerine `` ` `` ile satır devam ettirilebilir.*
