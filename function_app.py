import os
import azure.functions as func
import azure.durable_functions as df
import logging
from langchain_community.document_loaders import PyPDFLoader
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_openai import AzureOpenAIEmbeddings
from langchain_community.vectorstores import AzureSearch

# triggered when a PDF is added to the pdfs container in Blob Storage.
@app.blob_trigger(arg_name="pdfBlob",
                  path="pdfs/{name}.pdf",
                  connection="AzureWebJobsStorage")
@app.durable_client_input(client_name="client")
async def blob_trigger(pdfBlob: func.InputStream, client: df.DurableOrchestrationClient):
    
    # Get the name and path of the uploaded file
    blob_name = pdfBlob.name
    logging.info(f"Processing new file: {blob_name}")
    
    # Start the Durable Function Orchestrator
    instance_id = await client.start_new("pdf_orchestrator", None, blob_name)
    logging.info(f"Started orchestration with ID = '{instance_id}'.")


@app.orchestration_trigger(context_name="context")
def pdf_orchestrator(context: df.DurableOrchestrationContext):
    
    blob_name_to_process = context.get_input()
    logging.info(f"Orchestrator started for: {blob_name_to_process}")
    
    try:
        # Call the "worker" function to do the heavy lifting
        yield context.call_activity("process_pdf_activity", blob_name_to_process)
        
        logging.info(f"Successfully processed {blob_name_to_process}")
        
    except Exception as e:
        logging.error(f"Error processing {blob_name_to_process}: {e}")


# --- 3. The Activity Function (The "Worker") ---
# This does the actual AI work. It can run for a long time
# without timing out (unlike a normal function).

@app.activity_trigger(input_name="blobName")
def process_pdf_activity(blobName: str):
    logging.info(f"Activity started for: {blobName}")
    

    # Load the PDF using PyPDFLoader. The connection string is automatically available as 'AzureWebJobsStorage'
    loader = PyPDFLoader(
        file_path=blobName,
        connection_string=os.environ["AzureWebJobsStorage"]
    )
    documents = loader.load()

    # split into chunks
    text_splitter = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=200)
    chunks = text_splitter.split_documents(documents)

    # 3. create Embeddings (connects to your Azure OpenAI)
    embeddings = AzureOpenAIEmbeddings(
        azure_deployment=os.environ["OPENAI_EMBEDDING_MODEL_NAME"],
        openai_api_key=os.environ["OPENAI_API_KEY"],
        azure_endpoint=os.environ["OPENAI_ENDPOINT"]
    )

    # 4. Connect to your Vector Store (Azure AI Search)
    vector_store = AzureSearch(
        azure_search_endpoint=os.environ["AI_SEARCH_ENDPOINT"],
        azure_search_key=os.environ["AI_SEARCH_API_KEY"],
        index_name="pdf-index",
        embedding_function=embeddings.embed_query
    )
    
    # 5. Add the document chunks to the vector store
    vector_store.add_documents(documents=chunks)
    
    return f"Successfully processed and embedded {len(chunks)} chunks."