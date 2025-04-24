import os
import json
from fastapi import FastAPI, UploadFile, File, Form, HTTPException, Path
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from typing import List, Optional, Dict, Any
import uvicorn
from werkzeug.utils import secure_filename
# Import FAISS specifically if needed for type checking
from langchain_community.vectorstores import FAISS
from rag_pipeline import (
    load_and_chunk_documents, generate_embeddings, create_vector_store,
    build_rag_pipeline, format_response, load_single_document, update_vector_store
)
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
            
        print(f"Formatted response: {format_response(response)}")  # Added logging for debugging
        
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

# --- New Endpoint for Deleting Files ---
@app.delete("/api/delete_file/{filename}")
async def delete_file(filename: str = Path(..., title="The name of the file to delete")):
    global global_vectorstore, global_rag_pipeline

    secured_filename = secure_filename(filename) # Sanitize filename
    filepath = os.path.join(UPLOAD_FOLDER, secured_filename)

    # 1. Delete the physical file
    file_deleted_from_server = False
    if os.path.exists(filepath):
        try:
            os.remove(filepath)
            print(f"Deleted file: {filepath}")
            file_deleted_from_server = True
        except OSError as e:
            print(f"Error deleting file {filepath}: {e}")
            # Decide if failure to delete file should prevent vector deletion attempt
            # For now, we'll raise immediately if file deletion fails.
            raise HTTPException(status_code=500, detail=f"Error deleting file from server: {str(e)}")
    else:
        # File might already be deleted or never existed, proceed to check vector store
        print(f"File not found on server, attempting vector deletion: {filepath}")
        # If the file wasn't found, we still might want to clean up vectors if they exist

    # 2. Delete vectors from the vector store (FAISS specific logic)
    deleted_vector_count = 0
    if global_vectorstore and isinstance(global_vectorstore, FAISS):
        try:
            # FAISS specific deletion: Find docstore IDs by iterating through metadata
            docstore_ids_to_delete = [] # Changed variable name for clarity
            if hasattr(global_vectorstore, 'index_to_docstore_id') and hasattr(global_vectorstore, 'docstore'):
                index_to_docstore = global_vectorstore.index_to_docstore_id
                docstore = global_vectorstore.docstore

                # Iterate through the mapping to find relevant docstore IDs
                for index_id, docstore_id in index_to_docstore.items():
                    # Retrieve the document/metadata from the docstore using its ID
                    if hasattr(docstore, '_dict') and docstore_id in docstore._dict:
                        doc_metadata = docstore._dict[docstore_id].metadata
                        # Check if the 'filename' in metadata matches the one to delete
                        if doc_metadata.get('filename') == secured_filename:
                            # *** CHANGE: Collect the docstore_id (UUID) instead of the index_id (int) ***
                            docstore_ids_to_delete.append(docstore_id)
                    else:
                         print(f"Warning: Could not access document metadata for docstore_id {docstore_id}")
            else:
                 print("Warning: FAISS vector store structure (index_to_docstore_id or docstore) not found as expected.")


            if docstore_ids_to_delete:
                # Remove duplicates just in case (though unlikely for docstore IDs)
                unique_docstore_ids = list(set(docstore_ids_to_delete))
                print(f"Attempting to delete {len(unique_docstore_ids)} vectors (by docstore ID) for file: {secured_filename}")

                # *** CHANGE: Use the collected docstore_ids with the delete method ***
                delete_result = global_vectorstore.delete(ids=unique_docstore_ids)

                if delete_result: # Check if deletion was successful
                    # Note: FAISS delete might remove more vectors than docstore IDs if chunks map to multiple vectors
                    # We'll report based on the number of unique docstore IDs targeted.
                    deleted_vector_count = len(unique_docstore_ids)
                    print(f"Successfully processed deletion request for {deleted_vector_count} docstore IDs for file: {secured_filename}")

                    # Rebuild the RAG pipeline with the modified vector store
                    global_rag_pipeline = build_rag_pipeline(global_vectorstore)
                    print("RAG pipeline updated after vector deletion.")
                else:
                    print(f"FAISS delete operation returned False for file: {secured_filename}. Vectors may not have been deleted.")
                    # Check if the error message indicates missing IDs again
                    # It's possible some IDs were already deleted or became invalid
                    # Consider treating 'False' with missing IDs as a partial success or warning
                    # For now, raising an error for clarity.
                    raise HTTPException(status_code=500, detail=f"FAISS failed to delete vectors for file '{secured_filename}'. Check logs for details.")

            else:
                print(f"No vectors found in the store for file: {secured_filename}")

        except NotImplementedError:
             # This shouldn't happen if it's FAISS, but keep as a safeguard
             print(f"Warning: Vector store deletion method not implemented as expected.")
             raise HTTPException(status_code=501, detail="Vector deletion not implemented correctly for the vector store.")
        except AttributeError as e:
             print(f"Error accessing FAISS internal structure: {e}. This might be due to LangChain version changes.")
             raise HTTPException(status_code=500, detail=f"Error accessing vector store internals for deletion: {str(e)}")
        except Exception as e:
            print(f"Error deleting vectors for file {secured_filename}: {e}")
            # Decide if this should be a fatal error or just a warning
            raise HTTPException(status_code=500, detail=f"Error deleting vectors from store: {str(e)}")
    elif global_vectorstore:
         print(f"Warning: Vector store type ({type(global_vectorstore)}) not handled for deletion.")
         # Optionally raise an error if only FAISS is expected
         # raise HTTPException(status_code=501, detail=f"Deletion not implemented for vector store type: {type(global_vectorstore)}")
    else:
        print("Vector store not initialized, skipping vector deletion.")

    # Construct the simplified success message
    simple_success_message = f"Successfully removed file '{secured_filename}'."

    return JSONResponse(
        content={
            "message": simple_success_message, # Use the simplified message
            "filename": secured_filename,
            "vectors_deleted": deleted_vector_count # Keep reporting count for potential debugging/logging
        },
        status_code=200
    )

if __name__ == '__main__':
    # Ensure upload directory exists
    os.makedirs(UPLOAD_FOLDER, exist_ok=True)
    uvicorn.run(app, host="0.0.0.0", port=5000)