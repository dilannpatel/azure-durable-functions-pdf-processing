# import os
# import json
# import logging
# from datetime import datetime
# from dataclasses import dataclass
# from typing import Optional, Any

# import azure.functions as func
# import azure.durable_functions as df
# from azure.storage.blob import BlobServiceClient

# from langchain_community.document_loaders import PyPDFLoader
# from langchain_ollama import OllamaEmbeddings, OllamaLLM
# from langchain_core.tools import tool, StructuredTool
# from langchain.agents import AgentExecutor, create_react_agent
# from langchain import hub

# UPLOADS_CONTAINER = os.environ.get("FILE_UPLOADS_CONTAINER", "file-uploads")
# RESULTS_CONTAINER = os.environ.get("FILE_RESULTS_CONTAINER", "file-results")

# OLLAMA_BASE_URL = os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434")
# OLLAMA_EMBEDDING_MODEL = os.environ.get("OLLAMA_EMBEDDING_MODEL", "nomic-embed-text")
# OLLAMA_LLM_MODEL = os.environ.get("OLLAMA_LLM_MODEL", "mistral")

# app = func.FunctionApp()


# # ============================================================================
# # Dependency Injection: Orchestration Context Wrapper
# # ============================================================================

# @dataclass
# class OrchestrationContext:
#     """
#     Wrapper for Durable Orchestration context.
#     Provides a clean interface for calling activities.
#     This is passed to LangChain tools via dependency injection.
#     """
#     durable_context: df.DurableOrchestrationContext
#     filename: str
    
#     def call_activity(self, activity_name: str, input_: Any = None) -> Any:
#         """
#         Call a Durable Function activity.
#         Wraps context.call_activity() for clean separation of concerns.
#         """
#         logging.info(f"[CONTEXT] Calling activity '{activity_name}' with input: {input_}")
#         try:
#             result = self.durable_context.call_activity(activity_name, input_)
#             logging.info(f"[CONTEXT] Activity '{activity_name}' returned: {result}")
#             return result
#         except Exception as e:
#             logging.error(f"[CONTEXT] Activity '{activity_name}' failed: {e}")
#             raise


# # ============================================================================
# # LangChain Tools with Dependency Injection
# # ============================================================================

# def create_file_processing_tools(orch_context: OrchestrationContext):
#     """
#     Factory function that creates tools with injected orchestration context.
#     This is the clean production pattern - tools are created with their dependencies.
#     """
    
#     @tool
#     def process_cv_pdf(filename: str) -> str:
#         """
#         Process a CV PDF file.
#         Extracts candidate info, skills, experience, education.
#         """
#         logging.info(f"[TOOL] process_cv_pdf called for {filename}")
#         try:
#             result = orch_context.call_activity("analyze_cv_activity", filename)
#             return json.dumps({
#                 "status": "success",
#                 "tool": "process_cv_pdf",
#                 "result": result
#             })
#         except Exception as e:
#             return json.dumps({
#                 "status": "error",
#                 "tool": "process_cv_pdf",
#                 "error": str(e)
#             })
    
#     @tool
#     def process_report_pdf(filename: str) -> str:
#         """
#         Process a report PDF file.
#         Extracts key sections, summary, tables.
#         """
#         logging.info(f"[TOOL] process_report_pdf called for {filename}")
#         try:
#             result = orch_context.call_activity("analyze_report_activity", filename)
#             return json.dumps({
#                 "status": "success",
#                 "tool": "process_report_pdf",
#                 "result": result
#             })
#         except Exception as e:
#             return json.dumps({
#                 "status": "error",
#                 "tool": "process_report_pdf",
#                 "error": str(e)
#             })
    
#     @tool
#     def process_image_file(filename: str) -> str:
#         """
#         Process an image file.
#         Analyzes image content, extracts text (OCR), identifies objects.
#         """
#         logging.info(f"[TOOL] process_image_file called for {filename}")
#         try:
#             result = orch_context.call_activity("analyze_image_activity", filename)
#             return json.dumps({
#                 "status": "success",
#                 "tool": "process_image_file",
#                 "result": result
#             })
#         except Exception as e:
#             return json.dumps({
#                 "status": "error",
#                 "tool": "process_image_file",
#                 "error": str(e)
#             })
    
#     @tool
#     def process_text_file(filename: str) -> str:
#         """
#         Process a text file.
#         Analyzes content, extracts entities, summarizes.
#         """
#         logging.info(f"[TOOL] process_text_file called for {filename}")
#         try:
#             result = orch_context.call_activity("analyze_text_activity", filename)
#             return json.dumps({
#                 "status": "success",
#                 "tool": "process_text_file",
#                 "result": result
#             })
#         except Exception as e:
#             return json.dumps({
#                 "status": "error",
#                 "tool": "process_text_file",
#                 "error": str(e)
#             })
    
#     @tool
#     def embed_file_to_vector_store(filename: str) -> str:
#         """
#         Embed file content into vector store for semantic search.
#         Works with any file type.
#         """
#         logging.info(f"[TOOL] embed_file_to_vector_store called for {filename}")
#         try:
#             result = orch_context.call_activity("embed_file_activity", filename)
#             return json.dumps({
#                 "status": "success",
#                 "tool": "embed_file_to_vector_store",
#                 "result": result
#             })
#         except Exception as e:
#             return json.dumps({
#                 "status": "error",
#                 "tool": "embed_file_to_vector_store",
#                 "error": str(e)
#             })
    
