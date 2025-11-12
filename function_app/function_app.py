import os
import json
import logging
import io
import requests
import azure.functions as func
import azure.durable_functions as df

from azure.storage.blob import BlobServiceClient
from langchain_community.document_loaders import PyPDFLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter

from langchain_openai import AzureOpenAIEmbeddings
from langchain_community.vectorstores import AzureSearch

import tempfile
import atexit

app = func.FunctionApp()

@app.route(route="hello")
def hello_world(req: func.HttpRequest) -> func.HttpResponse:
    return func.HttpResponse("Hello World!")

@app.event_grid_trigger(arg_name="event")
@app.durable_client_input(client_name="client")
async def event_grid_trigger(event: func.EventGridEvent, client: df.DurableOrchestrationClient):
    
    event_type = event.event_type
    
    if event_type == "Microsoft.Storage.BlobCreated":
        
        data = event.get_json()
        
        blob_url = data['url']

        blob_name = blob_url.split('/pdf-uploads/')[-1]
        
        logging.info(f"Processing new file: {blob_name}")

        # Pass the FILE NAME (not the URL)
        instance_id = await client.start_new("pdf_orchestrator", None, blob_name)
        logging.info(f"Started orchestration with ID = '{instance_id}'.")


@app.orchestration_trigger(context_name="context")
def pdf_orchestrator(context: df.DurableOrchestrationContext):
    
    blob_file_name = context.get_input()
    logging.info(f"Orchestrator started for: {blob_file_name}")
    
    try:
        # Pass the file name to the worker
        ai_result = yield context.call_activity("process_pdf_activity", blob_file_name)
        
        logging.info(f"Successfully processed {blob_file_name}")
        
    except Exception as e:
        logging.error(f"Error processing {blob_file_name}: {e}")
        raise


@app.activity_trigger(input_name="blobName")
def process_pdf_activity(blobName: str):
    logging.info(f"Activity started for: {blobName}")
    

    temp_file_path = None
    try:
        logging.info(f"Downloading file {blobName} from storage...")
        connection_string = os.environ["AzureWebJobsStorage"]
        blob_service_client = BlobServiceClient.from_connection_string(connection_string)
        blob_client = blob_service_client.get_blob_client(container="pdf-uploads", blob=blobName)
        
        blob_content = blob_client.download_blob().readall()
        logging.info(f"Successfully downloaded {len(blob_content)} bytes.")


        with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as temp_file:
            temp_file.write(blob_content)
            temp_file_path = temp_file.name # Get the path, e.g., /tmp/xyz.pdf
        
        logging.info(f"Saved PDF to temporary file: {temp_file_path}")

        loader = PyPDFLoader(temp_file_path)
        documents = loader.load()
        logging.info(f"Loaded {len(documents)} pages from PDF.")

        text_splitter = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=200)
        chunks = text_splitter.split_documents(documents)
        logging.info(f"Split document into {len(chunks)} chunks.")

        embeddings = AzureOpenAIEmbeddings(
            azure_deployment=os.environ["OPENAI_EMBEDDING_MODEL_NAME"],
            openai_api_key=os.environ["OPENAI_API_KEY"],
            azure_endpoint=os.environ["OPENAI_ENDPOINT"]
        )

        vector_store = AzureSearch(
            azure_search_endpoint=os.environ["AI_SEARCH_ENDPOINT"],
            azure_search_key=os.environ["AI_SEARCH_API_KEY"],
            index_name=os.environ["AI_SEARCH_INDEX_NAME"],
            embedding_function=embeddings.embed_query
        )
        
        vector_store.add_documents(documents=chunks)
        
        return f"Successfully processed and embedded {len(chunks)} chunks."

    except Exception as e:
        logging.error(f"Failed to process blob: {e}")
        raise
        
    finally:
        if temp_file_path and os.path.exists(temp_file_path):
            logging.info(f"Cleaning up temporary file: {temp_file_path}")
            os.remove(temp_file_path)


# THE HTTP STARTER (For Local Testing)
@app.route(route="startOrchestrator")
@app.durable_client_input(client_name="client")
async def http_start(req: func.HttpRequest, client: df.DurableOrchestrationClient):
    
    # Get the file name from the query string
    file_name = req.params.get('file')
    if not file_name:
        return func.HttpResponse("Please pass a 'file' parameter in the query string", status_code=400)

    logging.info(f"HTTP Starter manually triggering for: {file_name}")

    # Start the "Manager" and pass the FILE NAME
    instance_id = await client.start_new("pdf_orchestrator", None, file_name)
    
    return client.create_check_status_response(req, instance_id)