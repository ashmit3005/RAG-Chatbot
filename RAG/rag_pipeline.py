from langchain_community.document_loaders import PyPDFLoader
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_community.vectorstores import FAISS
import os
import glob
import openai


def load_and_chunk_documents(recent_files=None):
    current_dir = os.path.dirname(os.path.abspath(__file__))
    uploaded_dir = os.path.join(current_dir, 'Uploaded Documents')
    database_dir = os.path.join(current_dir, 'Documents Database')
    
    documents = []

    # Load from Documents Database
    database_files = glob.glob(os.path.join(database_dir, '*.pdf'))
    for file_path in database_files:
        try:
            loader = PyPDFLoader(file_path)
            docs = loader.load()
            # Add metadata for database documents
            for doc in docs:
                doc.metadata['source'] = 'database'
                doc.metadata['is_recent'] = False
            documents.extend(docs)
            print(f"Loaded database file: {file_path}")
        except Exception as e:
            print(f"Error loading database file {file_path}: {e}")

    # Load from Uploaded Documents
    uploaded_files = glob.glob(os.path.join(uploaded_dir, '*.pdf'))
    for file_path in uploaded_files:
        try:
            loader = PyPDFLoader(file_path)
            docs = loader.load()
            filename = os.path.basename(file_path)
            # Add metadata for uploaded documents
            for doc in docs:
                doc.metadata['source'] = 'uploaded'
                doc.metadata['is_recent'] = recent_files and filename in recent_files
            documents.extend(docs)
            print(f"Loaded uploaded file: {file_path} {'(recent)' if doc.metadata['is_recent'] else ''}")
        except Exception as e:
            print(f"Error loading uploaded file {file_path}: {e}")
    
    if not documents:
        raise RuntimeError("No documents loaded from either directory.")

    # Split into chunks
    text_splitter = RecursiveCharacterTextSplitter(
        chunk_size=1000,
        chunk_overlap=200,
        separators=["\n\n", "\n", ".", "!", "?", ",", " ", ""]
    )
    chunks = text_splitter.split_documents(documents)
    print(f"Created {len(chunks)} chunks from {len(database_files) + len(uploaded_files)} documents")
    return chunks


def generate_embeddings(chunks):
    embedding_model = HuggingFaceEmbeddings(
        model_name="sentence-transformers/all-MiniLM-L6-v2"
    )
    return embedding_model, None


def create_vector_store(chunks, embedding_model):
    vectorstore = FAISS.from_documents(documents=chunks, embedding=embedding_model)
    return vectorstore


def build_rag_pipeline(vectorstore):
    # Initialize OpenAI client
    # Make sure to set OPENAI_API_KEY environment variable or pass it directly
    
    client = openai.OpenAI()  # Will use OPENAI_API_KEY from environment
    
    def qa_function(question):
        try:
            # Get relevant documents
            relevant_docs = vectorstore.similarity_search(
                question,
                k=3
            )
            
            if not relevant_docs:
                return "I couldn't find any relevant information in the documents."
            
            # Combine contexts
            context = " ".join([doc.page_content for doc in relevant_docs])
            
            # Use OpenAI API for question answering
            response = client.chat.completions.create(
                model="gpt-4o-mini",  # You can change to other models like "gpt-4" if needed
                messages=[
                    {"role": "system", "content": "You are a helpful assistant that answers questions based on the provided context. Only use information from the context to answer."},
                    {"role": "user", "content": f"Context: {context}\n\nQuestion: {question}\n\nAnswer:"}
                ],
                max_tokens=150,
                temperature=0.3
            )
            
            answer = response.choices[0].message.content.strip()
            
            # If answer is too short, return relevant context
            if len(answer) < 3:
                return relevant_docs[0].page_content[:200] + "..."
                
            return answer
            
        except Exception as e:
            print(f"Error in QA pipeline: {e}")
            return "Sorry, I encountered an error while processing your question."

    return qa_function


def test_rag_pipeline(rag_pipeline):
    questions = [
        "Who is the 45th president of the USA?",
        "What year was the Shinkansen name first used?",
    ]

    for question in questions:
        response = rag_pipeline(question)
        print(f"Q: {question}\nA: {response}")


if __name__ == "__main__":
    try:
   
        chunks = load_and_chunk_documents()
        
        
        embedding_model, embeddings = generate_embeddings(chunks)

 
        vectorstore = create_vector_store(chunks, embedding_model)

        
        rag_pipeline = build_rag_pipeline(vectorstore)
        test_rag_pipeline(rag_pipeline)
    except Exception as e:
        print(f"Error in RAG pipeline execution: {e}")