#     return [
#         process_cv_pdf,
#         process_report_pdf,
#         process_image_file,
#         process_text_file,
#         embed_file_to_vector_store
#     ]


# # ============================================================================
# # LangChain Agent Factory
# # ============================================================================

# def create_file_orchestration_agent(tools: list):
#     """
#     Factory function to create the ReAct agent with injected tools.
    
#     Args:
#         tools: List of LangChain tools with injected orchestration context
    
#     Returns:
#         AgentExecutor instance
#     """
#     llm = OllamaLLM(
#         base_url=OLLAMA_BASE_URL,
#         model=OLLAMA_LLM_MODEL,
#         temperature=0
#     )
    
#     prompt = hub.pull("hwchase17/react")
#     agent = create_react_agent(llm, tools, prompt)
    
#     agent_executor = AgentExecutor(
#         agent=agent,
#         tools=tools,
#         verbose=True,
#         max_iterations=10,
#         handle_parsing_errors=True
#     )
    
#     return agent_executor


# def analyze_file_with_agent(filename: str, orch_context: OrchestrationContext) -> dict:
#     """
#     Main orchestration function that uses LangChain agent to decide processing pipeline.
    
#     Args:
#         filename: Name of the file to process
#         orch_context: Injected orchestration context
    
#     Returns:
#         Dictionary with analysis results
#     """
#     logging.info(f"[AGENT] Creating tools with injected context for {filename}")
    
#     # Create tools with dependency injection
#     tools = create_file_processing_tools(orch_context)
    
#     # Create agent with tools
#     agent = create_file_orchestration_agent(tools)
    
#     # Determine file type from extension
#     file_ext = filename.rsplit('.', 1)[-1].lower() if '.' in filename else 'unknown'
    
#     # Agent prompt - minimal, lets agent decide
#     prompt = f"""Process this file optimally: {filename}
    
# File extension: {file_ext}

# Analyze the file type and use appropriate tools:
# - CV PDFs: use process_cv_pdf
# - Report PDFs: use process_report_pdf
# - Images: use process_image_file
# - Text files: use process_text_file
# - For embeddings: use embed_file_to_vector_store

# Decide the best processing pipeline for this file."""
    
#     try:
#         logging.info(f"[AGENT] Starting orchestration for {filename}")
#         result = agent.invoke({"input": prompt})
        
#         logging.info(f"[AGENT] Orchestration complete for {filename}")
        
#         return {
#             "status": "completed",
#             "file": filename,
#             "file_type": file_ext,
#             "analysis": result.get("output", ""),
#             "processed_at": datetime.now().isoformat()
#         }
#     except Exception as e:
#         logging.error(f"[AGENT] Orchestration failed: {e}", exc_info=True)
#         return {
#             "status": "failed",
#             "file": filename,
#             "error": str(e),
#             "processed_at": datetime.now().isoformat()
#         }


# # ============================================================================
# # Event Grid Trigger
# # ============================================================================

# @app.event_grid_trigger(arg_name="event")
# @app.durable_client_input(client_name="client")
# async def event_grid_trigger(event: func.EventGridEvent, client: df.DurableOrchestrationClient):
#     """Triggered when ANY file is uploaded to file-uploads container."""
#     try:
#         event_type = event.event_type
        
#         if event_type == "Microsoft.Storage.BlobCreated":
#             data = event.get_json()
#             blob_url = data['url']
#             blob_name = blob_url.split(f'/{UPLOADS_CONTAINER}/')[-1]
            
#             logging.info(f"[EVENT GRID] File detected: {blob_name}")
            
#             # Start orchestrator for this file
#             instance_id = await client.start_new("file_orchestrator", None, blob_name)
#             logging.info(f"[EVENT GRID] Started orchestration {instance_id} for file: {blob_name}")
    
#     except Exception as e:
#         logging.error(f"[EVENT GRID] Error: {e}", exc_info=True)
#         raise


# # ============================================================================
# # Durable Orchestrator
# # ============================================================================

# @app.orchestration_trigger(context_name="context")
# def file_orchestrator(context: df.DurableOrchestrationContext):
#     """
#     Main orchestrator for file processing.
#     Delegates to LangChain agent via activity, passing context cleanly.
#     """
#     filename = context.get_input()
#     logging.info(f"[ORCHESTRATOR] Starting for: {filename}")
    
#     try:
#         # Call the agent activity, passing the filename
#         # The activity will handle the LangChain orchestration
#         result = yield context.call_activity("langchain_orchestration_activity", filename)
        
#         logging.info(f"[ORCHESTRATOR] File processing completed for {filename}")
        
#         return {
#             "status": "completed",
#             "file": filename,
#             "result": result
#         }
        
#     except Exception as e:
#         logging.error(f"[ORCHESTRATOR] Error: {e}", exc_info=True)
#         raise


# # ============================================================================
# # Activity: LangChain Orchestration
# # ============================================================================

# @app.activity_trigger(input_name="filename")
# def langchain_orchestration_activity(filename: str, context: df.DurableActivityContext):
#     """
#     Activity that runs the LangChain agent with injected orchestration context.
#     This is a production-clean pattern using dependency injection.
    
#     The key difference from the global variable approach:
#     - Context is passed via function parameter (not global)
#     - Tools receive context via factory function (not global)
#     - Clean separation of concerns
#     - Thread-safe and testable
#     """
#     logging.info(f"[ACTIVITY] LangChain orchestration started for: {filename}")
    
