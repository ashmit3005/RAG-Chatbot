import os
from flask import Flask, request, jsonify
from flask_cors import CORS
from werkzeug.utils import secure_filename
from rag_pipeline import load_and_chunk_documents, generate_embeddings, create_vector_store, build_rag_pipeline

app = Flask(__name__)
CORS(app)

# Configure upload settings
current_dir = os.path.dirname(os.path.abspath(__file__))  # Gets the RAG directory path
UPLOAD_FOLDER = os.path.join(current_dir, 'Uploaded Documents')
ALLOWED_EXTENSIONS = {'pdf'}

# Debug print to verify the path
print(f"Setting upload folder to: {UPLOAD_FOLDER}")

app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max file size

def allowed_file(filename):
    return filename.lower().endswith('.pdf')

# Initialize global RAG pipeline
global_rag_pipeline = None

def initialize_rag_pipeline():
    global global_rag_pipeline
    try:
        chunks = load_and_chunk_documents()
        embedding_model, embeddings = generate_embeddings(chunks)
        vectorstore = create_vector_store(chunks, embedding_model)
        global_rag_pipeline = build_rag_pipeline(vectorstore)
    except Exception as e:
        print(f"Error initializing RAG pipeline: {e}")
        global_rag_pipeline = None

# Initialize the pipeline when starting the server
initialize_rag_pipeline()

@app.route('/api/chat', methods=['POST'])
def chat():
    global global_rag_pipeline
    
    try:
        # Debug logging
        print("Received request")
        print("Form data:", request.form)
        print("Files:", request.files)
        
        # Get the message text (can be empty)
        message = request.form.get('message', '')
        
        # Handle file uploads if present
        uploaded_files = []
        
        # Look for files with indexed names (file0, file1, etc.)
        file_keys = [key for key in request.files.keys() if key.startswith('file')]
        
        if file_keys:
            # Ensure the upload directory exists
            os.makedirs(UPLOAD_FOLDER, exist_ok=True)
            
            for key in file_keys:
                file = request.files[key]
                if file and file.filename:
                    try:
                        filename = secure_filename(file.filename)
                        filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
                        file.save(filepath)
                        uploaded_files.append(filename)
                        print(f"Successfully saved file to: {filepath}")
                    except Exception as e:
                        print(f"Error saving file {file.filename}: {e}")
                        return jsonify({"error": f"Error saving file {file.filename}: {str(e)}"}), 500
        
        # If files were uploaded, reinitialize the pipeline
        if uploaded_files:
            print(f"New files uploaded: {uploaded_files}")
            initialize_rag_pipeline()
        
        # Initialize pipeline if it's not already initialized
        if global_rag_pipeline is None:
            initialize_rag_pipeline()
            
        if global_rag_pipeline is None:
            return jsonify({"error": "Failed to initialize RAG pipeline"}), 500
            
        # Process the query (if no message but files uploaded, acknowledge the upload)
        if not message and uploaded_files:
            response = f"Successfully uploaded files: {', '.join(uploaded_files)}"
        else:
            response = global_rag_pipeline(message) if message else "Files uploaded successfully"
        
        return jsonify({
            "response": response,
            "uploaded_files": uploaded_files
        })
        
    except Exception as e:
        print(f"Error processing request: {e}")
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    # Ensure upload directory exists
    os.makedirs(UPLOAD_FOLDER, exist_ok=True)
    print(f"Upload directory set to: {UPLOAD_FOLDER}")
    app.run(host='0.0.0.0', port=5000, debug=True) 