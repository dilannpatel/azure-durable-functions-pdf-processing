import os
import json
import logging
from datetime import datetime
import tempfile

import azure.functions as func
import azure.durable_functions as df
from azure.storage.blob import BlobServiceClient

from langchain_community.document_loaders import PyPDFLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_openai import AzureOpenAIEmbeddings, AzureChatOpenAI
from langchain_community.vectorstores import AzureSearch

from langchain.agents import AgentExecutor, create_tool_calling_agent
from langchain_core.tools import tool
from langchain_core.prompts import ChatPromptTemplate


UPLOADS_CONTAINER = os.environ.get("PDF_UPLOADS_CONTAINER", "pdf-uploads")
RESULTS_CONTAINER = os.environ.get("PDF_RESULTS_CONTAINER", "pdf-results")
CHUNK_SIZE = 1000
CHUNK_OVERLAP = 200

app = func.FunctionApp()


def get_llm():
    """Create and return an LLM instance."""
    try:
        return AzureChatOpenAI(
            model="gpt-4",
            api_version=os.environ.get("AZURE_OPENAI_API_VERSION", "2024-02-15-preview"),
            temperature=0,
            azure_endpoint=os.environ["OPENAI_ENDPOINT"],
            openai_api_key=os.environ["OPENAI_API_KEY"]
        )
    except Exception as e:
        logging.error(f"Failed to initialize LLM: {e}")
        raise

def get_embeddings():
    """Create and return embeddings instance."""
    try:
        return AzureOpenAIEmbeddings(
            azure_deployment=os.environ["OPENAI_EMBEDDING_MODEL_NAME"],
            openai_api_key=os.environ["OPENAI_API_KEY"],
            azure_endpoint=os.environ["OPENAI_ENDPOINT"]
        )
    except Exception as e:
        logging.error(f"Failed to initialize embeddings: {e}")
        raise

def get_vector_store():
    """Create and return vector store instance."""
    try:
        return AzureSearch(
            azure_search_endpoint=os.environ["AI_SEARCH_ENDPOINT"],
            azure_search_key=os.environ["AI_SEARCH_API_KEY"],
            index_name=os.environ["AI_SEARCH_INDEX_NAME"],
            embedding_function=get_embeddings().embed_query
        )
    except Exception as e:
        logging.error(f"Failed to initialize vector store: {e}")
        raise