#     try:
#         # Create the orchestration context wrapper
#         # This contains the durable context that tools will use
#         orch_context = OrchestrationContext(
#             durable_context=context,
#             filename=filename
#         )
        
#         # Run the LangChain agent with injected context
#         # The agent will call tools, which will call activities
#         result = analyze_file_with_agent(filename, orch_context)
        
#         # Store result to blob storage
#         store_result_to_blob(filename, result)
        
#         return result
    
#     except Exception as e:
#         logging.error(f"[ACTIVITY] LangChain orchestration failed: {e}", exc_info=True)
#         raise


# # ============================================================================
# # Specialized Processing Activities
# # ============================================================================

# @app.activity_trigger(input_name="filename")
# def analyze_cv_activity(filename: str):
#     """Activity for CV PDF analysis."""
#     logging.info(f"[CV ACTIVITY] Analyzing CV: {filename}")
    
#     try:
#         # Download and analyze CV
#         connection_string = os.environ["AzureWebJobsStorage"]
#         blob_service_client = BlobServiceClient.from_connection_string(connection_string)
#         blob_client = blob_service_client.get_blob_client(container=UPLOADS_CONTAINER, blob=filename)
        
#         blob_content = blob_client.download_blob().readall()
#         logging.info(f"[CV ACTIVITY] Downloaded {len(blob_content)} bytes")
        
#         # TODO: Implement actual CV analysis
#         result = {
#             "file": filename,
#             "type": "CV",
#             "status": "analyzed",
#             "message": "CV extracted and analyzed",
#             "timestamp": datetime.now().isoformat()
#         }
        
#         return json.dumps(result)
    
#     except Exception as e:
#         logging.error(f"[CV ACTIVITY] Failed: {e}", exc_info=True)
#         raise


# @app.activity_trigger(input_name="filename")
# def analyze_report_activity(filename: str):
#     """Activity for report PDF analysis."""
#     logging.info(f"[REPORT ACTIVITY] Analyzing report: {filename}")
    
#     try:
#         # TODO: Implement actual report analysis
#         result = {
#             "file": filename,
#             "type": "Report",
#             "status": "analyzed",
#             "message": "Report extracted and analyzed",
#             "timestamp": datetime.now().isoformat()
#         }
        
#         return json.dumps(result)
    
#     except Exception as e:
#         logging.error(f"[REPORT ACTIVITY] Failed: {e}", exc_info=True)
#         raise


# @app.activity_trigger(input_name="filename")
# def analyze_image_activity(filename: str):
#     """Activity for image analysis."""
#     logging.info(f"[IMAGE ACTIVITY] Analyzing image: {filename}")
    
#     try:
#         # TODO: Implement actual image analysis (OCR, object detection, etc)
#         result = {
#             "file": filename,
#             "type": "Image",
#             "status": "analyzed",
#             "message": "Image analyzed",
#             "timestamp": datetime.now().isoformat()
#         }
        
#         return json.dumps(result)
    
#     except Exception as e:
#         logging.error(f"[IMAGE ACTIVITY] Failed: {e}", exc_info=True)
#         raise


# @app.activity_trigger(input_name="filename")
# def analyze_text_activity(filename: str):
#     """Activity for text file analysis."""
#     logging.info(f"[TEXT ACTIVITY] Analyzing text file: {filename}")
    
#     try:
#         # TODO: Implement actual text analysis
#         result = {
#             "file": filename,
#             "type": "Text",
#             "status": "analyzed",
#             "message": "Text file analyzed",
#             "timestamp": datetime.now().isoformat()
#         }
        
#         return json.dumps(result)
    
#     except Exception as e:
#         logging.error(f"[TEXT ACTIVITY] Failed: {e}", exc_info=True)
#         raise


# @app.activity_trigger(input_name="filename")
# def embed_file_activity(filename: str):
#     """Activity to embed file content into vector store."""
#     logging.info(f"[EMBED ACTIVITY] Embedding file: {filename}")
    
#     try:
#         # TODO: Implement actual embedding logic
#         result = {
#             "file": filename,
#             "status": "embedded",
#             "message": "File embedded to vector store",
#             "timestamp": datetime.now().isoformat()
#         }
        
#         return json.dumps(result)
    
#     except Exception as e:
#         logging.error(f"[EMBED ACTIVITY] Failed: {e}", exc_info=True)
#         raise


# # ============================================================================
# # Helper Functions
# # ============================================================================

# def store_result_to_blob(filename: str, result: dict):
#     """
#     Store analysis result to blob storage.
    
#     Args:
#         filename: Original filename
#         result: Analysis result dictionary
#     """
#     try:
#         connection_string = os.environ["AzureWebJobsStorage"]
#         blob_service_client = BlobServiceClient.from_connection_string(connection_string)
        
#         result_filename = f"{filename.rsplit('.', 1)[0]}_analysis.json"
#         blob_client = blob_service_client.get_blob_client(
#             container=RESULTS_CONTAINER,
#             blob=result_filename
#         )
        
#         result_json = json.dumps(result, indent=2)
#         blob_client.upload_blob(result_json, overwrite=True)
        
#         logging.info(f"[STORAGE] Result stored: {result_filename}")
    
#     except Exception as e:
#         logging.error(f"[STORAGE] Failed to store result: {e}")
#         # Don't raise - storage failure shouldn't fail the whole orchestration


# # ============================================================================
# # HTTP Endpoints
# # ============================================================================

