# Azure CLI Çözüm Rehberi — Django Blog App (Student Account)

Tüm adımlar **Bash terminalde Azure CLI** ile yapılır. Portal adımı yoktur.

## Ön Koşullar

```bash
# Azure CLI kurulu ve giriş yapılmış olmalı
az login
az account show   # Azure for Students subscription görünmeli
```

---

## 0. Değişkenleri Ayarla (Bir Kez Çalıştır)

> Aşağıdaki değerleri **kendi tercihlerine göre** değiştir.  
> Kaynak adları Azure genelinde benzersiz olmalı.

```bash
# Temel ayarlar
RG="myapp-rg"
LOCATION="swedencentral"        # değiştirebilirsin: eastus, westeurope

# Kaynak adları — benzersiz olması için sonuna rastgele rakam ekle
VNET="myapp-vnet"
MYSQL_SERVER="myapp-mysql-$RANDOM"   # örn: myapp-mysql-14823
STORAGE="myappblob$RANDOM"            # örn: myappblob27491 (sadece küçük harf + rakam)
DB_NAME="lerniablog"
DB_USER="adminuser"
DB_PASSWORD="MySecurePass1!"          # en az 8 karakter, büyük/küçük/rakam/sembol
APP_PLAN="myapp-plan"
APP_NAME="myapp-blog-$RANDOM"        # örn: myapp-blog-9823
FUNC_APP="myapp-func-$RANDOM"
CDN_PROFILE="myapp-cdn"
CDN_ENDPOINT="myapp-endpoint-$RANDOM"
TRAFFIC="myapp-traffic-$RANDOM"

# Değişkenleri kaydet (terminali kapatırsan tekrar çalıştır)
echo "RG=$RG | APP=$APP_NAME | MYSQL=$MYSQL_SERVER | STORAGE=$STORAGE"
```

---

## Adım 1 — Resource Group

```bash
az group create --name $RG --location $LOCATION
```

---

## Adım 2 — Virtual Network + Subnet

```bash
az network vnet create \
  --resource-group $RG \
  --name $VNET \
  --address-prefix 10.0.0.0/16 \
  --location $LOCATION

# Public subnet (App Service için)
az network vnet subnet create \
  --resource-group $RG \
  --vnet-name $VNET \
  --name public-subnet \
  --address-prefix 10.0.1.0/24

# Private subnet (MySQL için — delegated)
az network vnet subnet create \
  --resource-group $RG \
  --vnet-name $VNET \
  --name private-subnet \
  --address-prefix 10.0.2.0/24 \
  --delegations Microsoft.DBforMySQL/flexibleServers

# App Service VNet Integration için ayrı subnet
az network vnet subnet create \
  --resource-group $RG \
  --vnet-name $VNET \
  --name app-subnet \
  --address-prefix 10.0.3.0/24 \
  --delegations Microsoft.Web/serverFarms
```

---

## Adım 3 — Azure Database for MySQL Flexible Server

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

### Veritabanı Oluştur

```bash
az mysql flexible-server db create \
  --resource-group $RG \
  --server-name $MYSQL_SERVER \
  --database-name $DB_NAME
```

### MySQL FQDN'yi Kaydet

```bash
DB_HOST=$(az mysql flexible-server show \
  --resource-group $RG \
  --name $MYSQL_SERVER \
  --query "fullyQualifiedDomainName" -o tsv)

echo "DB_HOST=$DB_HOST"
```

---

## Adım 4 — Azure Blob Storage

```bash
az storage account create \
  --name $STORAGE \
  --resource-group $RG \
  --location $LOCATION \
  --sku Standard_LRS \
  --kind StorageV2 \
  --allow-blob-public-access true
```

### Storage Key'i Al

```bash
STORAGE_KEY=$(az storage account keys list \
  --account-name $STORAGE \
  --resource-group $RG \
  --query "[0].value" -o tsv)

echo "STORAGE_KEY=$STORAGE_KEY"
```

### Container'ları Oluştur

