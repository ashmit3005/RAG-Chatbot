import os
import json
from flask import Flask, request, jsonify, session
from flask_cors import CORS
from werkzeug.utils import secure_filename
from rag_pipeline import load_and_chunk_documents, generate_embeddings, create_vector_store, build_rag_pipeline, format_response, load_single_document, update_vector_store
from langchain_community.chat_message_histories import ChatMessageHistory

app = Flask(__name__)
CORS(app)
app.secret_key = os.urandom(24)  # For session management

# Configure upload settings
current_dir = os.path.dirname(os.path.abspath(__file__))
UPLOAD_FOLDER = os.path.join(current_dir, 'Uploaded Documents')
ALLOWED_EXTENSIONS = {'pdf'}

print(f"Setting upload folder to: {UPLOAD_FOLDER}")

app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max file size

def allowed_file(filename):
    return filename.lower().endswith('.pdf')

# Global variables for the RAG pipeline and its components
global_rag_pipeline = None
global_vectorstore = None
global_embedding_model = None

# With a session store similar to your example
store = {}

def get_session_history(session_id):
    if session_id not in store:
        store[session_id] = ChatMessageHistory()
    return store[session_id]

def initialize_rag_pipeline():
    global global_rag_pipeline, global_vectorstore, global_embedding_model
    try:
        chunks = load_and_chunk_documents()
        global_embedding_model = generate_embeddings(chunks)
        global_vectorstore = create_vector_store(chunks, global_embedding_model)
        global_rag_pipeline = build_rag_pipeline(global_vectorstore)
        print("RAG pipeline initialized successfully")
    except Exception as e:
        print(f"Error initializing RAG pipeline: {e}")
        global_rag_pipeline = None
        global_vectorstore = None
        global_embedding_model = None

# Initialize the pipeline when starting the server
initialize_rag_pipeline()

@app.route('/api/chat', methods=['POST'])
def chat():
    global global_rag_pipeline, global_vectorstore, global_embedding_model
    
    try:
        # Debug logging
        print("Received request")
        
        # Get the message text (can be empty)
        message = request.form.get('message', '')

        # Get session ID (you could use cookies or other methods)
        session_id = request.form.get('session_id', 'default')
        
        # Check if there are any previously processed files
        processed_files_json = request.form.get('processedFiles', '[]')
        try:
            processed_files = json.loads(processed_files_json) if processed_files_json else []
            if processed_files:
                print(f"Already processed files: {processed_files}")
        except json.JSONDecodeError:
            processed_files = []
            print("Error parsing processed files JSON")
        
        # Handle file uploads if present
        uploaded_files = []
        uploaded_file_paths = []
        
        # Look for files with indexed names (file0, file1, etc.)
        file_keys = [key for key in request.files.keys() if key.startswith('file')]
        
        if file_keys:
            # Ensure the upload directory exists
            os.makedirs(UPLOAD_FOLDER, exist_ok=True)
            
            for key in file_keys:
                file = request.files[key]
                if file and file.filename and allowed_file(file.filename):
                    try:
                        filename = secure_filename(file.filename)
                        # Skip processing if this file was already processed
                        if filename in processed_files:
                            print(f"Skipping already processed file: {filename}")
                            continue
                            
                        filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
                        file.save(filepath)
                        uploaded_files.append(filename)
                        uploaded_file_paths.append(filepath)
                        print(f"Successfully saved file to: {filepath}")
                    except Exception as e:
                        print(f"Error saving file {file.filename}: {e}")
                        return jsonify({"error": f"Error saving file {file.filename}: {str(e)}"}), 500
        
        # Get a list of all files referenced in this request (newly uploaded + previously processed)
        all_referenced_files = uploaded_files + processed_files
        
        # If files were uploaded and we have an existing vectorstore, add them to it
        if uploaded_file_paths:
            print(f"New files uploaded: {uploaded_files}")
            if global_vectorstore is not None and global_embedding_model is not None:
                # Process each new file individually and add to the vectorstore
                for file_path in uploaded_file_paths:
                    new_chunks = load_single_document(file_path)
                    if new_chunks:
                        global_vectorstore = update_vector_store(global_vectorstore, new_chunks, global_embedding_model)
                
                # Update the RAG pipeline with the updated vectorstore
                global_rag_pipeline = build_rag_pipeline(global_vectorstore)
                print("Updated RAG pipeline with new documents")
            else:
                # If we don't have a vectorstore yet, initialize the full pipeline
                initialize_rag_pipeline()
            
        # Initialize pipeline if it's not already initialized
        if global_rag_pipeline is None:
            print("Initializing RAG pipeline")
            initialize_rag_pipeline()
            
        # Process the query (if no message but files uploaded, acknowledge the upload)
        print(f"Processing message: '{message}'")
        if not message and all_referenced_files:
            response = f"Files ready to use: {', '.join(all_referenced_files)}"
        else:
            try:
                response = global_rag_pipeline(message, session_id=session_id) if message else "Files uploaded successfully"
                print(f"Generated raw response: '{response[0:50]}...'") # Print first 50 chars of response
            except Exception as e:
                print(f"Error generating response: {e}")
                return jsonify({"error": f"Error generating response: {str(e)}"}), 500
        
        # Create the response data
        response_data = {
            "response": format_response(response),
            "uploaded_files": all_referenced_files  # Include all referenced files in the response
        }

        print("Sending response")
        return jsonify(response_data)
        
    except Exception as e:
        print(f"Error processing request: {e}")
        import traceback
        traceback.print_exc()  # Print full stack trace
        return jsonify({"error": str(e)}), 500

