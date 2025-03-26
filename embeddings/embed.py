import os
import math
import shutil
import zipfile
import multiprocessing as mp
from pathlib import Path
from typing import List

# For .env loading
from dotenv import load_dotenv

# OpenSearch & LangChain
from opensearchpy import OpenSearch, NotFoundError, RequestError
from langchain_community.vectorstores import OpenSearchVectorSearch
from langchain_huggingface import HuggingFaceEmbeddings
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain.docstore.document import Document

# -------------------------------------------------------------------
# Load environment variables from .env
# -------------------------------------------------------------------
load_dotenv()

# Read environment variables, with defaults
OPEN_SEARCH_URL = os.getenv("OPENSEARCH_URL", "https://example-1.es.amazonaws.com")
OS_USERNAME     = os.getenv("OPENSEARCH_USERNAME", "master-user")
OS_PASSWORD     = os.getenv("OPENSEARCH_PASSWORD", "password123")
MODEL_NAME      = os.getenv("QODO_MODEL_NAME", "Qodo/Qodo-Embed-1-1.5B")
NUM_GPUS        = int(os.getenv("NUM_GPUS", "4"))
BULK_SIZE       = int(os.getenv("BULK_SIZE", "10000"))

# -------------------------------------------------------------------
# Functions
# -------------------------------------------------------------------
def create_index_if_not_exists(index_name: str, dimension: int = 768):
    """
    Creates the OpenSearch index if it doesn't exist.
    Handles concurrency gracefully by ignoring 'resource_already_exists_exception'.
    """
    client = OpenSearch(
        hosts=[{"host": _parse_host(OPEN_SEARCH_URL), "port": _parse_port(OPEN_SEARCH_URL), "scheme": _parse_scheme(OPEN_SEARCH_URL)}],
        http_auth=(OS_USERNAME, OS_PASSWORD),
        use_ssl=True,
        verify_certs=True
    )

    # Minimal mapping – adjust dimension if your embedding is different
    mapping = {
      "settings": {
        "index": {
          "knn": True
        }
      },
      "mappings": {
        "properties": {
          "embedding": {
            "type": "knn_vector",
            "dimension": dimension
          }
        }
      }
    }

    try:
        client.indices.get(index=index_name)
        print(f"Index '{index_name}' already exists.")
    except NotFoundError:
        print(f"Index '{index_name}' does not exist; creating now.")
        try:
            client.indices.create(index=index_name, body=mapping)
            print(f"Index '{index_name}' created.")
        except RequestError as e:
            if "resource_already_exists_exception" in str(e):
                print(f"Index '{index_name}' was created concurrently by another process.")
            else:
                raise

def load_and_chunk(repo_path: str) -> List[Document]:
    """
    Loads .go, .yaml, .sh .js .c .cpp from `repo_path`, splits them into chunks.
    """
    exts = [".go", ".yaml", ".sh", ".js", ".c", ".cpp"]
    docs = []

    repo_dir = Path(repo_path).expanduser().resolve()

    for ext in exts:
        for file_path in repo_dir.rglob(f"*{ext}"):
            try:
                content = file_path.read_text(encoding="utf-8", errors="ignore")
                doc = Document(page_content=content, metadata={"source": str(file_path)})
                docs.append(doc)
            except Exception as e:
                print(f"Error reading {file_path}: {e}")

    splitter = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=200)
    chunks = splitter.split_documents(docs)
    return chunks

def embed_and_store(docs_subset: List[Document], gpu_id: int, index_name: str):
    """
    Child worker to embed docs on `cuda:<gpu_id>` and store in 'index_name'.
    """
    # Generate unique IDs
    for i, d in enumerate(docs_subset):
        d.metadata["doc_id"] = f"{index_name}_gpu{gpu_id}_chunk{i}"

    embeddings = HuggingFaceEmbeddings(
        model_name=MODEL_NAME,
        model_kwargs={"device": f"cuda:{gpu_id}"}
    )

    vs = OpenSearchVectorSearch(
        index_name=index_name,
        opensearch_url=OPEN_SEARCH_URL,
        http_auth=(OS_USERNAME, OS_PASSWORD),
        embedding_function=embeddings
    )

    print(f"[GPU {gpu_id}] Embedding & storing {len(docs_subset)} docs in index='{index_name}'...")
    vs.add_documents(docs_subset, bulk_size=BULK_SIZE, id_key="doc_id")
    print(f"[GPU {gpu_id}] Done storing {len(docs_subset)} docs in index='{index_name}'.")

