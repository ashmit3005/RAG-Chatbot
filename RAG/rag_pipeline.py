from langchain_community.document_loaders import TextLoader
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_community.vectorstores import FAISS
from langchain.chains import RetrievalQA
from langchain_huggingface import HuggingFaceEmbeddings

from transformers import pipeline 
from textblob import TextBlob
from language_tool_python import LanguageTool, utils
import os
import spacy

def load_and_chunk_documents():
    current_dir = os.path.dirname(os.path.abspath(__file__))
    file_paths = [os.path.join(current_dir, f) for f in ['carss.txt', 'trainss.txt']]
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

def retrieve_relevant_context(vectorstore, question, k=3):
    # Retrieve multiple documents and merge them
    relevant_docs = vectorstore.similarity_search(question, k=k)
    # Join contexts with clear separation
    merged_context = "\n\n".join([doc.page_content for doc in relevant_docs])
    return merged_context


def process_query(question):
    nlp = spacy.load("en_core_web_sm")
    doc = nlp(question)
    
    # Extract key entities and technical terms
    entities = [ent.text for ent in doc.ents]
    
    # Extract key noun phrases
    noun_phrases = [chunk.text for chunk in doc.noun_chunks]
    
    # Enhance original query with extracted information
    processed_query = question
    return processed_query, entities, noun_phrases

def validate_response(response):
    # Initialize grammar checker
    tool = LanguageTool('en-US')
    matches = tool.check(response)

    # Corrected response
    corrected_response = utils.correct(response, matches)
    
    # Use TextBlob for sentiment and subjectivity analysis
    blob = TextBlob(response)
    
    # Create validation report
    validation = {
        "grammar_error_count": len(matches),
        "corrected_text": corrected_response
    }
    
    return corrected_response, validation


def build_rag_pipeline(vectorstore):
  
    qa_pipeline = pipeline("question-answering", model="distilbert-base-cased-distilled-squad")
    
    def qa_function(question):
        # Process query
        processed_query, entities, noun_phrases = process_query(question)

        # Retrieve context with processed query
        context = retrieve_relevant_context(vectorstore, processed_query, k=3)

        if context:
            # Generate response
            result = qa_pipeline(question=processed_query, context=context)
            raw_answer = result['answer']

            # Validate and improve response
            corrected_answer, validation_report = validate_response(raw_answer)

            # Log validation metrics
            print(f"Validation report: {validation_report}")

            return corrected_answer
        else:
            return "No relevant information found"

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
