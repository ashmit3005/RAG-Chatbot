from langchain_community.document_loaders import TextLoader
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_community.vectorstores import FAISS
from langchain.chains import RetrievalQA
from langchain_huggingface import HuggingFaceEmbeddings

from transformers import pipeline 


def load_and_chunk_documents():
    file_paths = ['carss.txt', 'trainss.txt'] 
    documents = []


    for file_path in file_paths:
        try:
            
            loader = TextLoader(file_path, encoding='utf-8')
            documents.extend(loader.load()) 
        except Exception as e:
            print(f"Error loading file {file_path}: {e}")
    
    if not documents:
        raise RuntimeError("No documents loaded. Check file paths and content.")

    
    text_splitter = RecursiveCharacterTextSplitter(chunk_size=500, chunk_overlap=50)
    return text_splitter.split_documents(documents)


def generate_embeddings(chunks):
    
    embedding_model = HuggingFaceEmbeddings(model_name="sentence-transformers/all-MiniLM-L6-v2")
    embeddings = embedding_model.embed_documents([chunk.page_content for chunk in chunks])
    return embedding_model, embeddings


def create_vector_store(chunks, embedding_model):
  
    vectorstore = FAISS.from_documents(documents=chunks, embedding=embedding_model)
    return vectorstore


def build_rag_pipeline(vectorstore):
  
    qa_pipeline = pipeline("question-answering", model="distilbert-base-cased-distilled-squad")
    
    def qa_function(question):
       
        relevant_docs = vectorstore.similarity_search(question, k=1)  
        if relevant_docs:
            context = relevant_docs[0].page_content
            result = qa_pipeline(question=question, context=context)
            return result['answer']
        else:
            return "No relevant documents found."

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
