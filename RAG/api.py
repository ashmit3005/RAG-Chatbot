import os
import json
from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from typing import List, Optional, Dict, Any
import uvicorn
from werkzeug.utils import secure_filename
from rag_pipeline import load_and_chunk_documents, generate_embeddings, create_vector_store, build_rag_pipeline, format_response, load_single_document, update_vector_store
from langchain_community.chat_message_histories import ChatMessageHistory

app = FastAPI()

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allows all origins
    allow_credentials=True,
    allow_methods=["*"],  # Allows all methods
    allow_headers=["*"],  # Allows all headers
)

# Configure upload settings
current_dir = os.path.dirname(os.path.abspath(__file__))
UPLOAD_FOLDER = os.path.join(current_dir, 'Uploaded Documents')
ALLOWED_EXTENSIONS = {'pdf'}

def allowed_file(filename):
    return filename.lower().endswith('.pdf')

# With a session store similar to your example
store = {}

def get_session_history(session_id):
    if session_id not in store:
        store[session_id] = ChatMessageHistory()
    return store[session_id]

# Global variables for the RAG pipeline and its components
global_rag_pipeline = None
global_vectorstore = None
global_embedding_model = None

def initialize_rag_pipeline():
    global global_rag_pipeline, global_vectorstore, global_embedding_model
    try:
        chunks = load_and_chunk_documents()
        global_embedding_model = generate_embeddings(chunks)
        global_vectorstore = create_vector_store(chunks, global_embedding_model)
        global_rag_pipeline = build_rag_pipeline(global_vectorstore)
    except Exception as e:
        global_rag_pipeline = None
        global_vectorstore = None
        global_embedding_model = None

# Initialize the pipeline when starting the server
initialize_rag_pipeline()

