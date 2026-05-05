from storages.backends.azure_storage import AzureStorage

class AzureMediaStorage(AzureStorage):
    azure_container = 'media'
    overwrite_files = False
