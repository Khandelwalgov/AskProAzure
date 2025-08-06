# rag_utils.py
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain.vectorstores import FAISS
from langchain.embeddings import HuggingFaceEmbeddings, OpenAIEmbeddings
from langchain.docstore.document import Document
import os
import pickle
from langchain.vectorstores import FAISS


# Set up embeddings (Sentence Transformers)
# embedding_model = HuggingFaceEmbeddings(model_name="all-MiniLM-L6-v2")
from openai import AzureOpenAI
from langchain_openai import AzureOpenAIEmbeddings
import os
from dotenv import load_dotenv

load_dotenv()

embedding_model = AzureOpenAIEmbeddings(
    model="text-embedding-3-small",  # or your deployed model name
    deployment=os.getenv("AZURE_OPENAI_EMBEDDING_DEPLOYMENT"),
    api_key=os.getenv("AZURE_OPENAI_API_KEY"),
    azure_endpoint=os.getenv("AZURE_OPENAI_ENDPOINT"),  # ✅ FIXED HERE
    api_version=os.getenv("AZURE_OPENAI_API_VERSION")
)

# Chunking config
text_splitter = RecursiveCharacterTextSplitter(
    chunk_size=700,
    chunk_overlap=100,
    separators=["\n\n", "\n", ".", " "]
)

def chunk_and_store(text, persist_path, metadata=None):
    # Wrap raw text into LangChain Document
    docs = [Document(page_content=text, metadata=metadata or {})]

    # Split into chunks
    chunks = text_splitter.split_documents(docs)

    # Create vector DB
    vector_db = FAISS.from_documents(chunks, embedding_model)

    # Save DB
    os.makedirs(os.path.dirname(persist_path), exist_ok=True)
    vector_db.save_local(persist_path)

def load_vector_db(path):
    return FAISS.load_local(path, embedding_model, allow_dangerous_deserialization=True)

# def retrieve_chunks(vector_db, query, k=10):
#     results = vector_db.similarity_search(query, k=k)
#     return [doc.page_content for doc in results]
def retrieve_chunks(vectordb: FAISS, query: str, k: int = 25):
    return vectordb.similarity_search_with_score(query, k=k)
