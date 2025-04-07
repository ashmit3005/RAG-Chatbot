from langchain_community.document_loaders import PyPDFLoader
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_community.vectorstores import FAISS
from langchain_openai import OpenAIEmbeddings
import os
import glob
import openai
import re
import string


def preprocess_text(text):
    """
    Preprocess text to improve quality for embedding and retrieval.
    """
    if not text or not isinstance(text, str):
        return text
    
    # Convert to lowercase
    text = text.lower()
    
    # Remove extra whitespace
    text = re.sub(r'\s+', ' ', text)
    
    # Remove URLs
    text = re.sub(r'http[s]?://\S+', '', text)
    
    # Remove email addresses
    text = re.sub(r'\S+@\S+', '', text)
    
    # Remove special characters but keep periods, question marks, etc.
    text = re.sub(r'[^\w\s.,?!;:()\-\'"]', ' ', text)
    
    # Remove extra punctuation 
    text = re.sub(r'([.,!?;:])\1+', r'\1', text)
    
    # Fix spacing around punctuation
    text = re.sub(r'\s([.,!?;:])', r'\1', text)
    
    # Clean up 
    text = text.strip()
    
    return text


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
                # Apply preprocessing to document content
                doc.page_content = preprocess_text(doc.page_content)
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
                # Apply preprocessing to document content
                doc.page_content = preprocess_text(doc.page_content)
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
    # Make sure query text is preprocessed the same way for consistency
    embedding_model = OpenAIEmbeddings(
        model="text-embedding-3-large",  # Using OpenAI's most powerful embedding model
    )
    return embedding_model, None


def create_vector_store(chunks, embedding_model):
    vectorstore = FAISS.from_documents(documents=chunks, embedding=embedding_model)
    return vectorstore


def build_rag_pipeline(vectorstore, existing_history=None):
    # Initialize OpenAI client
    # Make sure to set OPENAI_API_KEY environment variable or pass it directly
    
    client = openai.OpenAI()  # Will use OPENAI_API_KEY from environment
    
    # Initialize conversation history, using existing history if provided
    conversation_history = existing_history if existing_history is not None else []
    
    def qa_function(question, reset_conversation=False):
        nonlocal conversation_history
        
        # Reset conversation if requested
        if reset_conversation:
            conversation_history.clear()
            return "Conversation history has been reset."
        
        try:
            # Get relevant documents
            relevant_docs = vectorstore.similarity_search(
                question,
                k=3
            )
            
            if not relevant_docs:
                response_text = "I couldn't find any relevant information in the documents."
                conversation_history.append({"role": "user", "content": question})
                conversation_history.append({"role": "assistant", "content": response_text})
                return response_text
            
            # Combine contexts
            context = " ".join([doc.page_content for doc in relevant_docs])
            
            # Construct messages for the API call
            messages = [
                {"role": "system", 
                 "content": "You are a helpful assistant that answers questions based ONLY on the provided context. \
                Use information ONLY from the context and remember previous parts of the conversation when answering."}
            ]
            
            # Add conversation history (limited to last 10 exchanges to manage token limit)
            if conversation_history:
                messages.extend(conversation_history[-10:])
                
            # Add the current question with context
            messages.append({"role": "user", "content": f"Context: {context}\n\nQuestion: {question}\n\nAnswer:"})
            
            # Use OpenAI API for question answering
            response = client.chat.completions.create(
                model="gpt-4o",  # Best option for context adherence
                messages=messages,
                max_tokens=800,
                temperature=0.1
            )
            
            answer = response.choices[0].message.content.strip()
            
            # If answer is too short, return relevant context
            if len(answer) < 3:
                answer = relevant_docs[0].page_content[:200] + "..."
            
            # Update conversation history
            conversation_history.append({"role": "user", "content": question})
            conversation_history.append({"role": "assistant", "content": answer})
                
            return answer
            
        except Exception as e:
            print(f"Error in QA pipeline: {e}")
            error_msg = "Sorry, I encountered an error while processing your question."
            conversation_history.append({"role": "user", "content": question})
            conversation_history.append({"role": "assistant", "content": error_msg})
            return error_msg

    return qa_function


def test_rag_pipeline(rag_pipeline):
    # Test with conversational queries that build upon each other
    conversation = [
        "Who is the 45th president of the USA?",
        "When did he take office?",
        "What were some major policies during his term?",
        "What year was the Shinkansen name first used?",
        "How fast can these trains go?",
    ]

    print("Testing conversational capabilities:\n")
    for question in conversation:
        response = rag_pipeline(question)
        print(f"Q: {question}")
        print(f"A: {response}")
        print("-" * 50)


if __name__ == "__main__":
    try:
   
        chunks = load_and_chunk_documents()
        
        
        embedding_model, embeddings = generate_embeddings(chunks)

 
        vectorstore = create_vector_store(chunks, embedding_model)

        
        rag_pipeline = build_rag_pipeline(vectorstore)
        test_rag_pipeline(rag_pipeline)
    except Exception as e:
        print(f"Error in RAG pipeline execution: {e}")
