from langchain_community.document_loaders import PyPDFLoader
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_community.vectorstores import FAISS
from langchain_huggingface import HuggingFaceEmbeddings
from transformers import pipeline
import os
import glob


def load_and_chunk_documents():
    # Get path to Documents Database folder
    current_dir = os.path.dirname(os.path.abspath(__file__))
    database_dir = os.path.join(current_dir, 'Documents Database')
    
    # Find all PDF files
    pdf_files = glob.glob(os.path.join(database_dir, '*.pdf'))
    documents = []

    # Load each PDF
    for file_path in pdf_files:
        try:
            loader = PyPDFLoader(file_path)
            documents.extend(loader.load())
            print(f"Successfully loaded: {file_path}")
        except Exception as e:
            print(f"Error loading PDF file {file_path}: {e}")
    
    if not documents:
        raise RuntimeError("No documents loaded. Check if there are PDF files in the Documents Database directory.")

    # Split documents into chunks
    text_splitter = RecursiveCharacterTextSplitter(
        chunk_size=1000,
        chunk_overlap=200,
        separators=["\n\n", "\n", ".", "!", "?", ",", " ", ""]
    )
    chunks = text_splitter.split_documents(documents)
    print(f"Created {len(chunks)} chunks from {len(pdf_files)} documents")
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
    # Initialize a simpler QA pipeline
    qa_model = pipeline(
        "question-answering",
        model="deepset/roberta-base-squad2",
        tokenizer="deepset/roberta-base-squad2"
    )
    
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
            
            # Get answer using QA pipeline
            result = qa_model(
                question=question,
                context=context,
                max_answer_len=100
            )
            
            answer = result['answer'].strip()
            
            # If answer is too short or just punctuation, return relevant context
            if len(answer) < 3 or answer in '.,!?':
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