```bash
# Django CSS/JS dosyaları
az storage container create \
  --name static \
  --account-name $STORAGE \
  --account-key $STORAGE_KEY \
  --public-access blob

# Kullanıcı yüklemeleri (profil fotoğrafları vb.)
az storage container create \
  --name media \
  --account-name $STORAGE \
  --account-key $STORAGE_KEY \
  --public-access blob
```

### Static Website (Failover Sayfası)

```bash
az storage blob service-properties update \
  --account-name $STORAGE \
  --account-key $STORAGE_KEY \
  --static-website \
  --index-document index.html

# Failover HTML yükle (basit "bakım" sayfası)
cat > /tmp/index.html << 'EOF'
<!DOCTYPE html>
<html><body>
<h1>Site under maintenance. Please try again later.</h1>
</body></html>
EOF

az storage blob upload \
  --account-name $STORAGE \
  --account-key $STORAGE_KEY \
  --container-name '$web' \
  --file /tmp/index.html \
  --name index.html
```

---

## Adım 5 — App Service (Django)

### App Service Plan

```bash
az appservice plan create \
  --name $APP_PLAN \
  --resource-group $RG \
  --location $LOCATION \
  --is-linux \
  --sku B1
```

### Web App Oluştur

```bash
az webapp create \
  --name $APP_NAME \
  --resource-group $RG \
  --plan $APP_PLAN \
  --runtime "PYTHON:3.11"
```

### SECRET_KEY Üret

```bash
SECRET_KEY=$(python3 -c "import secrets, string; print(''.join(secrets.choice(string.ascii_letters + string.digits + '!@#%^&*') for _ in range(50)))")
echo "SECRET_KEY=$SECRET_KEY"
```

### Environment Variables Ayarla

```bash
az webapp config appsettings set \
  --name $APP_NAME \
  --resource-group $RG \
  --settings \
    SECRET_KEY="$SECRET_KEY" \
    DB_NAME="$DB_NAME" \
    DB_USER="$DB_USER" \
    DB_PASSWORD="$DB_PASSWORD" \
    DB_HOST="$DB_HOST" \
    AZURE_APP_HOSTNAME="$APP_NAME.azurewebsites.net" \
    AZURE_STORAGE_ACCOUNT_NAME="$STORAGE" \
    AZURE_STORAGE_ACCOUNT_KEY="$STORAGE_KEY"
```

### Startup Script Ayarla

```bash
az webapp config set \
  --name $APP_NAME \
  --resource-group $RG \
  --startup-file "bash /home/site/wwwroot/startup.sh"
```

### VNet Integration (App Service → MySQL özel ağ)

```bash
az webapp vnet-integration add \
  --name $APP_NAME \
  --resource-group $RG \
  --vnet $VNET \
  --subnet app-subnet
```

### Kodu Deploy Et (ZIP)

```bash
# Proje klasöründeyken çalıştır
cd "$(git rev-parse --show-toplevel)"

zip -r app.zip . \
  --exclude "*.git*" \
  --exclude "*.env" \
  --exclude "__pycache__/*" \
  --exclude "*.zip" \
  --exclude "media_root/*"

az webapp deployment source config-zip \
  --resource-group $RG \
  --name $APP_NAME \
  --src app.zip

rm app.zip
```

### Deploy Doğrula

```bash
az webapp log tail \
  --resource-group $RG \
  --name $APP_NAME
```

> Tarayıcıda aç: `https://$APP_NAME.azurewebsites.net`

---

## Adım 6 — Azure Function App (Blob Trigger)

```bash
az functionapp create \
  --name $FUNC_APP \
  --resource-group $RG \
  --storage-account $STORAGE \
  --plan $APP_PLAN \
  --runtime python \
  --runtime-version 3.11 \
  --functions-version 4 \
  --os-type linux
```

### Connection String Ayarla

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

### Function Kodu Deploy Et

```bash
# Azure Functions Core Tools kur (bir kez)
npm install -g azure-functions-core-tools@4 --unsafe-perm true

cd azure/azure_function
func azure functionapp publish $FUNC_APP --python
cd ../..
```

---

## Adım 7 — Azure CDN (CloudFront Karşılığı)

