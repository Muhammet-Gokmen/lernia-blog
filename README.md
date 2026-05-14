# Django Blog App — Azure Student Deployment

Django blog app deployed on Azure — App Service, MySQL, Blob Storage, CDN, Traffic Manager, Azure Functions

## Mimari

```
Internet → Azure Traffic Manager (Failover)
               ↓
          Azure CDN
               ↓
        Azure App Service  (Django / Gunicorn)
       /         |          \
Azure MySQL   Azure Blob   Azure Function
(Flexible)    Storage      (Blob Trigger)
              (media/static)     |
                          Azure Table Storage
```

## Azure Servis Karşılıkları (AWS → Azure)

| AWS | Azure |
|-----|-------|
| VPC | Virtual Network (VNet) |
| EC2 Auto Scaling Group | App Service + Auto Scale |
| Application Load Balancer | App Service (yerleşik) |
| RDS MySQL | Azure Database for MySQL Flexible Server |
| S3 | Azure Blob Storage |
| CloudFront | Azure CDN |
| Route 53 + Failover | Azure Traffic Manager |
| Lambda | Azure Functions |
| DynamoDB | Azure Table Storage |

## Hızlı Başlangıç

### 1. Gereksinimler

- [Azure for Students hesabı](https://azure.microsoft.com/en-us/free/students/) ($100 ücretsiz kredi)
- [Azure CLI](https://learn.microsoft.com/en-us/cli/azure/install-azure-cli)
- Python 3.11+

### 2. Environment Variables

`azure/src/.env.example` dosyasını `src/.env` olarak kopyalayıp doldurun:

```bash
cp azure/src/.env.example src/.env
```

Doldurulması gerekenler:
| Değişken | Kaynak |
|----------|--------|
| `SECRET_KEY` | `python -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"` |
| `DB_PASSWORD` | Azure MySQL oluştururken belirlediğiniz şifre |
| `DB_HOST` | Azure MySQL → Overview → Server name (FQDN) |
| `DB_NAME` | `lerniablog` |
| `DB_USER` | `adminuser` |
| `AZURE_APP_HOSTNAME` | App Service → Overview → Default domain |
| `AZURE_STORAGE_ACCOUNT_NAME` | Storage Account adınız |
| `AZURE_STORAGE_ACCOUNT_KEY` | Storage Account → Access keys → key1 |

### 3. Deployment Rehberleri

| Rehber | Açıklama |
|--------|----------|
| [azure/PORTAL_SOLUTION.md](azure/PORTAL_SOLUTION.md) | Azure Portal üzerinden adım adım kurulum |
| [azure/CLI_SOLUTION.md](azure/CLI_SOLUTION.md) | Bash terminalde Azure CLI ile tam otomatik kurulum |

## Proje Yapısı

```
lernia_project/
├── src/                    # Django uygulaması
│   ├── cblog/              # Proje ayarları (settings.py, storages.py)
│   ├── blog/               # Blog uygulaması
│   ├── users/              # Kullanıcı yönetimi
│   └── manage.py
├── azure/                  # Azure deployment dosyaları
│   ├── README_cli_solution.md      # CLI rehberi
│   ├── README_solution_student.md  # Portal rehberi
│   ├── requirements.txt            # Python bağımlılıkları
│   ├── startup.sh                  # App Service başlatma scripti
│   ├── azure_function/             # Azure Function (Blob Trigger)
│   └── src/.env.example            # Environment variables şablonu
├── startup.sh              # App Service startup script
├── requirements.txt        # Python bağımlılıkları
└── .gitignore
```

## Önemli Notlar

- `src/.env` dosyasını **asla** git'e commit etmeyin
- Azure App Service'te environment variables'ları **Configuration → Application settings** üzerinden ayarlayın
- MySQL SSL bağlantısı zorunludur (`DigiCertGlobalRootCA.crt.pem` App Service'te hazır gelir)