@app.route('/api/upload_new_files', methods=['POST'])
def upload_new_files():
    global global_rag_pipeline, global_vectorstore, global_embedding_model
    
    try:
        # Handle file uploads
        uploaded_files = []
        uploaded_file_paths = []
        
        # Look for files with indexed names (file0, file1, etc.)
        file_keys = [key for key in request.files.keys() if key.startswith('file')]
        
        if not file_keys:
            return jsonify({"error": "No files provided"}), 400
            
        # Ensure the upload directory exists
        os.makedirs(UPLOAD_FOLDER, exist_ok=True)

        print(file_keys)
        
        for key in file_keys:
            file = request.files[key]
            if file and file.filename and allowed_file(file.filename):
                try:
                    filename = secure_filename(file.filename)
                    filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
                    file.save(filepath)
                    uploaded_files.append(filename)
                    uploaded_file_paths.append(filepath)
                    print(f"Successfully saved file to: {filepath}")
                except Exception as e:
                    print(f"Error saving file {file.filename}: {e}")
                    return jsonify({"error": f"Error saving file {file.filename}: {str(e)}"}), 500
            else:
                return jsonify({"error": f"Invalid file format. Only PDF files are allowed."}), 400
        
        # Process each new file individually and add to the vectorstore
        if global_vectorstore is not None and global_embedding_model is not None:
            for file_path in uploaded_file_paths:
                new_chunks = load_single_document(file_path)
                if new_chunks:
                    global_vectorstore = update_vector_store(global_vectorstore, new_chunks, global_embedding_model)
            
            # Update the RAG pipeline with the updated vectorstore
            global_rag_pipeline = build_rag_pipeline(global_vectorstore)
            print("Updated RAG pipeline with new documents")
        else:
            # If we don't have a vectorstore yet, initialize the full pipeline
            initialize_rag_pipeline()
        
        return jsonify({
            "message": f"Successfully uploaded and processed {len(uploaded_files)} file(s): {', '.join(uploaded_files)}",
            "uploaded_files": uploaded_files
        })
        
    except Exception as e:
        print(f"Error processing file upload: {e}")
        import traceback
        traceback.print_exc()  # Print full stack trace
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    # Ensure upload directory exists
    os.makedirs(UPLOAD_FOLDER, exist_ok=True)
    print(f"Upload directory set to: {UPLOAD_FOLDER}")
    app.run(host='0.0.0.0', port=5000, debug=False)