def create_cv_tools():
    """Creates all CV analysis tools."""
    llm = get_llm()
    
    @tool
    def extract_candidate_info(cv_text: str) -> dict:
        """Extracts candidate's name, email, phone, location, and experience."""
        prompt = f"""
        Extract the following information from this CV. Return as JSON:
        - name: Full name of candidate
        - email: Email address
        - phone: Phone number
        - location: Location/City
        - years_of_experience: Total years of professional experience (estimate if not explicit)
        
        CV Text: {cv_text[:2000]}
        Return ONLY valid JSON, no other text.
        """
        response = llm.invoke(prompt)
        try:
            return json.loads(response.content)
        except:
            return {"error": "Could not parse candidate info"}

    @tool
    def extract_skills(cv_text: str) -> dict:
        """Extracts and categorizes all skills from the CV."""
        prompt = f"""
        Extract all skills from this CV and categorize them. Return as JSON:
        {{
            "technical_skills": ["Python", "JavaScript", ...],
            "soft_skills": ["Leadership", "Communication", ...],
            "tools_frameworks": ["React", "Docker", ...],
            "languages": ["English", "Spanish", ...],
            "skill_count": "total number of skills found"
        }}
        CV Text: {cv_text[:3000]}
        Return ONLY valid JSON, no other text.
        """
        response = llm.invoke(prompt)
        try:
            return json.loads(response.content)
        except:
            return {"error": "Could not parse skills"}

    @tool
    def extract_work_experience(cv_text: str) -> dict:
        """Extracts work experience from the CV."""
        prompt = f"""
        Extract work experience from this CV. Return as JSON:
        {{
            "experiences": [
                {{"position": "Job Title", "company": "Company Name", "duration": "Years", "key_achievement": "Brief description"}},
                ...
            ],
            "total_positions": "number of positions",
            "career_progression": "Brief summary of career growth"
        }}
        CV Text: {cv_text[:3000]}
        Return ONLY valid JSON, no other text.
        """
        response = llm.invoke(prompt)
        try:
            return json.loads(response.content)
        except:
            return {"error": "Could not parse work experience"}

    @tool
    def extract_education(cv_text: str) -> dict:
        """Extracts education information from the CV."""
        prompt = f"""
        Extract education information from this CV. Return as JSON:
        {{
            "education": [
                {{"degree": "Bachelor of Science", "field": "Computer Science", "institution": "University Name", "graduation_year": "2020"}},
                ...
            ],
            "has_advanced_degree": "boolean",
            "education_summary": "Brief summary"
        }}
        CV Text: {cv_text[:2000]}
        Return ONLY valid JSON, no other text.
        """
        response = llm.invoke(prompt)
        try:
            return json.loads(response.content)
        except:
            return {"error": "Could not parse education"}

    @tool
    def generate_cv_summary(cv_text: str) -> str:
        """Generates a 3-4 sentence executive summary of the CV."""
        prompt = f"""
        Based on this CV, write a 3-4 sentence executive summary highlighting the candidate's strengths and value proposition.
        CV Text: {cv_text[:2000]}
        """
        response = llm.invoke(prompt)
        return response.content

    @tool
    def rate_cv_quality(cv_text: str) -> dict:
        """Rates the CV quality on multiple dimensions."""
        prompt = f"""
        Rate this CV on the following dimensions (1-10 scale). Return as JSON:
        {{
            "completeness": "score (0-10)",
            "clarity": "score (0-10)",
            "skills_presentation": "score (0-10)",
            "achievement_focus": "score (0-10)",
            "overall_quality": "score (0-10)",
            "strengths": ["List of strengths"],
            "improvements": ["List of improvements"]
        }}
        CV Text: {cv_text[:2000]}
        Return ONLY valid JSON, no other text.
        """
        response = llm.invoke(prompt)
        try:
            return json.loads(response.content)
        except:
            return {"error": "Could not rate CV"}

    return [
        extract_candidate_info,
        extract_skills,
        extract_work_experience,
        extract_education,
        generate_cv_summary,
        rate_cv_quality
    ]

def create_cv_analysis_agent():
    """Creates the LangChain agent."""
    llm = get_llm()
    tools = create_cv_tools()
    
    prompt = ChatPromptTemplate.from_messages([
        ("system", "You are a helpful CV analysis assistant. Use the provided tools to analyze CVs comprehensively."),
        ("human", "{input}"),
        ("placeholder", "{agent_scratchpad}")
    ])
    
    agent = create_tool_calling_agent(llm, tools, prompt)
    agent_executor = AgentExecutor(agent=agent, tools=tools, verbose=True)
    return agent_executor

# ============================================================================
# EVENT GRID TRIGGER
# ============================================================================

@app.event_grid_trigger(arg_name="event")
@app.durable_client_input(client_name="client")
async def event_grid_trigger(event: func.EventGridEvent, client: df.DurableOrchestrationClient):
    """Triggered when a PDF is uploaded."""
    try:
        event_type = event.event_type
        
        if event_type == "Microsoft.Storage.BlobCreated":
            data = event.get_json()
            blob_url = data['url']
            blob_name = blob_url.split(f'/{UPLOADS_CONTAINER}/')[-1]
            
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
    """Orchestrates parallel CV processing tasks."""
    blob_file_name = context.get_input()
    logging.info(f"[ORCHESTRATOR] Starting for: {blob_file_name}")
    
    try:
        logging.info(f"[ORCHESTRATOR] Spawning parallel tasks for {blob_file_name}")
        task1_embed = context.call_activity("embed_pdf_to_search", blob_file_name)
        task2_analyze = context.call_activity("analyse_cv_with_agent", blob_file_name)
        
        results = yield context.task_all([task1_embed, task2_analyze])
        logging.info(f"[ORCHESTRATOR] Both tasks completed for {blob_file_name}")
        
        return {
            "status": "completed",
            "file": blob_file_name,
            "embedding_result": results[0],
            "analysis_result": results[1]
        }
        
    except Exception as e:
        logging.error(f"[ORCHESTRATOR] Error: {e}", exc_info=True)
        raise


