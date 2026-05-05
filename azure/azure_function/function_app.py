import azure.functions as func
import logging
import os
from azure.data.tables import TableServiceClient
from datetime import datetime, timezone

app = func.FunctionApp()


@app.blob_trigger(
    arg_name="myblob",
    path="media/{name}",
    connection="AzureWebJobsStorage"
)
def blob_trigger_handler(myblob: func.InputStream):
    """
    Azure Function equivalent of AWS Lambda + S3 trigger.
    Fires when a blob is created/updated in the 'media' container
    and logs the event to Azure Table Storage (equivalent of DynamoDB).
    """
    logging.info(
        f"Blob trigger fired — Name: {myblob.name}, Size: {myblob.length} bytes"
    )

    conn_str = os.environ["STORAGE_CONNECTION_STRING"]
    table_service = TableServiceClient.from_connection_string(conn_str=conn_str)
    table_client = table_service.get_table_client(table_name="BlobEvents")

    # Create the table if it doesn't exist yet
    try:
        table_client.create_table()
    except Exception:
        pass  # table already exists

    filename = myblob.name.split("/")[-1]
    timestamp = datetime.now(timezone.utc).isoformat()

    entity = {
        "PartitionKey": "blob",          # equivalent of DynamoDB partition
        "RowKey": filename,              # equivalent of DynamoDB 'id'
        "Timestamp": timestamp,          # equivalent of DynamoDB 'timestamp'
        "Event": "BlobCreated",          # equivalent of DynamoDB 'Event'
        "FullPath": myblob.name,
        "SizeBytes": myblob.length,
    }

    table_client.upsert_entity(entity=entity)
    logging.info(f"Written to Table Storage: {filename}")
