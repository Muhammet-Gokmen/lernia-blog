# Azure Portal Çözüm Rehberi — Django Blog App (Student Account)

Tüm adımlar **[portal.azure.com](https://portal.azure.com)** üzerinden yapılır.

> **Not:** Azure for Students hesabı ile başla → $100 ücretsiz kredi, kredi kartı gerekmez.

---

## Adım 1 — Resource Group

1. Portal'da **Resource groups** → **+ Create**
2. Doldur:

   | Alan | Değer |
   |------|-------|
   | Subscription | Azure for Students |
   | Resource group | `myapp-rg` (istediğin adı ver) |
   | Region | `Sweden Central` (veya sana yakın bir bölge) |

3. **Review + Create** → **Create**

---

## Adım 2 — Virtual Network

1. **Virtual Networks** → **+ Create**

2. **Basics** sekmesi:

   | Alan | Değer |
   |------|-------|
   | Resource group | `myapp-rg` |
   | Name | `myapp-vnet` |
   | Region | Resource Group ile **aynı bölge** |

3. **IP Addresses** sekmesi — **address space**: `10.0.0.0/16`  
   Default subnet'i sil, aşağıdaki 3 subnet'i ekle:

   | Name | Starting Address | Size |
   |------|-----------------|------|
   | `public-subnet` | `10.0.1.0` | `/24` |
   | `private-subnet` | `10.0.2.0` | `/24` |
   | `app-subnet` | `10.0.3.0` | `/24` |

4. **Review + Create** → **Create**

### Private Subnet Delegation (MySQL için zorunlu)

1. **Virtual Networks** → `myapp-vnet` → **Subnets** → `private-subnet`
2. **Subnet delegation** → `Microsoft.DBforMySQL/flexibleServers`
3. **Save**

### App Subnet Delegation (App Service için zorunlu)

1. **Subnets** → `app-subnet`
2. **Subnet delegation** → `Microsoft.Web/serverFarms`
3. **Save**

---

## Adım 3 — Azure Database for MySQL Flexible Server

1. **Azure Database for MySQL flexible servers** → **+ Create** → **Flexible server**

2. **Basics** sekmesi:

   | Alan | Değer |
   |------|-------|
   | Resource group | `myapp-rg` |
   | Server name | `myapp-mysql` (küresel benzersiz — başına/sonuna isim ekle) |
   | Region | Aynı bölge |
   | MySQL version | `8.0` |
   | Workload type | Development |
   | Compute + storage | **Burstable, B1ms** |
   | Admin username | `adminuser` |
   | Password | Güçlü bir şifre — **Not al, sonra lazım!** |

3. **Networking** sekmesi:
   - Connectivity method: **Private access (VNet Integration)**
   - Virtual network: `myapp-vnet`
   - Subnet: `private-subnet`
   - Private DNS zone: Otomatik oluşturulur ✅

4. **Review + Create** → **Create** (3–5 dk sürebilir)

### Veritabanı Oluştur

1. MySQL server'ına git → **Databases** → **+ Add**
2. Database name: `lerniablog`
3. **Save**

### FQDN'i Kaydet

MySQL server → **Overview** → **Server name** değerini not al:
```
myapp-mysql.mysql.database.azure.com
```

---

## Adım 4 — Azure Storage Account (Blob Storage)

1. **Storage accounts** → **+ Create**

2. Ayarlar:

   | Alan | Değer |
   |------|-------|
   | Resource group | `myapp-rg` |
   | Storage account name | `myappblob12345` (küresel benzersiz, sadece küçük harf + rakam) |
   | Region | Aynı bölge |
   | Performance | Standard |
   | Redundancy | LRS |

3. **Advanced** sekmesi → **Allow Blob anonymous access**: Enabled

4. **Review + Create** → **Create**

### Container'ları Oluştur

1. Storage account → **Containers** → **+ Container**

   | Name | Public access level |
   |------|---------------------|
   | `static` | Blob |
   | `media` | Blob |

### Storage Key'i Al

1. Storage account → **Security + networking** → **Access keys**
2. **key1** → **Show** → Key değerini kopyala → **Not al!**

### Static Website (Failover sayfası)

1. Storage account → **Data management** → **Static website**
2. **Enabled** → Index document name: `index.html`
3. **Save**
4. **$web container** oluşur → içine basit bir `index.html` yükle (bakım sayfası)

---

## Adım 5 — App Service (Django Uygulaması)

### App Service Plan Oluştur

1. **App Service plans** → **+ Create**

   | Alan | Değer |
   |------|-------|
   | Resource group | `myapp-rg` |
   | Name | `myapp-plan` |
   | Operating System | Linux |
   | Region | Aynı bölge |
   | Pricing plan | **B1** (Basic, ~13 $/ay) |

2. **Review + Create** → **Create**

### Web App Oluştur

1. **App Services** → **+ Create** → **Web App**

   | Alan | Değer |
   |------|-------|
   | Resource group | `myapp-rg` |
   | Name | `myapp-blog` (küresel benzersiz — URL'in olur) |
   | Publish | Code |
   | Runtime stack | Python 3.11 |
   | Operating System | Linux |
   | Region | Aynı bölge |
   | App Service Plan | `myapp-plan` |

2. **Review + Create** → **Create**

### Environment Variables Ayarla

> Portal: App Service → **Settings** → **Environment variables** → **+ Add**

Aşağıdaki her değişkeni tek tek ekle:

| Name | Value | Kaynak |
|------|-------|--------|
| `SECRET_KEY` | `python3 -c "import secrets; print(secrets.token_urlsafe(50))"` çıktısı | Terminalden üret |
| `DB_NAME` | `lerniablog` | Sabit |
| `DB_USER` | `adminuser` | Adım 3'te belirlediğin |
| `DB_PASSWORD` | Adım 3'teki şifren | Adım 3'te not aldın |
| `DB_HOST` | `myapp-mysql.mysql.database.azure.com` | Adım 3'te not aldın |
| `AZURE_APP_HOSTNAME` | `myapp-blog.azurewebsites.net` | App Service Overview'da görünür |
| `AZURE_STORAGE_ACCOUNT_NAME` | `myappblob12345` | Adım 4'te belirlediğin |
| `AZURE_STORAGE_ACCOUNT_KEY` | Adım 4'teki key1 değeri | Adım 4'te not aldın |

Ekledikten sonra **Apply** → **Confirm**

### Startup Script Ayarla

1. App Service → **Settings** → **Configuration** → **General settings**
2. **Startup Command**: `bash /home/site/wwwroot/startup.sh`
3. **Save**

### VNet Integration (App Service → MySQL özel ağ)

1. App Service → **Settings** → **Networking** → **VNet Integration** → **Add VNet Integration**
2. Virtual Network: `myapp-vnet`
3. Subnet: `app-subnet`
4. **OK**

### Kodu Deploy Et

**Yöntem A — ZIP Deploy (en basit):**

```bash
# Terminalde (proje klasöründe)
zip -r app.zip . --exclude "*.git*" --exclude "*.env" --exclude "*.zip" --exclude "media_root/*"
az webapp deployment source config-zip \
  --resource-group myapp-rg \
  --name myapp-blog \
  --src app.zip
```

**Yöntem B — GitHub bağlantısı:**
1. App Service → **Deployment** → **Deployment Center**
2. Source: **GitHub** → Hesabını bağla → Repo ve branch seç
3. **Save**

---

## Adım 6 — Azure Function App (Blob Trigger)

1. **Function App** → **+ Create**

   | Alan | Değer |
   |------|-------|
   | Resource group | `myapp-rg` |
   | Function App name | `myapp-func` (küresel benzersiz) |
   | Runtime stack | Python |
   | Version | 3.11 |
   | Region | Aynı bölge |
   | Hosting | **App Service Plan** → `myapp-plan` seç |
   | Storage account | `myappblob12345` |

2. **Review + Create** → **Create**

### Bağlantı Ayarları

1. Function App → **Settings** → **Environment variables** → **+ Add**

   | Name | Value |
   |------|-------|
   | `AzureWebJobsStorage` | Storage account connection string |
   | `STORAGE_CONNECTION_STRING` | Storage account connection string |

   > Connection string: Storage account → **Access keys** → **Connection string** (key1)

### Function Kodu Deploy Et

```bash
cd azure/azure_function
# Azure Functions Core Tools gerekli:
npm install -g azure-functions-core-tools@4 --unsafe-perm true
func azure functionapp publish myapp-func --python
```

---

## Adım 7 — Azure CDN

1. **Front Door and CDN profiles** → **+ Create** → **Explore other offerings** → **Azure CDN Standard from Microsoft (classic)**

2. Ayarlar:

   | Alan | Değer |
   |------|-------|
   | Resource group | `myapp-rg` |
   | Name | `myapp-cdn` |
   | Pricing tier | Standard Microsoft |
   | Create CDN endpoint | ✅ İşaretle |
   | Endpoint name | `myapp-endpoint` |
   | Origin type | App Service |
   | Origin hostname | `myapp-blog.azurewebsites.net` |

3. **Create**

CDN URL: `myapp-endpoint.azureedge.net`

---

## Adım 8 — Azure Traffic Manager (Failover)

1. **Traffic Manager profiles** → **+ Create**

   | Alan | Değer |
   |------|-------|
   | Name | `myapp-traffic` (küresel benzersiz) |
   | Routing method | **Priority** |
   | Resource group | `myapp-rg` |

2. **Create**

### Primary Endpoint (App Service)

1. Traffic Manager → **Settings** → **Endpoints** → **+ Add**

   | Alan | Değer |
   |------|-------|
   | Type | Azure endpoint |
   | Name | `primary` |
   | Target resource type | App Service |
   | Target resource | `myapp-blog` |
   | Priority | `1` |

### Failover Endpoint (Static Website)

1. **+ Add**

   | Alan | Değer |
   |------|-------|
   | Type | External endpoint |
   | Name | `failover` |
   | Fully qualified domain name | Static website URL (Adım 4'te not aldın) |
   | Priority | `2` |

Traffic Manager URL: `myapp-traffic.trafficmanager.net`

---

## Doğrulama

| Test | Yapılacak |
|------|-----------|
| App Service | `https://myapp-blog.azurewebsites.net` tarayıcıda aç |
| CDN | `https://myapp-endpoint.azureedge.net` tarayıcıda aç |
| Traffic Manager | `https://myapp-traffic.trafficmanager.net` tarayıcıda aç |
| Log kontrol | App Service → **Monitoring** → **Log stream** |
| Failover testi | App Service → **Stop** → Traffic Manager'ın failover'a geçmesini bekle |

---

## Sorun Giderme

**App açılmıyor / 502 hatası:**
1. App Service → **Log stream** → Hata mesajına bak
2. Environment variables eksiksiz mi? `DB_HOST`, `SECRET_KEY`, `AZURE_STORAGE_ACCOUNT_KEY` kontrol et
3. Startup command doğru mu: `bash /home/site/wwwroot/startup.sh`

**MySQL bağlantı hatası:**
1. VNet Integration aktif mi? App Service → Networking → VNet Integration
2. Private DNS zone VNet'e bağlı mı? MySQL server → Networking → Private DNS

**Static files yüklenmiyor:**
1. Blob Storage container public access: `blob` olmalı
2. App Service environment'ta `AZURE_STORAGE_ACCOUNT_NAME` ve `AZURE_STORAGE_ACCOUNT_KEY` doğru mu?
3. Log stream'de `collectstatic` başarılı mı?

**Tüm kaynakları sil (temizlik):**
- **Resource groups** → `myapp-rg` → **Delete resource group**