# @app.route(route="processingStatus")
# @app.durable_client_input(client_name="client")
# async def get_processing_status(req: func.HttpRequest, client: df.DurableOrchestrationClient):
#     """Check status of orchestrations."""
#     try:
#         logging.info("[STATUS] Fetching orchestration instances...")
#         instance_query = await client.get_status_all()
        
#         running = []
#         completed = []
#         failed = []
        
#         for instance in instance_query:
#             info = {
#                 "instanceId": instance.instance_id,
#                 "status": instance.runtime_status.name,
#                 "input": instance.input,
#                 "created_time": str(instance.created_at),
#                 "last_updated": str(instance.last_updated_at)
#             }
            
#             if instance.runtime_status.name == "Running":
#                 running.append(info)
#             elif instance.runtime_status.name == "Completed":
#                 completed.append(info)
#             elif instance.runtime_status.name == "Failed":
#                 failed.append(info)
        
#         response_data = {
#             "summary": {
#                 "running": len(running),
#                 "completed": len(completed),
#                 "failed": len(failed)
#             },
#             "running": running,
#             "completed": completed,
#             "failed": failed
#         }
        
#         return func.HttpResponse(
#             json.dumps(response_data, indent=2),
#             mimetype="application/json"
#         )
    
#     except Exception as e:
#         logging.error(f"[STATUS] Error: {e}", exc_info=True)
#         return func.HttpResponse(f"Error: {str(e)}", status_code=500)


import os
import json
import logging
import tempfile
from datetime import datetime
from dataclasses import dataclass
from typing import Any

import azure.functions as func
import azure.durable_functions as df
from azure.storage.blob import BlobServiceClient

from langchain_community.document_loaders import PyPDFLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_ollama import OllamaEmbeddings, OllamaLLM
from langchain_core.tools import tool
from langchain_core.documents import Document
from langchain.agents import AgentExecutor, create_react_agent
from langchain_community.vectorstores import FAISS
from langchain import hub

UPLOADS_CONTAINER = os.environ.get("FILE_UPLOADS_CONTAINER", "pdf-uploads")
RESULTS_CONTAINER = os.environ.get("FILE_RESULTS_CONTAINER", "pdf-results")

CHUNK_SIZE = 1000
CHUNK_OVERLAP = 200

OLLAMA_BASE_URL = os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434")
OLLAMA_EMBEDDING_MODEL = os.environ.get("OLLAMA_EMBEDDING_MODEL", "nomic-embed-text")
OLLAMA_LLM_MODEL = os.environ.get("OLLAMA_LLM_MODEL", "mistral")

app = func.FunctionApp()


# ============================================================================
# Dependency Injection: Orchestration Context
# ============================================================================

@dataclass
class OrchestrationContext:
    """Wrapper for Durable Orchestration context with dependency injection."""
    durable_context: df.DurableOrchestrationContext
    filename: str
    
    def call_activity(self, activity_name: str, input_: Any = None) -> Any:
        """Call a Durable Function activity."""
        logging.info(f"[CONTEXT] Calling activity '{activity_name}' with input: {input_}")
        try:
            result = self.durable_context.call_activity(activity_name, input_)
            logging.info(f"[CONTEXT] Activity '{activity_name}' returned: {result}")
            return result
        except Exception as e:
            logging.error(f"[CONTEXT] Activity '{activity_name}' failed: {e}")
            raise


# ============================================================================
# LangChain Tools with Dependency Injection
# ============================================================================

def create_file_processing_tools(orch_context: OrchestrationContext):
    """Factory function that creates tools with injected orchestration context."""
    
    @tool
    def process_cv_pdf(filename: str) -> str:
        """Process a CV PDF file."""
        logging.info(f"[TOOL] process_cv_pdf called for {filename}")
        try:
            # Call activity - this returns a Task that will be resolved
            task = orch_context.call_activity("analyze_cv_activity", filename)
            # Task is a durable function task - convert to string for LangChain
            result = str(task) if task else "Processing CV..."
            return json.dumps({
                "status": "success",
                "tool": "process_cv_pdf",
                "message": "CV analysis queued",
                "result": result
            })
        except Exception as e:
            logging.error(f"[TOOL] process_cv_pdf error: {e}")
            return json.dumps({
                "status": "error",
                "tool": "process_cv_pdf",
                "error": str(e)
            })
    
    @tool
    def process_report_pdf(filename: str) -> str:
        """Process a report PDF file."""
        logging.info(f"[TOOL] process_report_pdf called for {filename}")
        try:
            task = orch_context.call_activity("analyze_report_activity", filename)
            result = str(task) if task else "Processing report..."
            return json.dumps({
                "status": "success",
                "tool": "process_report_pdf",
                "message": "Report analysis queued",
                "result": result
            })
        except Exception as e:
            logging.error(f"[TOOL] process_report_pdf error: {e}")
            return json.dumps({
                "status": "error",
                "tool": "process_report_pdf",
                "error": str(e)
            })
    
    @tool
    def process_image_file(filename: str) -> str:
        """Process an image file."""
        logging.info(f"[TOOL] process_image_file called for {filename}")
        try:
            task = orch_context.call_activity("analyze_image_activity", filename)
            result = str(task) if task else "Processing image..."
            return json.dumps({
                "status": "success",
                "tool": "process_image_file",
                "message": "Image analysis queued",
                "result": result
            })
        except Exception as e:
            logging.error(f"[TOOL] process_image_file error: {e}")
            return json.dumps({
                "status": "error",
                "tool": "process_image_file",
                "error": str(e)
            })
    
    @tool
    def process_text_file(filename: str) -> str:
        """Process a text file."""
        logging.info(f"[TOOL] process_text_file called for {filename}")
        try:
            task = orch_context.call_activity("analyze_text_activity", filename)
            result = str(task) if task else "Processing text..."
            return json.dumps({
                "status": "success",
                "tool": "process_text_file",
                "message": "Text analysis queued",
                "result": result
            })
        except Exception as e:
            logging.error(f"[TOOL] process_text_file error: {e}")
            return json.dumps({
                "status": "error",
                "tool": "process_text_file",
                "error": str(e)
            })
    
    @tool
    def embed_file_to_vector_store(filename: str) -> str:
        """Embed file content into vector store for semantic search."""
        logging.info(f"[TOOL] embed_file_to_vector_store called for {filename}")
        try:
            task = orch_context.call_activity("embed_file_activity", filename)
            result = str(task) if task else "Embedding file..."
            return json.dumps({
                "status": "success",
                "tool": "embed_file_to_vector_store",
                "message": "File embedding queued",
                "result": result
            })
        except Exception as e:
            logging.error(f"[TOOL] embed_file_to_vector_store error: {e}")
            return json.dumps({
                "status": "error",
                "tool": "embed_file_to_vector_store",
                "error": str(e)
            })
    
    return [
        process_cv_pdf,
        process_report_pdf,
        process_image_file,
        process_text_file,
        embed_file_to_vector_store
    ]


