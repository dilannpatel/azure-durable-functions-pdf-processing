import os
import json
import logging
import azure.functions as func
import azure.durable_functions as df

from azure.storage.blob import BlobServiceClient
from langchain_community.document_loaders import PyPDFLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_openai import AzureOpenAIEmbeddings
from langchain_community.vectorstores import AzureSearch

import tempfile

app = func.FunctionApp()

@app.event_grid_trigger(arg_name="event")
@app.durable_client_input(client_name="client")
async def event_grid_trigger(event: func.EventGridEvent, client: df.DurableOrchestrationClient):
    
    event_type = event.event_type
    
    if event_type == "Microsoft.Storage.BlobCreated":
        data = event.get_json()
        blob_url = data['url']
        blob_name = blob_url.split('/pdf-uploads/')[-1]
        
        # Only process PDF files
        if not blob_name.lower().endswith('.pdf'):
            logging.info(f"[EVENT GRID] Skipping non-PDF file: {blob_name}")
            return
        
        logging.info(f"[EVENT GRID] New PDF detected: {blob_name}")

        instance_id = await client.start_new("pdf_orchestrator", None, blob_name)
        logging.info(f"[EVENT GRID] Started orchestration with ID = '{instance_id}' for file: {blob_name}")



@app.orchestration_trigger(context_name="context")
def pdf_orchestrator(context: df.DurableOrchestrationContext):
    
    blob_file_name = context.get_input()
    logging.info(f"[ORCHESTRATOR] Starting for: {blob_file_name}")
    
    try:
        # Run both tasks in PARALLEL
        logging.info(f"[ORCHESTRATOR] Spawning parallel tasks for {blob_file_name}")
        task1 = context.call_activity("embed_pdf_to_search", blob_file_name)
        task2 = context.call_activity("process_pdf_secondary_task", blob_file_name)
        
        # Wait for both to complete
        results = yield context.task_all([task1, task2])
        
        logging.info(f"[ORCHESTRATOR] Both tasks completed for {blob_file_name}")
        
        return {
            "status": "completed",
            "file": blob_file_name,
            "embedding_result": results[0],
            "secondary_result": results[1]
        }
        
    except Exception as e:
        logging.error(f"[ORCHESTRATOR] Error processing {blob_file_name}: {e}")
        raise



@app.activity_trigger(input_name="blobName")
def embed_pdf_to_search(blobName: str):
    """Activity 1: Download PDF, chunk it, and embed into Azure AI Search"""
    logging.info(f"Embedding activity started for: {blobName}")
    
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
            temp_file_path = temp_file.name
        
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
        
        return f"Successfully embedded {len(chunks)} chunks into Azure Search."

    except Exception as e:
        logging.error(f"Failed to embed PDF: {e}")
        raise
        
    finally:
        if temp_file_path and os.path.exists(temp_file_path):
            logging.info(f"Cleaning up temporary file: {temp_file_path}")
            os.remove(temp_file_path)


@app.activity_trigger(input_name="blobName")
def process_pdf_secondary_task(blobName: str):
    """Activity 2: Extract metadata and store in pdf-results container"""
    logging.info(f"[SECONDARY TASK] Started for: {blobName}")
    
    temp_file_path = None
    try:
        logging.info(f"[SECONDARY TASK] Downloading file {blobName} from storage...")
        connection_string = os.environ["AzureWebJobsStorage"]
        blob_service_client = BlobServiceClient.from_connection_string(connection_string)
        blob_client = blob_service_client.get_blob_client(container="pdf-uploads", blob=blobName)
        
        blob_content = blob_client.download_blob().readall()
        logging.info(f"[SECONDARY TASK] Downloaded {len(blob_content)} bytes.")

        # Save to temp file
        with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as temp_file:
            temp_file.write(blob_content)
            temp_file_path = temp_file.name

        # Load PDF
        loader = PyPDFLoader(temp_file_path)
        documents = loader.load()
        
        # Extract metadata
        page_count = len(documents)
        total_chars = sum(len(doc.page_content) for doc in documents)
        
        from datetime import datetime
        metadata = {
            "file_name": blobName,
            "page_count": page_count,
            "total_characters": total_chars,
            "processed_at": datetime.now().isoformat(),
            "status": "completed"
        }
        
        logging.info(f"[SECONDARY TASK] Metadata extracted: {metadata}")
        
        # Store metadata as JSON in pdf-results container
        metadata_blob_name = f"{blobName.rsplit('.', 1)[0]}_metadata.json"
        results_blob_client = blob_service_client.get_blob_client(
            container="pdf-results",
            blob=metadata_blob_name
        )
        
        metadata_json = json.dumps(metadata, indent=2)
        results_blob_client.upload_blob(metadata_json, overwrite=True)
        
        logging.info(f"[SECONDARY TASK] Metadata stored as: {metadata_blob_name}")
        
        return f"Metadata stored: {metadata_blob_name}"

    except Exception as e:
        logging.error(f"[SECONDARY TASK] Failed: {e}")
        raise
        
    finally:
        if temp_file_path and os.path.exists(temp_file_path):
            logging.info(f"[SECONDARY TASK] Cleaning up temporary file: {temp_file_path}")
            os.remove(temp_file_path)


# HTTP starter (for manual testing)
@app.route(route="startOrchestrator")
@app.durable_client_input(client_name="client")
async def http_start(req: func.HttpRequest, client: df.DurableOrchestrationClient):
    
    file_name = req.params.get('file')
    if not file_name:
        return func.HttpResponse("Please pass a 'file' parameter in the query string", status_code=400)

    logging.info(f"HTTP Starter manually triggering for: {file_name}")

    instance_id = await client.start_new("pdf_orchestrator", None, file_name)
    
    return client.create_check_status_response(req, instance_id)