@app.activity_trigger(input_name="blobName")
def embed_pdf_to_search(blobName: str):
    """Downloads, chunks, and embeds a PDF into AI Search."""
    logging.info(f"[EMBEDDING] Activity started for: {blobName}")
    
    temp_file_path = None
    try:
        connection_string = os.environ["AzureWebJobsStorage"]
        blob_service_client = BlobServiceClient.from_connection_string(connection_string)
        blob_client = blob_service_client.get_blob_client(container=UPLOADS_CONTAINER, blob=blobName)
        
        blob_content = blob_client.download_blob().readall()
        logging.info(f"[EMBEDDING] Downloaded {len(blob_content)} bytes")

        with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as temp_file:
            temp_file.write(blob_content)
            temp_file_path = temp_file.name
        
        logging.info("[EMBEDDING] Extracting text from PDF...")
        loader = PyPDFLoader(temp_file_path)
        documents = loader.load()

        logging.info(f"[EMBEDDING] Splitting into chunks...")
        text_splitter = RecursiveCharacterTextSplitter(chunk_size=CHUNK_SIZE, chunk_overlap=CHUNK_OVERLAP)
        chunks = text_splitter.split_documents(documents)
        
        logging.info(f"[EMBEDDING] Adding {len(chunks)} chunks to search index...")
        vector_store = get_vector_store()
        vector_store.add_documents(documents=chunks)
        
        return f"Successfully embedded {len(chunks)} chunks."

    except Exception as e:
        logging.error(f"[EMBEDDING] Failed: {e}", exc_info=True)
        raise
    finally:
        if temp_file_path and os.path.exists(temp_file_path):
            os.remove(temp_file_path)


@app.activity_trigger(input_name="blobName")
def analyse_cv_with_agent(blobName: str):
    """Downloads and analyzes a CV with the LangChain agent."""
    logging.info(f"[AGENT] CV analysis started for: {blobName}")
    
    temp_file_path = None
    try:
        connection_string = os.environ["AzureWebJobsStorage"]
        blob_service_client = BlobServiceClient.from_connection_string(connection_string)
        blob_client = blob_service_client.get_blob_client(container=UPLOADS_CONTAINER, blob=blobName)
        
        blob_content = blob_client.download_blob().readall()
        logging.info(f"[AGENT] Downloaded {len(blob_content)} bytes")

        with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as temp_file:
            temp_file.write(blob_content)
            temp_file_path = temp_file.name

        logging.info("[AGENT] Extracting text from CV...")
        loader = PyPDFLoader(temp_file_path)
        documents = loader.load()
        cv_text = "\n".join([doc.page_content for doc in documents])
        logging.info(f"[AGENT] Extracted {len(cv_text)} characters")

        logging.info("[AGENT] Initializing CV analysis agent...")
        agent = create_cv_analysis_agent()

        logging.info("[AGENT] Running agent analysis...")
        agent_input = f"Analyze this CV comprehensively using all available tools. CV Text: {cv_text}"
        
        agent_result = agent.invoke({"input": agent_input})
        logging.info("[AGENT] Agent analysis completed")

        analysis = {
            "file_name": blobName,
            "analysis_type": "CV Analysis",
            "agent_output": agent_result.get("output", ""),
            "processed_at": datetime.now().isoformat(),
            "status": "completed"
        }

        results_blob_name = f"{blobName.rsplit('.', 1)[0]}_cv_analysis.json"
        results_blob_client = blob_service_client.get_blob_client(
            container=RESULTS_CONTAINER,
            blob=results_blob_name
        )
        
        results_json = json.dumps(analysis, indent=2)
        results_blob_client.upload_blob(results_json, overwrite=True)
        
        return f"CV analysis completed and stored: {results_blob_name}"

    except Exception as e:
        logging.error(f"[AGENT] Failed: {e}", exc_info=True)
        raise
    finally:
        if temp_file_path and os.path.exists(temp_file_path):
            os.remove(temp_file_path)


@app.route(route="startOrchestrator")
@app.durable_client_input(client_name="client")
async def http_start(req: func.HttpRequest, client: df.DurableOrchestrationClient):
    """HTTP endpoint to manually trigger CV processing."""
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
    """HTTP endpoint to check status of all processing instances."""
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