# ============================================================================
# LangChain Agent Factory
# ============================================================================

def create_file_orchestration_agent(tools: list):
    """Factory function to create the ReAct agent with injected tools."""
    llm = OllamaLLM(
        base_url=OLLAMA_BASE_URL,
        model=OLLAMA_LLM_MODEL,
        temperature=0
    )
    
    prompt = hub.pull("hwchase17/react")
    agent = create_react_agent(llm, tools, prompt)
    
    agent_executor = AgentExecutor(
        agent=agent,
        tools=tools,
        verbose=True,
        max_iterations=10,
        handle_parsing_errors=True
    )
    
    return agent_executor


def analyze_file_with_agent(filename: str, orch_context: OrchestrationContext) -> dict:
    """Main orchestration function that uses LangChain agent to decide processing pipeline."""
    logging.info(f"[AGENT] Creating tools with injected context for {filename}")
    
    # Create tools with dependency injection
    tools = create_file_processing_tools(orch_context)
    
    # Create agent with tools
    agent = create_file_orchestration_agent(tools)
    
    # Determine file type from extension
    file_ext = filename.rsplit('.', 1)[-1].lower() if '.' in filename else 'unknown'
    
    # Agent prompt - minimal, lets agent decide
    prompt = f"""Process this file optimally: {filename}

File extension: {file_ext}

Analyze the file type and use appropriate tools:
- CV PDFs: use process_cv_pdf
- Report PDFs: use process_report_pdf
- Images: use process_image_file
- Text files: use process_text_file
- For embeddings: use embed_file_to_vector_store

Decide the best processing pipeline for this file."""
    
    try:
        logging.info(f"[AGENT] Starting orchestration for {filename}")
        result = agent.invoke({"input": prompt})
        
        logging.info(f"[AGENT] Orchestration complete for {filename}")
        
        return {
            "status": "completed",
            "file": filename,
            "file_type": file_ext,
            "analysis": result.get("output", ""),
            "processed_at": datetime.now().isoformat()
        }
    except Exception as e:
        logging.error(f"[AGENT] Orchestration failed: {e}", exc_info=True)
        return {
            "status": "failed",
            "file": filename,
            "error": str(e),
            "processed_at": datetime.now().isoformat()
        }


# ============================================================================
# Event Grid Trigger
# ============================================================================

@app.event_grid_trigger(arg_name="event")
@app.durable_client_input(client_name="client")
async def event_grid_trigger(event: func.EventGridEvent, client: df.DurableOrchestrationClient):
    """Triggered when ANY file is uploaded to file-uploads container."""
    try:
        event_type = event.event_type
        
        if event_type == "Microsoft.Storage.BlobCreated":
            data = event.get_json()
            blob_url = data['url']
            blob_name = blob_url.split(f'/{UPLOADS_CONTAINER}/')[-1]
            
            logging.info(f"[EVENT GRID] File detected: {blob_name}")
            
            instance_id = await client.start_new("file_orchestrator", None, blob_name)
            logging.info(f"[EVENT GRID] Started orchestration {instance_id} for file: {blob_name}")
    
    except Exception as e:
        logging.error(f"[EVENT GRID] Error: {e}", exc_info=True)
        raise


# ============================================================================
# Durable Orchestrator (Acts as LangChain orchestration layer)
# ============================================================================

@app.orchestration_trigger(context_name="context")
def file_orchestrator(context: df.DurableOrchestrationContext):
    """Main orchestrator - LangChain agent decides which activities to call."""
    filename = context.get_input()
    logging.info(f"[ORCHESTRATOR] Starting for: {filename}")
    
    try:
        # Create orchestration context with the durable context
        orch_context = OrchestrationContext(
            durable_context=context,
            filename=filename
        )
        
        # Run LangChain orchestration (in orchestrator, not activity)
        result = analyze_file_with_agent(filename, orch_context)
        
        logging.info(f"[ORCHESTRATOR] File processing completed for {filename}")
        
        # Store result to blob
        yield context.call_activity("store_result_activity", result)
        
        return {
            "status": "completed",
            "file": filename,
            "result": result
        }
        
    except Exception as e:
        logging.error(f"[ORCHESTRATOR] Error: {e}", exc_info=True)
        raise


