from flask import Flask, request, jsonify
from flask_cors import CORS
from rag_pipeline import load_and_chunk_documents, generate_embeddings, create_vector_store, build_rag_pipeline

app = Flask(__name__)
CORS(app)

# Initialize RAG pipeline
try:
    chunks = load_and_chunk_documents()
    embedding_model, embeddings = generate_embeddings(chunks)
    vectorstore = create_vector_store(chunks, embedding_model)
    rag_pipeline = build_rag_pipeline(vectorstore)
except Exception as e:
    print(f"Error initializing RAG pipeline: {e}")
    rag_pipeline = None

@app.route('/api/chat', methods=['POST'])
def chat():
    if not rag_pipeline:
        return jsonify({"error": "RAG pipeline not initialized"}), 500
        
    data = request.json
    question = data.get('message')
    
    if not question:
        return jsonify({"error": "No message provided"}), 400
        
    try:
        response = rag_pipeline(question)
        return jsonify({"response": response})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000) 