```bash
az cdn profile create \
  --name $CDN_PROFILE \
  --resource-group $RG \
  --location global \
  --sku Standard_Microsoft

az cdn endpoint create \
  --name $CDN_ENDPOINT \
  --profile-name $CDN_PROFILE \
  --resource-group $RG \
  --origin "$APP_NAME.azurewebsites.net" \
  --origin-host-header "$APP_NAME.azurewebsites.net" \
  --enable-compression true
```

### CDN URL'ini Al

```bash
CDN_URL=$(az cdn endpoint show \
  --name $CDN_ENDPOINT \
  --profile-name $CDN_PROFILE \
  --resource-group $RG \
  --query "hostName" -o tsv)

echo "CDN: https://$CDN_URL"
```

---

## Adım 8 — Azure Traffic Manager (Route 53 Failover Karşılığı)

```bash
az network traffic-manager profile create \
  --name $TRAFFIC \
  --resource-group $RG \
  --routing-method Priority \
  --unique-dns-name $TRAFFIC \
  --ttl 30 \
  --protocol HTTPS \
  --port 443 \
  --path "/"
```

### Primary Endpoint (App Service)

```bash
APP_ID=$(az webapp show \
  --name $APP_NAME \
  --resource-group $RG \
  --query id -o tsv)

az network traffic-manager endpoint create \
  --name primary \
  --profile-name $TRAFFIC \
  --resource-group $RG \
  --type azureEndpoints \
  --target-resource-id $APP_ID \
  --priority 1 \
  --endpoint-status Enabled
```

### Failover Endpoint (Static Website)

```bash
STATIC_HOST=$(az storage account show \
  --name $STORAGE \
  --resource-group $RG \
  --query "primaryEndpoints.web" -o tsv | sed 's|https://||' | sed 's|/||')

az network traffic-manager endpoint create \
  --name failover \
  --profile-name $TRAFFIC \
  --resource-group $RG \
  --type externalEndpoints \
  --target $STATIC_HOST \
  --priority 2 \
  --endpoint-status Enabled
```

### Traffic Manager URL'ini Al

```bash
az network traffic-manager profile show \
  --name $TRAFFIC \
  --resource-group $RG \
  --query "dnsConfig.fqdn" -o tsv
```

---

## Doğrulama

```bash
# Tüm kaynakları listele
az resource list --resource-group $RG -o table

# App Service logları
az webapp log tail --resource-group $RG --name $APP_NAME

# MySQL bağlantı testi
az mysql flexible-server connect \
  --name $MYSQL_SERVER \
  --admin-user $DB_USER \
  --admin-password $DB_PASSWORD \
  --database-name $DB_NAME

# Blob Storage içeriği
az storage blob list \
  --account-name $STORAGE \
  --account-key $STORAGE_KEY \
  --container-name static \
  --output table

# Failover testi
az webapp stop --name $APP_NAME --resource-group $RG
# Traffic Manager'ın failover endpoint'e geçmesi ~30 saniye sürer
curl -I https://$TRAFFIC.trafficmanager.net/
az webapp start --name $APP_NAME --resource-group $RG
```

---

## Sorun Giderme

### MySQL Bağlantı Hatası

```bash
# Private DNS zone VNet'e bağlı mı?
az network private-dns link vnet list \
  --resource-group $RG \
  --zone-name privatelink.mysql.database.azure.com \
  -o table

# Bağlı değilse ekle
az network private-dns link vnet create \
  --resource-group $RG \
  --zone-name privatelink.mysql.database.azure.com \
  --name myapp-dns-link \
  --virtual-network $VNET \
  --registration-enabled false
```

### Static Files 404

```bash
# SSH ile bağlan ve manuel collectstatic çalıştır
az webapp ssh --name $APP_NAME --resource-group $RG
# SSH içinde:
# cd /home/site/wwwroot/src && python manage.py collectstatic --noinput
```

### App'i Yeniden Başlat

```bash
az webapp restart --name $APP_NAME --resource-group $RG
```

### Tüm Kaynakları Sil (Temizlik)

```bash
az group delete --name $RG --yes --no-wait
```