# NEW: Get status of all running/completed instances
@app.route(route="processingStatus")
@app.durable_client_input(client_name="client")
async def get_processing_status(req: func.HttpRequest, client: df.DurableOrchestrationClient):
    """
    Returns status of all active and recent processing instances.
    Shows which files are currently being processed.
    """
    try:
        # Get all instances from the past 24 hours
        instance_query = await client.get_status_all()
        
        # Organize by status
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
        
        return func.HttpResponse(
            json.dumps({
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
            }, indent=2),
            mimetype="application/json"
        )
    
    except Exception as e:
        logging.error(f"Error getting status: {e}")
        return func.HttpResponse(f"Error: {str(e)}", status_code=500)


# import os
# import json
# import logging
# import io
# import requests
# import azure.functions as func
# import azure.durable_functions as df

# from azure.storage.blob import BlobServiceClient
# from langchain_community.document_loaders import PyPDFLoader
# from langchain_text_splitters import RecursiveCharacterTextSplitter

# from langchain_openai import AzureOpenAIEmbeddings
# from langchain_community.vectorstores import AzureSearch

# import tempfile
# import atexit

# app = func.FunctionApp()

# @app.event_grid_trigger(arg_name="event")
# @app.durable_client_input(client_name="client")
# async def event_grid_trigger(event: func.EventGridEvent, client: df.DurableOrchestrationClient):
    
#     event_type = event.event_type
    
#     if event_type == "Microsoft.Storage.BlobCreated":
        
#         data = event.get_json()
        
#         blob_url = data['url']

#         blob_name = blob_url.split('/pdf-uploads/')[-1]
        
#         logging.info(f"Processing new file: {blob_name}")

#         # Pass the FILE NAME (not the URL)
#         instance_id = await client.start_new("pdf_orchestrator", None, blob_name)
#         logging.info(f"Started orchestration with ID = '{instance_id}'.")


# @app.orchestration_trigger(context_name="context")
# def pdf_orchestrator(context: df.DurableOrchestrationContext):
    
#     blob_file_name = context.get_input()
#     logging.info(f"Orchestrator started for: {blob_file_name}")
    
#     try:
#         # Pass the file name to the worker
#         ai_result = yield context.call_activity("process_pdf", blob_file_name)
        
#         logging.info(f"Successfully processed {blob_file_name}")
        
#     except Exception as e:
#         logging.error(f"Error processing {blob_file_name}: {e}")
#         raise


# @app.activity_trigger(input_name="blobName")
# def process_pdf(blobName: str):
#     logging.info(f"Activity started for: {blobName}")
    

#     temp_file_path = None
#     try:
#         logging.info(f"Downloading file {blobName} from storage...")
#         connection_string = os.environ["AzureWebJobsStorage"]
#         blob_service_client = BlobServiceClient.from_connection_string(connection_string)
#         blob_client = blob_service_client.get_blob_client(container="pdf-uploads", blob=blobName)
        
#         blob_content = blob_client.download_blob().readall()
#         logging.info(f"Successfully downloaded {len(blob_content)} bytes.")


#         with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as temp_file:
#             temp_file.write(blob_content)
#             temp_file_path = temp_file.name # Get the path, e.g., /tmp/xyz.pdf
        
#         logging.info(f"Saved PDF to temporary file: {temp_file_path}")

#         loader = PyPDFLoader(temp_file_path)
#         documents = loader.load()
#         logging.info(f"Loaded {len(documents)} pages from PDF.")

#         text_splitter = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=200)
#         chunks = text_splitter.split_documents(documents)
#         logging.info(f"Split document into {len(chunks)} chunks.")

#         embeddings = AzureOpenAIEmbeddings(
#             azure_deployment=os.environ["OPENAI_EMBEDDING_MODEL_NAME"],
#             openai_api_key=os.environ["OPENAI_API_KEY"],
#             azure_endpoint=os.environ["OPENAI_ENDPOINT"]
#         )

#         vector_store = AzureSearch(
#             azure_search_endpoint=os.environ["AI_SEARCH_ENDPOINT"],
#             azure_search_key=os.environ["AI_SEARCH_API_KEY"],
#             index_name=os.environ["AI_SEARCH_INDEX_NAME"],
#             embedding_function=embeddings.embed_query
#         )
        
#         vector_store.add_documents(documents=chunks)
        
#         return f"Successfully processed and embedded {len(chunks)} chunks."

#     except Exception as e:
#         logging.error(f"Failed to process blob: {e}")
#         raise
        
#     finally:
#         if temp_file_path and os.path.exists(temp_file_path):
#             logging.info(f"Cleaning up temporary file: {temp_file_path}")
#             os.remove(temp_file_path)


# # THE HTTP STARTER (For Local Testing)
# @app.route(route="startOrchestrator")
# @app.durable_client_input(client_name="client")
# async def http_start(req: func.HttpRequest, client: df.DurableOrchestrationClient):
    
#     # Get the file name from the query string
#     file_name = req.params.get('file')
#     if not file_name:
#         return func.HttpResponse("Please pass a 'file' parameter in the query string", status_code=400)

#     logging.info(f"HTTP Starter manually triggering for: {file_name}")

#     # Start the "Manager" and pass the FILE NAME
#     instance_id = await client.start_new("pdf_orchestrator", None, file_name)
    
#     return client.create_check_status_response(req, instance_id)