# ============================================================================
# Storage Activity
# ============================================================================

@app.activity_trigger(input_name="result")
def store_result_activity(result):
    """Activity to store analysis result to blob storage."""
    logging.info(f"[STORAGE ACTIVITY] Storing result for {result.get('file')}")
    
    try:
        connection_string = os.environ["AzureWebJobsStorage"]
        blob_service_client = BlobServiceClient.from_connection_string(connection_string)
        
        filename = result.get('file', 'unknown')
        result_filename = f"{filename.rsplit('.', 1)[0]}_analysis.json"
        blob_client = blob_service_client.get_blob_client(
            container=RESULTS_CONTAINER,
            blob=result_filename
        )
        
        result_json = json.dumps(result, indent=2)
        blob_client.upload_blob(result_json, overwrite=True)
        
        logging.info(f"[STORAGE ACTIVITY] Result stored: {result_filename}")
        return {"status": "stored", "filename": result_filename}
    
    except Exception as e:
        logging.error(f"[STORAGE ACTIVITY] Failed: {e}", exc_info=True)
        raise


# ============================================================================
# Specialized Processing Activities
# ============================================================================

@app.activity_trigger(input_name="filename")
def analyze_cv_activity(filename: str):
    """Activity for CV PDF analysis."""
    logging.info(f"[CV ACTIVITY] Analyzing CV: {filename}")
    
    temp_file_path = None
    try:
        connection_string = os.environ["AzureWebJobsStorage"]
        blob_service_client = BlobServiceClient.from_connection_string(connection_string)
        blob_client = blob_service_client.get_blob_client(container=UPLOADS_CONTAINER, blob=filename)
        
        blob_content = blob_client.download_blob().readall()
        logging.info(f"[CV ACTIVITY] Downloaded {len(blob_content)} bytes")
        
        with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as temp_file:
            temp_file.write(blob_content)
            temp_file_path = temp_file.name
        
        logging.info("[CV ACTIVITY] Extracting text from CV...")
        loader = PyPDFLoader(temp_file_path)
        documents = loader.load()
        logging.info(f"[CV ACTIVITY] Loaded {len(documents)} pages")
        
        cv_text = "\n".join([doc.page_content for doc in documents])
        
        llm = OllamaLLM(
            base_url=OLLAMA_BASE_URL,
            model=OLLAMA_LLM_MODEL,
            temperature=0
        )
        
        logging.info("[CV ACTIVITY] Analyzing CV content with LLM...")
        
        extraction_prompt = f"""Extract from this CV and return ONLY JSON:
        - name: Full name
        - email: Email address
        - phone: Phone number
        - location: Location/City
        - years_experience: Years of professional experience
        - key_skills: List of top 5 skills
        - current_title: Current job title
        
        CV: {cv_text[:3000]}
        
        Return ONLY valid JSON, no other text."""
        
        response = llm.invoke(extraction_prompt)
        
        try:
            cv_analysis = json.loads(response)
        except:
            cv_analysis = {"raw_extraction": response}
        
        result = {
            "file": filename,
            "type": "CV",
            "status": "analyzed",
            "message": "CV extracted and analyzed",
            "analysis": cv_analysis,
            "pages": len(documents),
            "characters": len(cv_text),
            "timestamp": datetime.now().isoformat()
        }
        
        logging.info(f"[CV ACTIVITY] CV analysis complete")
        return json.dumps(result)
    
    except Exception as e:
        logging.error(f"[CV ACTIVITY] Failed: {e}", exc_info=True)
        raise
    finally:
        if temp_file_path and os.path.exists(temp_file_path):
            os.remove(temp_file_path)


@app.activity_trigger(input_name="filename")
def analyze_report_activity(filename: str):
    """Activity for report PDF analysis."""
    logging.info(f"[REPORT ACTIVITY] Analyzing report: {filename}")
    
    temp_file_path = None
    try:
        connection_string = os.environ["AzureWebJobsStorage"]
        blob_service_client = BlobServiceClient.from_connection_string(connection_string)
        blob_client = blob_service_client.get_blob_client(container=UPLOADS_CONTAINER, blob=filename)
        
        blob_content = blob_client.download_blob().readall()
        logging.info(f"[REPORT ACTIVITY] Downloaded {len(blob_content)} bytes")
        
        with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as temp_file:
            temp_file.write(blob_content)
            temp_file_path = temp_file.name
        
        logging.info("[REPORT ACTIVITY] Extracting text from report...")
        loader = PyPDFLoader(temp_file_path)
        documents = loader.load()
        logging.info(f"[REPORT ACTIVITY] Loaded {len(documents)} pages")
        
        report_text = "\n".join([doc.page_content for doc in documents])
        
        llm = OllamaLLM(
            base_url=OLLAMA_BASE_URL,
            model=OLLAMA_LLM_MODEL,
            temperature=0
        )
        
        logging.info("[REPORT ACTIVITY] Analyzing report content with LLM...")
        
        analysis_prompt = f"""Analyze this report and return ONLY JSON:
        - title: Report title
        - key_findings: List of 3-5 main findings
        - summary: 2-3 sentence summary
        - recommendations: List of recommendations if any
        - sections: List of main sections/chapters
        
        Report: {report_text[:3000]}
        
        Return ONLY valid JSON, no other text."""
        
        response = llm.invoke(analysis_prompt)
        
        try:
            report_analysis = json.loads(response)
        except:
            report_analysis = {"raw_analysis": response}
        
        result = {
            "file": filename,
            "type": "Report",
            "status": "analyzed",
            "message": "Report extracted and analyzed",
            "analysis": report_analysis,
            "pages": len(documents),
            "characters": len(report_text),
            "timestamp": datetime.now().isoformat()
        }
        
        logging.info(f"[REPORT ACTIVITY] Report analysis complete")
        return json.dumps(result)
    
    except Exception as e:
        logging.error(f"[REPORT ACTIVITY] Failed: {e}", exc_info=True)
        raise
    finally:
        if temp_file_path and os.path.exists(temp_file_path):
            os.remove(temp_file_path)