@app.post("/api/chat")
async def chat(
    message: Optional[str] = Form(None),
    session_id: str = Form("default"),
    processed_files: Optional[str] = Form(None),
    files: List[UploadFile] = []
):
    global global_rag_pipeline, global_vectorstore, global_embedding_model
    
    try:
        # Process processed_files JSON
        try:
            processed_files_list = json.loads(processed_files) if processed_files else []
        except json.JSONDecodeError:
            processed_files_list = []
        
        # Handle file uploads if present
        uploaded_files = []
        uploaded_file_paths = []
        
        # Ensure the upload directory exists
        os.makedirs(UPLOAD_FOLDER, exist_ok=True)
        
        for file in files:
            if file and file.filename and allowed_file(file.filename):
                try:
                    filename = secure_filename(file.filename)
                    # Skip processing if this file was already processed
                    if filename in processed_files_list:
                        continue
                        
                    filepath = os.path.join(UPLOAD_FOLDER, filename)
                    
                    # Save the file
                    content = await file.read()
                    with open(filepath, "wb") as f:
                        f.write(content)
                    
                    uploaded_files.append(filename)
                    uploaded_file_paths.append(filepath)
                except Exception as e:
                    raise HTTPException(status_code=500, detail=f"Error saving file {file.filename}: {str(e)}")
            else:
                if file and file.filename:
                    raise HTTPException(status_code=400, detail="Invalid file format. Only PDF files are allowed.")
        
        # Get a list of all files referenced in this request (newly uploaded + previously processed)
        all_referenced_files = uploaded_files + processed_files_list
        
        # If files were uploaded and we have an existing vectorstore, add them to it
        if uploaded_file_paths:
            if global_vectorstore is not None and global_embedding_model is not None:
                # Process each new file individually and add to the vectorstore
                for file_path in uploaded_file_paths:
                    new_chunks = load_single_document(file_path)
                    if new_chunks:
                        global_vectorstore = update_vector_store(global_vectorstore, new_chunks, global_embedding_model)
                
                # Update the RAG pipeline with the updated vectorstore
                global_rag_pipeline = build_rag_pipeline(global_vectorstore)
            else:
                # If we don't have a vectorstore yet, initialize the full pipeline
                initialize_rag_pipeline()
            
        # Initialize pipeline if it's not already initialized
        if global_rag_pipeline is None:
            initialize_rag_pipeline()
            
        if global_rag_pipeline is None:
            raise HTTPException(status_code=500, detail="Failed to initialize RAG pipeline")
            
        # Process the query (if no message but files uploaded, acknowledge the upload)
        if not message and all_referenced_files:
            response = f"Files ready to use: {', '.join(all_referenced_files)}"
        else:
            try:
                response = global_rag_pipeline(message, session_id=session_id) if message else "Files uploaded successfully"
            except Exception as e:
                raise HTTPException(status_code=500, detail=f"Error generating response: {str(e)}")
        
        # Create the response data
        response_data = {
            "response": format_response(response),
            "uploaded_files": all_referenced_files  # Include all referenced files in the response
        }

        return response_data
        
    except HTTPException as e:
        # Re-raise FastAPI exceptions
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/upload_new_files")
async def upload_new_files(files: Optional[List[UploadFile]] = File(None)):
    global global_rag_pipeline, global_vectorstore, global_embedding_model
    
    try:
        # Handle file uploads
        uploaded_files = []
        uploaded_file_paths = []
        
        # Check if files were actually provided, even if the parameter is optional
        if not files:
            raise HTTPException(status_code=400, detail="No files provided")
            
        # Ensure the upload directory exists
        os.makedirs(UPLOAD_FOLDER, exist_ok=True)
        
        for file in files:
            if file and file.filename and allowed_file(file.filename):
                try:
                    filename = secure_filename(file.filename)
                    filepath = os.path.join(UPLOAD_FOLDER, filename)
                    
                    # Save the file
                    content = await file.read()
                    with open(filepath, "wb") as f:
                        f.write(content)
                    
                    uploaded_files.append(filename)
                    uploaded_file_paths.append(filepath)
                except Exception as e:
                    raise HTTPException(status_code=500, detail=f"Error saving file {file.filename}: {str(e)}")
            else:
                # If a file object exists but is invalid (e.g., wrong extension)
                if file and file.filename:
                     raise HTTPException(status_code=400, detail=f"Invalid file format for {file.filename}. Only PDF files are allowed.")
                # Handle cases where an item in the list might not be a valid file object (less common)
                else:
                     raise HTTPException(status_code=400, detail="Invalid item received in file list.")

        # Process each new file individually and add to the vectorstore
        if uploaded_file_paths: # Ensure we actually processed some files
            if global_vectorstore is not None and global_embedding_model is not None:
                for file_path in uploaded_file_paths:
                    new_chunks = load_single_document(file_path)
                    if new_chunks:
                        global_vectorstore = update_vector_store(global_vectorstore, new_chunks, global_embedding_model)
                
                # Update the RAG pipeline with the updated vectorstore
                global_rag_pipeline = build_rag_pipeline(global_vectorstore)
            else:
                # If we don't have a vectorstore yet, initialize the full pipeline
                # This path might need review - should uploading initialize if nothing exists?
                # Assuming yes for now based on previous logic.
                initialize_rag_pipeline()
                # We might need to re-process the uploaded files if initialize_rag_pipeline doesn't use them.
                # Adding re-processing logic here if initialization doesn't cover current uploads.
                if global_vectorstore is not None and global_embedding_model is not None:
                     for file_path in uploaded_file_paths:
                         new_chunks = load_single_document(file_path)
                         if new_chunks:
                             global_vectorstore = update_vector_store(global_vectorstore, new_chunks, global_embedding_model)
                     global_rag_pipeline = build_rag_pipeline(global_vectorstore)

        # Check if any files were successfully uploaded before returning success
        if not uploaded_files:
             # This case might occur if all provided files were invalid
             raise HTTPException(status_code=400, detail="No valid files were processed.")

        return {
            "message": f"Successfully uploaded and processed {len(uploaded_files)} file(s): {', '.join(uploaded_files)}",
            "uploaded_files": uploaded_files
        }
        
    except HTTPException as e:
        # Re-raise FastAPI exceptions
        raise
    except Exception as e:
        # Log the exception for debugging
        print(f"Unexpected error in /api/upload_new_files: {e}") # Added basic logging
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == '__main__':
    # Ensure upload directory exists
    os.makedirs(UPLOAD_FOLDER, exist_ok=True)
    uvicorn.run(app, host="0.0.0.0", port=5000)