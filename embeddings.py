# app/embeddings.py

from langchain_community.document_loaders import DirectoryLoader, TextLoader
from langchain_community.embeddings import HuggingFaceEmbeddings
from langchain_community.vectorstores import Chroma

from langchain.text_splitter import RecursiveCharacterTextSplitter
import os
from dotenv import load_dotenv

load_dotenv()  # Load API keys

def create_embeddings(repo_path: str):
    """
    Processes the local repository, splits the code into chunks, generates embeddings,
    and stores them in ChromaDB. Includes .go, .yaml, .sh files for broader context.
    """
    # Step 1: Load the repository's code files (.go, .yaml, .sh)
    loader = DirectoryLoader(
        repo_path,
        glob="**/*.go",  # Include Go files
        loader_cls=TextLoader
    )
    documents = loader.load()

    # Add additional file types (YAML and Shell scripts)
    loader_yaml = DirectoryLoader(
        repo_path,
        glob="**/*.yaml",  # Include YAML files
        loader_cls=TextLoader
    )
    documents += loader_yaml.load()

    loader_sh = DirectoryLoader(
        repo_path,
        glob="**/*.sh",  # Include Shell script files
        loader_cls=TextLoader
    )
    documents += loader_sh.load()

    # Step 2: Split documents into smaller chunks
    splitter = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=200)
    chunks = splitter.split_documents(documents)

    # Step 3: Generate embeddings using HuggingFace's Qodo-Embed-1-7B
    embeddings = HuggingFaceEmbeddings(model_name="Qodo/Qodo-Embed-1-7B")

    # Step 4: Store embeddings in a ChromaDB vector store
    db = Chroma.from_documents(chunks, embeddings, persist_directory="./data/embeddings_db")
    db.persist()

    print(f"✅ Embeddings for repo {repo_path} successfully created and stored!")

def main():
    # Path to the local repository
    repo_path = "/Users/darshsh/go/cisco/cloudsec/cloudsec-sfcn-sfcn"  # Update this path to your local repo
    create_embeddings(repo_path)

if __name__ == "__main__":
    main()
