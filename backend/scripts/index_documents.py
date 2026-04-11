import os
import glob
import logging
from dotenv import load_dotenv

load_dotenv(override=True)

from langchain_community.document_loaders import PyPDFLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_openai import AzureOpenAIEmbeddings
from langchain_community.vectorstores import AzureSearch

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger("indexer")


def index_docs():
    """
    Reads PDFs from backend/data/, chunks them, embeds them,
    and uploads vectors to Azure AI Search.
    Run this once before starting the app.
    """

    # ------------------------------------------------------------------ #
    # STEP 1 — Find the PDFs
    # ------------------------------------------------------------------ #
    current_dir = os.path.dirname(os.path.abspath(__file__))
    data_folder = os.path.join(current_dir, "../data")
    pdf_files = glob.glob(os.path.join(data_folder, "*.pdf"))

    if not pdf_files:
        logger.warning(f"No PDFs found in {data_folder}. Add your compliance PDFs there.")
        return

    logger.info(f"Found {len(pdf_files)} PDFs: {[os.path.basename(f) for f in pdf_files]}")

    # ------------------------------------------------------------------ #
    # STEP 2 — Initialize the embedding model
    # Converts text chunks into vectors (lists of numbers)
    # Must match the deployment name in your Azure AI Foundry
    # ------------------------------------------------------------------ #
    logger.info("Initializing embedding model...")
    embeddings = AzureOpenAIEmbeddings(
        azure_deployment=os.getenv("AZURE_OPENAI_EMBEDDING_DEPLOYMENT", "text-embedding-3-small"),
        azure_endpoint=os.getenv("AZURE_OPENAI_ENDPOINT"),
        api_key=os.getenv("AZURE_OPENAI_API_KEY"),
        openai_api_version=os.getenv("AZURE_OPENAI_API_VERSION"),
    )
    logger.info("Embedding model ready.")

    # ------------------------------------------------------------------ #
    # STEP 3 — Connect to Azure AI Search
    # This is where the vectors will be stored
    # ------------------------------------------------------------------ #
    logger.info("Connecting to Azure AI Search...")
    index_name = os.getenv("AZURE_SEARCH_INDEX_NAME")
    vector_store = AzureSearch(
        azure_search_endpoint=os.getenv("AZURE_SEARCH_ENDPOINT"),
        azure_search_key=os.getenv("AZURE_SEARCH_API_KEY"),
        index_name=index_name,
        embedding_function=embeddings.embed_query
    )
    logger.info(f"Connected to index: {index_name}")

    # ------------------------------------------------------------------ #
    # STEP 4 — Load and chunk each PDF
    # chunk_size=1000    → each chunk is ~1000 characters
    # chunk_overlap=200  → 200 chars shared between chunks
    #                      prevents rules being cut off at boundaries
    # ------------------------------------------------------------------ #
    all_chunks = []

    for pdf_path in pdf_files:
        logger.info(f"Loading: {os.path.basename(pdf_path)}")

        loader = PyPDFLoader(pdf_path)
        pages = loader.load()

        splitter = RecursiveCharacterTextSplitter(
            chunk_size=1000,
            chunk_overlap=200
        )
        chunks = splitter.split_documents(pages)

        # Tag each chunk with its source PDF — useful for citations later
        for chunk in chunks:
            chunk.metadata["source"] = os.path.basename(pdf_path)

        all_chunks.extend(chunks)
        logger.info(f"  → {len(chunks)} chunks created")

    # ------------------------------------------------------------------ #
    # STEP 5 — Upload all chunks to Azure AI Search
    # Azure Search auto-creates the index if it doesn't exist
    # ------------------------------------------------------------------ #
    if all_chunks:
        logger.info(f"Uploading {len(all_chunks)} chunks to Azure AI Search...")
        vector_store.add_documents(documents=all_chunks)
        logger.info("=" * 50)
        logger.info("Knowledge base is ready.")
        logger.info(f"Total chunks indexed: {len(all_chunks)}")
        logger.info("=" * 50)
    else:
        logger.warning("No chunks to upload.")


if __name__ == "__main__":
    index_docs()
