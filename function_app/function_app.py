import os
import json
import logging
from datetime import datetime

import azure.functions as func
import azure.durable_functions as df
from azure.storage.blob import BlobServiceClient

from langchain_community.document_loaders import PyPDFLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_openai import AzureOpenAIEmbeddings
from langchain_community.vectorstores import AzureSearch

import tempfile

UPLOADS_CONTAINER = os.environ.get("PDF_UPLOADS_CONTAINER", "pdf-uploads")
RESULTS_CONTAINER = os.environ.get("PDF_RESULTS_CONTAINER", "pdf-results")

# PDF processing configuration
CHUNK_SIZE = 1000
CHUNK_OVERLAP = 200

app = func.FunctionApp()

@app.event_grid_trigger(arg_name="event")
@app.durable_client_input(client_name="client")
async def event_grid_trigger(event: func.EventGridEvent, client: df.DurableOrchestrationClient):
    try:
        event_type = event.event_type
        
        if event_type == "Microsoft.Storage.BlobCreated":
            data = event.get_json()
            blob_url = data['url']
            blob_name = blob_url.split(f'/{UPLOADS_CONTAINER}/')[-1]
            
            # Only process PDF files
            if not blob_name.lower().endswith('.pdf'):
                logging.info(f"[EVENT GRID] Skipping non-PDF file: {blob_name}")
                return
            
            logging.info(f"[EVENT GRID] New PDF detected: {blob_name}")

            instance_id = await client.start_new("pdf_orchestrator", None, blob_name)
            logging.info(f"[EVENT GRID] Started orchestration {instance_id} for file: {blob_name}")
    
    except Exception as e:
        logging.error(f"[EVENT GRID] Error: {e}", exc_info=True)
        raise


@app.orchestration_trigger(context_name="context")
def pdf_orchestrator(context: df.DurableOrchestrationContext):

    blob_file_name = context.get_input()
    logging.info(f"[ORCHESTRATOR] Starting for: {blob_file_name}")
    
    try:
        logging.info(f"[ORCHESTRATOR] Spawning parallel tasks for {blob_file_name}")
        task1 = context.call_activity("embed_pdf_to_search", blob_file_name)
        task2 = context.call_activity("process_pdf_secondary_task", blob_file_name)
        
        # Wait for both tasks to complete
        results = yield context.task_all([task1, task2])
        
        logging.info(f"[ORCHESTRATOR] Both tasks completed for {blob_file_name}")
        
        return {
            "status": "completed",
            "file": blob_file_name,
            "embedding_result": results[0],
            "secondary_result": results[1]
        }
        
    except Exception as e:
        logging.error(f"[ORCHESTRATOR] Error processing {blob_file_name}: {e}", exc_info=True)
        raise


@app.activity_trigger(input_name="blobName")
def embed_pdf_to_search(blobName: str):
    logging.info(f"[EMBEDDING] Activity started for: {blobName}")
    
    temp_file_path = None
    try:
        # Download PDF
        logging.info(f"[EMBEDDING] Downloading {blobName} from {UPLOADS_CONTAINER}...")
        connection_string = os.environ["AzureWebJobsStorage"]
        blob_service_client = BlobServiceClient.from_connection_string(connection_string)
        blob_client = blob_service_client.get_blob_client(container=UPLOADS_CONTAINER, blob=blobName)
        
        blob_content = blob_client.download_blob().readall()
        logging.info(f"[EMBEDDING] Downloaded {len(blob_content)} bytes")

        # Save to temporary file
        with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as temp_file:
            temp_file.write(blob_content)
            temp_file_path = temp_file.name
        
        logging.info(f"[EMBEDDING] Saved to temporary file: {temp_file_path}")

        logging.info("[EMBEDDING] Extracting text from PDF...")
        loader = PyPDFLoader(temp_file_path)
        documents = loader.load()
        logging.info(f"[EMBEDDING] Loaded {len(documents)} pages")

        logging.info(f"[EMBEDDING] Splitting into chunks (size={CHUNK_SIZE}, overlap={CHUNK_OVERLAP})...")
        text_splitter = RecursiveCharacterTextSplitter(chunk_size=CHUNK_SIZE, chunk_overlap=CHUNK_OVERLAP)
        chunks = text_splitter.split_documents(documents)
        logging.info(f"[EMBEDDING] Created {len(chunks)} chunks")

        logging.info("[EMBEDDING] Initialising Azure OpenAI embeddings...")
        embeddings = AzureOpenAIEmbeddings(
            azure_deployment=os.environ["OPENAI_EMBEDDING_MODEL_NAME"],
            openai_api_key=os.environ["OPENAI_API_KEY"],
            azure_endpoint=os.environ["OPENAI_ENDPOINT"]
        )

        logging.info("[EMBEDDING] Connecting to Azure AI Search...")
        vector_store = AzureSearch(
            azure_search_endpoint=os.environ["AI_SEARCH_ENDPOINT"],
            azure_search_key=os.environ["AI_SEARCH_API_KEY"],
            index_name=os.environ["AI_SEARCH_INDEX_NAME"],
            embedding_function=embeddings.embed_query
        )
        
        logging.info(f"[EMBEDDING] Adding {len(chunks)} chunks to search index...")
        vector_store.add_documents(documents=chunks)
        logging.info("[EMBEDDING] Successfully added all chunks to search index")
        
        return f"Successfully embedded {len(chunks)} chunks into Azure Search."

    except Exception as e:
        logging.error(f"[EMBEDDING] Failed: {e}", exc_info=True)
        raise
        
    finally:
        if temp_file_path and os.path.exists(temp_file_path):
            try:
                os.remove(temp_file_path)
                logging.info(f"[EMBEDDING] Cleaned up temporary file")
            except OSError as e:
                logging.warning(f"[EMBEDDING] Cleanup failed: {e}")