@app.activity_trigger(input_name="filename")
def analyze_image_activity(filename: str):
    """Activity for image analysis."""
    logging.info(f"[IMAGE ACTIVITY] Analyzing image: {filename}")
    
    temp_file_path = None
    try:
        connection_string = os.environ["AzureWebJobsStorage"]
        blob_service_client = BlobServiceClient.from_connection_string(connection_string)
        blob_client = blob_service_client.get_blob_client(container=UPLOADS_CONTAINER, blob=filename)
        
        blob_content = blob_client.download_blob().readall()
        logging.info(f"[IMAGE ACTIVITY] Downloaded {len(blob_content)} bytes")
        
        with tempfile.NamedTemporaryFile(delete=False, suffix=".tmp") as temp_file:
            temp_file.write(blob_content)
            temp_file_path = temp_file.name
        
        logging.info(f"[IMAGE ACTIVITY] Saved to temporary file: {temp_file_path}")
        
        llm = OllamaLLM(
            base_url=OLLAMA_BASE_URL,
            model=OLLAMA_LLM_MODEL,
            temperature=0
        )
        
        logging.info("[IMAGE ACTIVITY] Analyzing image with LLM...")
        
        file_size = len(blob_content)
        
        analysis_prompt = f"""This is an image file ({filename}) of size {file_size} bytes.
        Provide a structured analysis in JSON:
        - filename: {filename}
        - file_size_bytes: {file_size}
        - file_type: Based on extension
        - detected: Whether it's a diagram, screenshot, photo, chart, etc.
        - description: What type of image this appears to be
        """
        
        response = llm.invoke(analysis_prompt)
        
        try:
            image_analysis = json.loads(response)
        except:
            image_analysis = {"raw_analysis": response}
        
        result = {
            "file": filename,
            "type": "Image",
            "status": "analyzed",
            "message": "Image analyzed",
            "analysis": image_analysis,
            "file_size_bytes": file_size,
            "timestamp": datetime.now().isoformat()
        }
        
        logging.info(f"[IMAGE ACTIVITY] Image analysis complete")
        return json.dumps(result)
    
    except Exception as e:
        logging.error(f"[IMAGE ACTIVITY] Failed: {e}", exc_info=True)
        raise
    finally:
        if temp_file_path and os.path.exists(temp_file_path):
            os.remove(temp_file_path)


@app.activity_trigger(input_name="filename")
def analyze_text_activity(filename: str):
    """Activity for text file analysis."""
    logging.info(f"[TEXT ACTIVITY] Analyzing text file: {filename}")
    
    temp_file_path = None
    try:
        connection_string = os.environ["AzureWebJobsStorage"]
        blob_service_client = BlobServiceClient.from_connection_string(connection_string)
        blob_client = blob_service_client.get_blob_client(container=UPLOADS_CONTAINER, blob=filename)
        
        blob_content = blob_client.download_blob().readall()
        logging.info(f"[TEXT ACTIVITY] Downloaded {len(blob_content)} bytes")
        
        with tempfile.NamedTemporaryFile(delete=False, suffix=".txt", mode='wb') as temp_file:
            temp_file.write(blob_content)
            temp_file_path = temp_file.name
        
        logging.info(f"[TEXT ACTIVITY] Saved to temporary file: {temp_file_path}")
        
        try:
            with open(temp_file_path, 'r', encoding='utf-8') as f:
                text_content = f.read()
        except UnicodeDecodeError:
            with open(temp_file_path, 'r', encoding='latin-1') as f:
                text_content = f.read()
        
        logging.info(f"[TEXT ACTIVITY] Extracted {len(text_content)} characters")
        
        llm = OllamaLLM(
            base_url=OLLAMA_BASE_URL,
            model=OLLAMA_LLM_MODEL,
            temperature=0
        )
        
        logging.info("[TEXT ACTIVITY] Analyzing text content with LLM...")
        
        analysis_prompt = f"""Analyze this text file and return ONLY JSON:
        - content_type: Type of content (e.g., article, documentation, log, code, etc.)
        - summary: 2-3 sentence summary
        - key_topics: List of 3-5 main topics
        - sentiment: Overall sentiment if applicable
        - entities: Any named entities, people, or important terms mentioned
        - word_count: Approximate word count
        
        Text: {text_content[:3000]}
        
        Return ONLY valid JSON, no other text."""
        
        response = llm.invoke(analysis_prompt)
        
        try:
            text_analysis = json.loads(response)
        except:
            text_analysis = {"raw_analysis": response}
        
        result = {
            "file": filename,
            "type": "Text",
            "status": "analyzed",
            "message": "Text file analyzed",
            "analysis": text_analysis,
            "characters": len(text_content),
            "bytes": len(blob_content),
            "timestamp": datetime.now().isoformat()
        }
        
        logging.info(f"[TEXT ACTIVITY] Text analysis complete")
        return json.dumps(result)
    
    except Exception as e:
        logging.error(f"[TEXT ACTIVITY] Failed: {e}", exc_info=True)
        raise
    finally:
        if temp_file_path and os.path.exists(temp_file_path):
            os.remove(temp_file_path)