# def multiprocess_embed(chunks: List[Document], index_name: str):
#     """
#     Multi-process embedding logic for a set of chunked docs, stored in 'index_name'.
#     """
#     # Create the index (if not exist)
#     create_index_if_not_exists(index_name)

#     total_chunks = len(chunks)
#     print(f"Total chunks: {total_chunks} for index='{index_name}'")

#     n = NUM_GPUS
#     docs_per_gpu = math.ceil(total_chunks / n)
#     subsets = [chunks[i:i+docs_per_gpu] for i in range(0, total_chunks, docs_per_gpu)]
#     subsets = subsets[:n]  # ensure at most N subsets

#     processes = []
#     for gpu_id in range(len(subsets)):
#         p = mp.Process(target=embed_and_store, args=(subsets[gpu_id], gpu_id, index_name))
#         p.start()
#         processes.append(p)

#     for p in processes:
#         p.join()

#     print(f"All GPU workers finished embedding & storing docs for index='{index_name}'.")

def multiprocess_embed(chunks: List[Document], index_name: str):
    create_index_if_not_exists(index_name)

    total_chunks = len(chunks)
    print(f"Total chunks: {total_chunks} for index='{index_name}'")

    if total_chunks == 0:
        print(f"No documents found for embedding. Skipping multi-GPU process.")
        return

    n = NUM_GPUS
    docs_per_gpu = math.ceil(total_chunks / n)
    if docs_per_gpu == 0:
        print(f"No docs to embed per GPU. Skipping.")
        return

    subsets = [chunks[i:i + docs_per_gpu] for i in range(0, total_chunks, docs_per_gpu)]
    subsets = subsets[:n]  # ensure at most N subsets

    processes = []
    for gpu_id in range(len(subsets)):
        p = mp.Process(target=embed_and_store, args=(subsets[gpu_id], gpu_id, index_name))
        p.start()
        processes.append(p)

    for p in processes:
        p.join()

    print(f"All GPU workers finished embedding for index='{index_name}'.")


def unzip_all_team_repos(team_name: str, base_dir: Path) -> Path:
    """
    Unzips all .zip files under 'repos/<team_name>' into a temp directory.
    Returns that directory path.
    """
    from datetime import datetime
    import tempfile

    team_repos_dir = base_dir / team_name
    if not team_repos_dir.exists():
        raise FileNotFoundError(f"No directory found for team '{team_name}': {team_repos_dir}")

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    temp_dir = Path(tempfile.mkdtemp(prefix=f"{team_name}_{timestamp}_"))

    print(f"Unzipping repos for team='{team_name}' into temp dir: {temp_dir}")
    for zip_file in team_repos_dir.glob("*.zip"):
        try:
            with zipfile.ZipFile(zip_file, "r") as z:
                z.extractall(temp_dir)
        except Exception as e:
            print(f"Error unzipping {zip_file}: {e}")

    return temp_dir

def embed_context(context_name: str, base_dir: Path):
    """
    Main function to embed all .zip repos for a given team_name. 
    Index name = team_name.
    """
    print(f"\n=== Embedding for context '{context_name}' ===")
    temp_dir = None
    try:
        #temp_dir = unzip_all_team_repos(team_name, base_dir)
        chunks = load_and_chunk(base_dir)
        print(f"Loaded {len(chunks)} chunks from context='{context_name}'. Using index '{context_name}'")
        multiprocess_embed(chunks, context_name)

    finally:
        if temp_dir and temp_dir.exists():
            shutil.rmtree(temp_dir, ignore_errors=True)
            print(f"Cleaned up temporary directory: {temp_dir}")

# Helpers to parse the host/port from OPENSEARCH_URL if needed
def _parse_scheme(url: str) -> str:
    if url.startswith("https://"):
        return "https"
    elif url.startswith("http://"):
        return "http"
    return "https"  # default

def _parse_host(url: str) -> str:
    # Remove scheme
    no_scheme = url.replace("https://", "").replace("http://", "")
    # If there's a slash, remove path
    no_path = no_scheme.split("/")[0]
    # If there's a port, remove it
    return no_path.split(":")[0]

def _parse_port(url: str) -> int:
    # If user included a :port, parse it, otherwise default 443
    no_scheme = url.replace("https://", "").replace("http://", "")
    no_path = no_scheme.split("/")[0]
    parts = no_path.split(":")
    if len(parts) == 2 and parts[1].isdigit():
        return int(parts[1])
    return 443