@app.activity_trigger(input_name="blobName")
def process_pdf_secondary_task(blobName: str):
    logging.info(f"[ANALYSIS] Activity started for: {blobName}")
    
    temp_file_path = None
    try:
        logging.info(f"[ANALYSIS] Downloading {blobName} from {UPLOADS_CONTAINER}...")
        connection_string = os.environ["AzureWebJobsStorage"]
        blob_service_client = BlobServiceClient.from_connection_string(connection_string)
        blob_client = blob_service_client.get_blob_client(container=UPLOADS_CONTAINER, blob=blobName)
        
        blob_content = blob_client.download_blob().readall()
        logging.info(f"[ANALYSIS] Downloaded {len(blob_content)} bytes")

        with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as temp_file:
            temp_file.write(blob_content)
            temp_file_path = temp_file.name

        logging.info("[ANALYSIS] Extracting text from PDF...")
        loader = PyPDFLoader(temp_file_path)
        documents = loader.load()
        
        logging.info("[ANALYSIS] Analyzing PDF content...")
        page_count = len(documents)
        total_chars = sum(len(doc.page_content) for doc in documents)
        
        metadata = {
            "file_name": blobName,
            "page_count": page_count,
            "total_characters": total_chars,
            "processed_at": datetime.now().isoformat(),
            "status": "completed"
        }
        
        logging.info(f"[ANALYSIS] Metadata extracted: {json.dumps(metadata)}")
        
        metadata_blob_name = f"{blobName.rsplit('.', 1)[0]}_metadata.json"
        results_blob_client = blob_service_client.get_blob_client(
            container=RESULTS_CONTAINER,
            blob=metadata_blob_name
        )
        
        metadata_json = json.dumps(metadata, indent=2)
        results_blob_client.upload_blob(metadata_json, overwrite=True)
        
        logging.info(f"[ANALYSIS] Metadata stored as: {metadata_blob_name}")
        
        return f"Metadata stored: {metadata_blob_name}"

    except Exception as e:
        logging.error(f"[ANALYSIS] Failed: {e}", exc_info=True)
        raise
        
    finally:
        if temp_file_path and os.path.exists(temp_file_path):
            try:
                os.remove(temp_file_path)
                logging.info(f"[ANALYSIS] Cleaned up temporary file")
            except OSError as e:
                logging.warning(f"[ANALYSIS] Cleanup failed: {e}")



@app.route(route="startOrchestrator")
@app.durable_client_input(client_name="client")
async def http_start(req: func.HttpRequest, client: df.DurableOrchestrationClient):
    try:
        file_name = req.params.get('file')
        if not file_name:
            return func.HttpResponse("Please pass a 'file' parameter in the query string", status_code=400)

        if not file_name.lower().endswith('.pdf'):
            return func.HttpResponse("Only PDF files are supported", status_code=400)

        logging.info(f"[HTTP] Starting orchestration for: {file_name}")
        instance_id = await client.start_new("pdf_orchestrator", None, file_name)
        
        return client.create_check_status_response(req, instance_id)
        
    except Exception as e:
        logging.error(f"[HTTP] Error: {e}", exc_info=True)
        return func.HttpResponse(f"Error: {str(e)}", status_code=500)


@app.route(route="processingStatus")
@app.durable_client_input(client_name="client")
async def get_processing_status(req: func.HttpRequest, client: df.DurableOrchestrationClient):
    try:
        logging.info("[STATUS] Fetching orchestration instances...")
        instance_query = await client.get_status_all()
        
        running = []
        completed = []
        failed = []
        pending = []
        
        for instance in instance_query:
            info = {
                "instanceId": instance.instance_id,
                "status": instance.runtime_status.name,
                "input": instance.input,
                "created_time": str(instance.created_at),
                "last_updated": str(instance.last_updated_at)
            }
            
            if instance.runtime_status.name == "Running":
                running.append(info)
            elif instance.runtime_status.name == "Completed":
                completed.append(info)
            elif instance.runtime_status.name == "Failed":
                failed.append(info)
            elif instance.runtime_status.name == "Pending":
                pending.append(info)
        
        response_data = {
            "summary": {
                "running": len(running),
                "completed": len(completed),
                "failed": len(failed),
                "pending": len(pending)
            },
            "running_files": running,
            "completed_files": completed,
            "failed_files": failed,
            "pending_files": pending
        }
        
        logging.info(f"[STATUS] Retrieved status for {len(instance_query)} instances")
        
        return func.HttpResponse(
            json.dumps(response_data, indent=2),
            mimetype="application/json"
        )
    
    except Exception as e:
        logging.error(f"[STATUS] Error: {e}", exc_info=True)
        return func.HttpResponse(f"Error: {str(e)}", status_code=500)