@app.activity_trigger(input_name="filename")
def embed_file_activity(filename: str):
    """Activity to embed file content into vector store using FAISS."""
    logging.info(f"[EMBED ACTIVITY] Embedding file: {filename}")
    
    temp_file_path = None
    try:
        connection_string = os.environ["AzureWebJobsStorage"]
        blob_service_client = BlobServiceClient.from_connection_string(connection_string)
        blob_client = blob_service_client.get_blob_client(container=UPLOADS_CONTAINER, blob=filename)
        
        blob_content = blob_client.download_blob().readall()
        logging.info(f"[EMBED ACTIVITY] Downloaded {len(blob_content)} bytes")
        
        file_ext = filename.rsplit('.', 1)[-1].lower() if '.' in filename else 'unknown'
        text_content = ""
        
        if file_ext == 'pdf':
            with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as temp_file:
                temp_file.write(blob_content)
                temp_file_path = temp_file.name
            
            logging.info("[EMBED ACTIVITY] Extracting text from PDF...")
            loader = PyPDFLoader(temp_file_path)
            documents = loader.load()
            text_content = "\n".join([doc.page_content for doc in documents])
        
        elif file_ext in ['txt', 'md', 'log']:
            try:
                text_content = blob_content.decode('utf-8')
            except UnicodeDecodeError:
                text_content = blob_content.decode('latin-1')
        
        else:
            text_content = f"File: {filename}, Type: {file_ext}, Size: {len(blob_content)} bytes"
        
        if not text_content:
            text_content = f"File: {filename} (No extractable text)"
        
        logging.info(f"[EMBED ACTIVITY] Extracted {len(text_content)} characters")
        
        logging.info("[EMBED ACTIVITY] Creating embeddings...")
        embeddings = OllamaEmbeddings(
            base_url=OLLAMA_BASE_URL,
            model=OLLAMA_EMBEDDING_MODEL
        )
        
        text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=CHUNK_SIZE,
            chunk_overlap=CHUNK_OVERLAP
        )
        
        doc = Document(page_content=text_content, metadata={"source": filename})
        chunks = text_splitter.split_documents([doc])
        
        logging.info(f"[EMBED ACTIVITY] Created {len(chunks)} chunks")
        
        logging.info("[EMBED ACTIVITY] Creating FAISS vector store...")
        vector_store = FAISS.from_documents(chunks, embeddings)
        
        faiss_index_path = f"/tmp/{filename.rsplit('.', 1)[0]}_faiss_index"
        vector_store.save_local(faiss_index_path)
        logging.info(f"[EMBED ACTIVITY] Saved FAISS index to {faiss_index_path}")
        
        result = {
            "file": filename,
            "status": "embedded",
            "message": "File embedded to vector store",
            "chunks_created": len(chunks),
            "characters_embedded": len(text_content),
            "index_path": faiss_index_path,
            "timestamp": datetime.now().isoformat()
        }
        
        logging.info(f"[EMBED ACTIVITY] Embedding complete")
        return json.dumps(result)
    
    except Exception as e:
        logging.error(f"[EMBED ACTIVITY] Failed: {e}", exc_info=True)
        raise
    finally:
        if temp_file_path and os.path.exists(temp_file_path):
            os.remove(temp_file_path)


# ============================================================================
# HTTP Endpoints
# ============================================================================

@app.route(route="startOrchestrator")
@app.durable_client_input(client_name="client")
async def http_start(req: func.HttpRequest, client: df.DurableOrchestrationClient):
    """HTTP endpoint to manually trigger file orchestration."""
    try:
        file_name = req.params.get('file')
        if not file_name:
            return func.HttpResponse("Please pass a 'file' parameter in the query string", status_code=400)
        
        logging.info(f"[HTTP] Starting orchestration for: {file_name}")
        instance_id = await client.start_new("file_orchestrator", None, file_name)
        
        return client.create_check_status_response(req, instance_id)
        
    except Exception as e:
        logging.error(f"[HTTP] Error: {e}", exc_info=True)
        return func.HttpResponse(f"Error: {str(e)}", status_code=500)


@app.route(route="processingStatus")
@app.durable_client_input(client_name="client")
async def get_processing_status(req: func.HttpRequest, client: df.DurableOrchestrationClient):
    """Check status of orchestrations."""
    try:
        logging.info("[STATUS] Fetching orchestration instances...")
        instance_query = await client.get_status_all()
        
        running = []
        completed = []
        failed = []
        
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
        
        response_data = {
            "summary": {
                "running": len(running),
                "completed": len(completed),
                "failed": len(failed)
            },
            "running": running,
            "completed": completed,
            "failed": failed
        }
        
        return func.HttpResponse(
            json.dumps(response_data, indent=2),
            mimetype="application/json"
        )
    
    except Exception as e:
        logging.error(f"[STATUS] Error: {e}", exc_info=True)
        return func.HttpResponse(f"Error: {str(e)}", status_code=500)