# Azure Student Deployment Guide — Django Blog App

Bu rehber, AWS üzerinde çalışan Django Blog uygulamasının **Azure Student hesabı** ile nasıl dağıtılacağını adım adım açıklamaktadır.

---

## Mimari Genel Bakış

```
                         INTERNET
                            |
                  Azure Traffic Manager
                  (Priority Failover)
                 /                      \
          [Birincil]                [Yedek (Failover)]
         Azure CDN                Azure Blob Storage
       (CDN Profili)             (Static Website)
              |
       Azure App Service
       (Django Uygulaması)
      /         |          \
     |           |           |
Azure MySQL  Azure Blob    Azure Function
(Flexible)   Storage      (Blob Trigger)
             (media/static)      |
                          Azure Table Storage
                           (BlobEvents tablosu)
```

---

## AWS → Azure Servis Karşılaştırması

| AWS Servisi | Azure Karşılığı | Notlar |
|---|---|---|
| VPC | Azure Virtual Network (VNet) | Aynı konsept |
| Public / Private Subnet | VNet Subnet | Aynı konsept |
| Internet Gateway | Dahili (VNet'e gömülü) | Manuel yapılandırma gerekmez |
| NAT Gateway | Azure NAT Gateway | Aynı |
| EC2 Auto Scaling Group | Azure App Service + Auto Scale | PaaS, yönetimi daha kolay |
| Application Load Balancer | App Service (yerleşik LB) | Otomatik |
| RDS MySQL | Azure Database for MySQL Flexible Server | |
| S3 (media / static) | Azure Blob Storage | Container = Bucket |
| CloudFront | Azure CDN | |
| Route 53 + Failover | Azure Traffic Manager + DNS Zone | |
| Lambda | Azure Functions | |
| DynamoDB | Azure Table Storage | NoSQL key-value |
| VPC Endpoint (S3) | Service Endpoint / Private Endpoint | |
| EC2 Launch Template (userdata.sh) | App Service Startup Script | |

---

## Ön Koşullar

1. **Azure for Students hesabı** → [azure.microsoft.com/free/students](https://azure.microsoft.com/en-us/free/students/)  
   - 100 $ ücretsiz kredi verir.  
   - Kredi kartı **gerekmez**.

2. **Azure CLI** (opsiyonel ama önerilir)  
   ```bash
   # Windows
   winget install Microsoft.AzureCLI
   az login
   ```

3. Bu repodaki `azure/` klasörünü kopyalayın ve içindeki dosyaları `src/` ile birleştirin:
   ```
   azure/src/cblog/settings.py   →  src/cblog/settings.py  (mevcut settings'i değiştir)
   azure/src/cblog/storages.py   →  src/cblog/storages.py  (mevcut storages'ı değiştir)
   azure/requirements.txt        →  requirements.txt
   azure/startup.sh              →  startup.sh
   ```

---

## Adım 1 — Resource Group Oluşturma

Resource Group, tüm Azure kaynaklarını bir arada tutan mantıksal bir kapsayıcıdır (AWS'deki CloudFormation Stack'e benzer).

**Portal:**
1. [portal.azure.com](https://portal.azure.com) → **Resource Groups** → **+ Create**
2. Alanları doldurun:
   | Alan | Değer |
   |---|---|
   | Subscription | Azure for Students |
   | Resource group | `lernia-rg` |
   | Region | `Sweden Central` |
3. **Review + Create** → **Create**

**CLI (alternatif):**
```bash
az group create --name lernia-rg --location swedencentral
```

---

## Adım 2 — Virtual Network (VNet) Oluşturma

> **"Deployment validation failed — policy violation" hatası alıyorsanız:**  
> Azure for Students hesapları bazı bölgelerde kaynak oluşturulmasını kısıtlayan policy'lere sahiptir.  
> Adım 1'de Resource Group için hangi bölgeyi seçtiyseniz **VNet için de aynı bölgeyi** seçin.  
> Sorun devam ederse aşağıdaki **izin verilen bölge listesini** deneyin:
> - `East US`
> - `West US`  
> - `Sweden Central` ✓ (kullandığınız bölge)
> - `Germany West Central`
> - `Switzerland North`
>
> Hangi bölgelerin kullanılabilir olduğunu görmek için CLI ile kontrol edebilirsiniz:
> ```bash
> az account list-locations --query "[].{Name:name, DisplayName:displayName}" -o table
> ```

**Portal:**
1. Sol menüden **Virtual Networks** → **+ Create**
2. **Basics** sekmesi:
   | Alan | Değer |
   |---|---|
   | Subscription | `Azure for Students` |
   | Resource group | `lernia-rg` (Adım 1'de oluşturduğunuz) |
   | Name | `lernia-vnet` |
   | Region | Adım 1'deki Resource Group ile **aynı bölge** |

3. **Security** sekmesi: Hiçbir şeyi değiştirmeyin, **Next** ile geçin.

4. **IP Addresses** sekmesi:
   - Varolan default subnet'i silin (çöp kutusu ikonuna tıklayın)
   - **Address space**: `10.0.0.0/16`
   - **+ Add a subnet** ile iki subnet ekleyin:

   | Alan | Subnet 1 (Public) | Subnet 2 (Private) |
   |---|---|---|
   | Name | `public-subnet` | `private-subnet` |
   | Starting address | `10.0.1.0` | `10.0.2.0` |
   | Size | `/24` (256 adres) | `/24` (256 adres) |

5. **Tags** sekmesi: Değiştirmeyin, geçin.

6. **Review + Create** → mavi **Create** butonuna tıklayın.  
   Deployment 30–60 saniye içinde tamamlanır.

**CLI alternatifi (hata ayıklamak için daha net mesaj verir):**
```bash
# VNet oluştur
az network vnet create \
  --resource-group lernia-rg \
  --name lernia-vnet \
  --address-prefix 10.0.0.0/16 \
  --location swedencentral

# Public subnet ekle
az network vnet subnet create \
  --resource-group lernia-rg \
  --vnet-name lernia-vnet \
  --name public-subnet \
  --address-prefix 10.0.1.0/24

# Private subnet ekle
az network vnet subnet create \
  --resource-group lernia-rg \
  --vnet-name lernia-vnet \
  --name private-subnet \
  --address-prefix 10.0.2.0/24
```

> **Not:** CLI kullanırsanız hata mesajı çok daha açıklayıcı olur ve hangi policy'nin engellendiğini gösterir.  
> App Service, VNet Integration özelliği ile private subnet üzerinden MySQL'e bağlanır.

---

## Adım 3 — Azure Database for MySQL Flexible Server

AWS RDS MySQL'in karşılığıdır.

**Portal:**
1. **Azure Database for MySQL flexible servers** → **+ Create**
2. **Flexible server** seçin
3. Temel ayarlar:
   | Alan | Değer |
   |---|---|
   | Resource group | `lernia-rg` |
   | Server name | `lernia-mysql` (küresel olarak benzersiz olmalı) |
   | Region | `Sweden Central` |
   | MySQL version | `8.0` |
   | Workload type | Development |
   | Compute + storage | **Burstable, B1ms** (en ucuz, ~10 $/ay) |
   | Admin username | `adminuser` |
   | Password | Güçlü bir şifre (ör. `REMOVED-PASSWORD`) |

4. **Networking** sekmesi:
   - Connectivity method: **Private access (VNet Integration)**
   - Virtual network: `lernia-vnet`
   - Subnet: `private-subnet`
   - Private DNS zone: otomatik oluşturulur

5. **Review + Create** → **Create** (3–5 dk sürebilir)

**Veritabanı oluşturma:**
```bash
az mysql flexible-server db create \
  --resource-group lernia-rg \
  --server-name lernia-mysql \
  --database-name lerniablog
```

> **SSL Notu:** Azure MySQL, SSL bağlantısı zorunlu kılar.  
> `DigiCertGlobalRootCA.crt.pem` sertifikasını App Service'e yüklemenize gerek yok —  
> sertifika `/etc/ssl/certs/` altında zaten mevcuttur.

---

## Adım 4 — Azure Storage Account + Containers (Blob Storage)

AWS S3'ün karşılığıdır.

### 4a. Storage Account Oluşturma

**Portal:**
1. **Storage accounts** → **+ Create**
2. Ayarlar:
   | Alan | Değer |
   |---|---|
   | Resource group | `lernia-rg` |
   | Storage account name | `lerniablobstorage` (küresel olarak benzersiz) |
   | Region | `Sweden Central` |
   | Performance | Standard |
   | Redundancy | LRS (Locally Redundant — öğrenci için yeterli) |
3. **Review + Create** → **Create**

### 4b. Container'ları Oluşturma (S3 Bucket = Storage Container)

Storage account oluştuktan sonra:
1. **Data storage** → **Containers** → **+ Container**

| Container Name | Access Level | Kullanım |
|---|---|---|
| `static` | Blob (anonim okuma) | Django static dosyaları (CSS, JS) |
| `media` | Blob (anonim okuma) | Kullanıcı yüklemeleri (fotoğraflar) |
| `failover` | Blob (anonim okuma) | Traffic Manager yedek static site |

### 4c. Static Website (Failover Sayfası)

AWS'deki S3 Static Website özelliğinin karşılığı:

1. **Data management** → **Static website** → **Enabled**
2. Index document name: `index.html`
3. **Save** tıklayın
4. Verilen `Primary endpoint` URL'sini not edin (Traffic Manager için lazım).
5. `S3_Static_Website/index.html` ve `S3_Static_Website/sorry.jpg` dosyalarını `$web` container'a yükleyin.

### 4d. Storage Account Key Alma

**Settings** → **Access keys** → **key1** → **Show** → Kopyalayın (`.env` için lazım).

---

## Adım 5 — Django Ayarlarını Yapılandırma

AWS `settings.py` yerine `azure/src/cblog/settings.py` dosyasını kullanacaksınız.

### 5a. `src/cblog/settings.py` Değişiklikleri (Özet)

| AWS Ayarı | Azure Karşılığı |
|---|---|
| `AWS_STORAGE_BUCKET_NAME` | `AZURE_ACCOUNT_NAME` |
| `AWS_S3_CUSTOM_DOMAIN` | `AZURE_CUSTOM_DOMAIN` |
| `AWS_S3_REGION_NAME` | Gerekmiyor |
| `storages.backends.s3boto3.S3Boto3Storage` | `storages.backends.azure_storage.AzureStorage` |
| `cblog.storages.MediaStore` | `cblog.storages.AzureMediaStorage` |
| RDS endpoint | Azure MySQL FQDN |

### 5b. `.env` Dosyası Oluşturma

`src/.env` dosyasını aşağıdaki değerlerle doldurun:

```env
# Django
SECRET_KEY=REMOVED-SECRET-KEY-2

# Azure MySQL
DB_NAME=lerniablog
DB_USER=adminuser
DB_PASSWORD=REMOVED-PASSWORD
DB_HOST=lernia-mysql.mysql.database.azure.com
DB_PORT=3306

# Azure Blob Storage
AZURE_STORAGE_ACCOUNT_NAME=lerniablobstorage
AZURE_STORAGE_ACCOUNT_KEY=<Adım 4d'den kopyaladığınız key>

# App Service hostname
AZURE_APP_HOSTNAME=lernia-app.azurewebsites.net
```

### 5c. `storages.py` Değiştirme

`azure/src/cblog/storages.py` dosyasını `src/cblog/storages.py` ile değiştirin:

```python
from storages.backends.azure_storage import AzureStorage

class AzureMediaStorage(AzureStorage):
    azure_container = 'media'
    overwrite_files = False
```

---

## Adım 6 — Azure App Service'e Dağıtım

AWS EC2 Auto Scaling Group'un karşılığıdır. App Service, yük dengeleme ve otomatik ölçeklendirmeyi dahili olarak yönetir.

### 6a. App Service Plan Oluşturma

**Portal:**
1. **App Service plans** → **+ Create**
2. Ayarlar:
   | Alan | Değer |
   |---|---|
   | Resource group | `lernia-rg` |
   | Name | `lernia-plan` |
   | Operating System | Linux |
   | Region | `Sweden Central` |
   | Pricing tier | **B1** (~13 $/ay) veya **F1** (ücretsiz, kısıtlı) |

### 6b. Web App Oluşturma

1. **App Services** → **+ Create** → **Web App**
2. Ayarlar:
   | Alan | Değer |
   |---|---|
   | Resource group | `lernia-rg` |
   | Name | `lernia-app` (küresel olarak benzersiz) |
   | Publish | Code |
   | Runtime stack | Python 3.8 |
   | Operating System | Linux |
   | App Service Plan | `lernia-plan` |
3. **Review + Create** → **Create**

### 6c. Environment Variables (Ortam Değişkenleri) Ayarlama

AWS Secrets Manager / Parameter Store yerine App Service **Configuration** kullanılır:

1. App Service → **Settings** → **Configuration** → **Application settings**
2. Her bir `.env` değişkenini buraya ekleyin:

   | Name | Value |
   |---|---|
   | SECRET_KEY | `i2^$(%im!!)@...` |
   | DB_NAME | `lerniablog` |
   | DB_USER | `adminuser` |
   | DB_PASSWORD | `REMOVED-PASSWORD` |
   | DB_HOST | `lernia-mysql.mysql.database.azure.com` |
   | DB_PORT | `3306` |
   | AZURE_STORAGE_ACCOUNT_NAME | `lerniablobstorage` |
   | AZURE_STORAGE_ACCOUNT_KEY | `<key>` |
   | AZURE_APP_HOSTNAME | `lernia-app.azurewebsites.net` |

3. **Save** → **Continue**

### 6d. VNet Integration (Private Subnet Bağlantısı)

App Service'in MySQL'e private subnet üzerinden erişmesi için:

1. App Service → **Settings** → **Networking** → **VNet Integration** → **Add VNet**
2. VNet: `lernia-vnet`, Subnet: `private-subnet`
3. **Connect**

### 6e. Startup Script Ayarlama

AWS userdata.sh'ın karşılığı olan `startup.sh` dosyasını ayarlayın:

1. App Service → **Settings** → **Configuration** → **General settings**
2. **Startup Command** alanına:
   ```
   bash /home/site/wwwroot/startup.sh
   ```
3. **Save**

### 6f. GitHub'dan Deploy Etme

**AWS EC2'deki `git clone` yerine App Service Deployment Center kullanılır:**

1. App Service → **Deployment** → **Deployment Center**
2. Source: **GitHub**
3. Authorize GitHub hesabınızla giriş yapın
4. Repository ve Branch seçin
5. **Save** → Otomatik CI/CD pipeline kurulur

> **Not:** GitHub Actions workflow dosyası `.github/workflows/` altına otomatik eklenir.

**Alternatif — ZIP Deploy:**
```bash
cd lernia_project
zip -r app.zip . -x "*.git*" "azure/*"
az webapp deployment source config-zip \
  --resource-group lernia-rg \
  --name lernia-app \
  --src app.zip
```

---

## Adım 7 — Azure Function Oluşturma (Lambda Karşılığı)

AWS Lambda + S3 trigger'ın karşılığıdır. Blob Storage'a dosya yüklendiğinde Azure Table Storage'a kayıt atar.

### 7a. Function App Oluşturma

**Portal:**
1. **Function App** → **+ Create**
2. Ayarlar:
   | Alan | Değer |
   |---|---|
   | Resource group | `lernia-rg` |
   | Function App name | `lernia-blobfunc` |
   | Publish | Code |
   | Runtime stack | Python |
   | Version | 3.8 |
   | Region | `Sweden Central` |
   | Hosting plan | **Consumption (Serverless)** — Ücretsiz tier |
   | Storage account | `lerniablobstorage` |

3. **Review + Create** → **Create**

### 7b. Function App Configuration

Function App → **Settings** → **Configuration** → **Application settings**:

| Name | Value |
|---|---|
| AzureWebJobsStorage | `<lerniablobstorage bağlantı dizesi>` |
| STORAGE_CONNECTION_STRING | `<lerniablobstorage bağlantı dizesi>` |

**Bağlantı dizesini almak için:**
Storage account → **Security + networking** → **Access keys** → **Connection string** (key1)

### 7c. Blob Trigger Function Deploy Etme

`azure/azure_function/` klasörünü Function App'e deploy edin:

```bash
cd azure/azure_function

# Azure Functions Core Tools gerekir
npm install -g azure-functions-core-tools@4

func azure functionapp publish lernia-blobfunc
```

**Sonuç:**  
`media` container'a dosya yüklendiğinde, Azure Table Storage'daki `BlobEvents` tablosuna şu bilgiler yazılır:
- `RowKey` = dosya adı (DynamoDB'deki `id` gibi)
- `Timestamp` = olay zamanı
- `Event` = `BlobCreated`
- `FullPath`, `SizeBytes`

### 7d. Table Storage Doğrulama

**Portal:**
Storage account → **Data storage** → **Tables** → `BlobEvents` tablosunu kontrol edin.

---

## Adım 8 — Azure CDN Oluşturma (CloudFront Karşılığı)

### 8a. CDN Profili Oluşturma

**Portal:**
1. **CDN profiles** → **+ Create**
2. Ayarlar:
   | Alan | Değer |
   |---|---|
   | Resource group | `lernia-rg` |
   | Name | `lernia-cdn` |
   | Pricing tier | **Standard Microsoft** (en ucuz) |
   | Create a CDN endpoint now | ✓ |
   | Endpoint name | `lernia-endpoint` |
   | Origin type | Web App |
   | Origin hostname | `lernia-app.azurewebsites.net` |

3. **Create**

### 8b. Custom Domain (Opsiyonel)

CDN endpoint URL'si: `lernia-endpoint.azureedge.net`

Kendi domain'iniz varsa:  
CDN endpoint → **+ Custom domain** → Domain adını ekleyin.

---

## Adım 9 — Azure Traffic Manager (Route 53 Failover Karşılığı)

Traffic Manager, AWS Route 53 + Health Check + Failover Routing'in karşılığıdır.

### 9a. Traffic Manager Profile Oluşturma

**Portal:**
1. **Traffic Manager profiles** → **+ Create**
2. Ayarlar:
   | Alan | Değer |
   |---|---|
   | Name | `lernia-traffic` |
   | Routing method | **Priority** (Failover için) |
   | Resource group | `lernia-rg` |

3. **Create**

### 9b. Endpoint'leri Ekleme

Traffic Manager profile → **Settings** → **Endpoints** → **+ Add**

**Primary Endpoint (Öncelik 1 — App Service/CDN):**
| Alan | Değer |
|---|---|
| Type | Azure endpoint |
| Name | `primary-endpoint` |
| Target resource type | App Service / CDN |
| Target resource | `lernia-app` veya CDN endpoint |
| Priority | `1` |

**Secondary Endpoint (Öncelik 2 — Static Website):**
| Alan | Değer |
|---|---|
| Type | External endpoint |
| Name | `failover-endpoint` |
| FQDN | Adım 4c'deki Static Website URL (ör. `lerniablobstorage.z6.web.core.windows.net`) |
| Priority | `2` |

### 9c. Health Check Ayarı

Traffic Manager → **Settings** → **Configuration**:
- Protocol: `HTTPS`
- Port: `443`
- Path: `/`
- Probing interval: `30` saniye

### 9d. DNS Yapılandırması

Traffic Manager URL'si: `lernia-traffic.trafficmanager.net`

Kendi domain'iniz varsa Azure DNS Zone oluşturun:
1. **DNS zones** → **+ Create**
2. Name: `yourdomain.com`
3. CNAME kaydı ekleyin: `www` → `lernia-traffic.trafficmanager.net`

---

## Adım 10 — Static Failover Web Sitesini Yükleme

AWS S3 Static Website'ın tam karşılığıdır.

1. Storage account → **Containers** → `$web` container'ı açın
2. `S3_Static_Website/index.html` ve `S3_Static_Website/sorry.jpg` dosyalarını yükleyin
3. **Static website** özelliğinin etkin olduğunu doğrulayın (Adım 4c)

**Test:**  
Primary App Service'i durdurarak Traffic Manager'ın failover'a geçip geçmediğini test edin.

---

## Doğrulama (Verification)

### Temel Kontroller

```bash
# 1. App Service'in çalışıp çalışmadığını kontrol edin
curl https://lernia-app.azurewebsites.net/

# 2. Django migrations'ın çalıştığını kontrol edin
# App Service → Log stream → Başlangıç loglarını inceleyin

# 3. Blob Storage bağlantısı
az storage blob list \
  --account-name lerniablobstorage \
  --container-name static \
  --output table

# 4. Azure Function logları
az functionapp logs show \
  --resource-group lernia-rg \
  --name lernia-blobfunc

# 5. Table Storage içeriği
az storage entity query \
  --account-name lerniablobstorage \
  --table-name BlobEvents \
  --output table
```

### İşlevsel Test Adımları

| Test | Beklenen Sonuç |
|---|---|
| `https://lernia-app.azurewebsites.net/` | Blog ana sayfası |
| Yeni kullanıcı kaydı | E-posta + profil oluşturulur |
| Blog yazısı oluştur + resim yükle | Resim `media` container'a gider |
| BlobEvents tablosu | Yeni yükleme kaydı görünür |
| `https://lernia-endpoint.azureedge.net/` | CDN üzerinden blog |
| App Service'i durdur → TM URL'si | Failover sayfasına yönlenir |

---

## Maliyet Tahmini (Student Account — 100 $ Kredi)

| Servis | Tier | Tahmini Aylık Maliyet |
|---|---|---|
| Azure App Service | B1 (1 core, 1.75 GB) | ~13 $ |
| Azure Database for MySQL | Flexible Server B1ms | ~10 $ |
| Azure Blob Storage | LRS, ~5 GB | ~0.10 $ |
| Azure Functions | Consumption (ilk 1M ücretsiz) | ~0 $ |
| Azure Table Storage | Dahili (Storage Account) | ~0.01 $ |
| Azure CDN | Standard Microsoft | ~0.08 $/GB |
| Traffic Manager | DNS Queries | ~0.54 $/1M query |
| **Toplam** | | **~24 $/ay** |

> 100 $ kredi ile yaklaşık **4 ay** çalıştırabilirsiniz.  
> F1 (ücretsiz) App Service planı kullanırsanız ayda **~11 $**'a düşer, ancak F1'de custom domain ve SSL kısıtlıdır.

---

## Sorun Giderme (Troubleshooting)

### MySQL Bağlantı Hatası

```
django.db.utils.OperationalError: (2003, "Can't connect to MySQL server")
```
- VNet Integration'ın doğru subnet'e bağlı olduğunu kontrol edin.
- MySQL Flexible Server'ın private DNS zone'unun VNet'e bağlı olduğunu doğrulayın:  
  MySQL server → **Networking** → Private DNS zone → VNet link.
- Firewall kuralı ekleyin: MySQL server → **Networking** → **Allow Azure services** ✓

### Static Files Yüklenmiyor

```
404 Not Found: /static/blog/main.css
```
- `python manage.py collectstatic` çalıştı mı? Startup.sh loglarına bakın.
- `static` container'ın Access Level'ı `Blob` (anonim okuma) olmalı.
- `AZURE_STORAGE_ACCOUNT_KEY` ortam değişkeninin doğru ayarlandığını kontrol edin.

### SSL Hatası (MySQL)

```
django.db.utils.OperationalError: SSL connection error
```
- settings.py'deki SSL yapılandırmasını kontrol edin:
  ```python
  'OPTIONS': {'ssl': {'ssl-ca': '/etc/ssl/certs/DigiCertGlobalRootCA.crt.pem'}}
  ```
- App Service Linux ortamında bu sertifika varsayılan olarak mevcuttur.

### Azure Function Tetiklenmiyor

- Function App → **Monitor** → **Invocations** bölümünü kontrol edin.
- `AzureWebJobsStorage` bağlantı dizesinin doğru olduğunu doğrulayın.
- Blob trigger path'inin `media/{name}` formatında olduğunu kontrol edin.
- `media` container'ın var olduğunu ve dosya yüklendiğini doğrulayın.

### 500 Internal Server Error

App Service → **Monitoring** → **Log stream** ile canlı logları izleyin:
```bash
az webapp log tail --resource-group lernia-rg --name lernia-app
```

---

## Dosya Yapısı (Azure Klasörü)

```
azure/
├── src/
│   ├── cblog/
│   │   ├── settings.py       # AWS S3/RDS → Azure Blob/MySQL adaptasyonu
│   │   └── storages.py       # AzureMediaStorage (S3Boto3Storage yerine)
│   └── .env.example          # Ortam değişkenleri şablonu
├── azure_function/
│   ├── function_app.py       # Lambda → Azure Function (Blob Trigger)
│   └── requirements.txt      # Azure Function bağımlılıkları
├── requirements.txt          # boto3 yerine azure-storage-blob + gunicorn + whitenoise
├── startup.sh                # EC2 userdata.sh karşılığı (App Service başlangıç scripti)
└── README_solution_student.md  # Bu dosya
```

---

*Bu rehber, AWS capstone projesinin Azure Student hesabıyla yeniden oluşturulması için hazırlanmıştır.*
