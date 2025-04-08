from langchain_community.document_loaders import PyPDFLoader
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_community.vectorstores import FAISS
from langchain.memory import ConversationBufferMemory
from langchain_openai import OpenAIEmbeddings
import os
import glob
import openai
import re
from nltk import pos_tag, ne_chunk
from nltk.corpus import stopwords
from nltk.tokenize import word_tokenize
from nltk.stem import WordNetLemmatizer

# Helper function to convert NLTK POS tags to WordNet POS tags
def get_wordnet_pos(tag):
    if tag.startswith('J'):
        return 'a'  # adjective
    elif tag.startswith('V'):
        return 'v'  # verb
    elif tag.startswith('N'):
        return 'n'  # noun
    elif tag.startswith('R'):
        return 'r'  # adverb
    else:
        return 'n'  # default to noun

def preprocess_text(text, is_document=False):
    """
    Enhanced text preprocessing using NLTK for improved quality in embedding and retrieval.

    Args:
        text (str): The text to preprocess
        is_document (bool): Whether this is a document (True) or query (False)
        
    Returns:
        tuple: (processed_text, entities_dict)
    """
    if not text or not isinstance(text, str):
        return text
    
    # Convert to lowercase
    text = text.lower()

    # Basic normalization
    text = text.strip()
    
    # Remove extra whitespace
    text = re.sub(r'\s+', ' ', text)
    
    # Remove URLs
    text = re.sub(r'http[s]?://\S+', '', text)
    
    # Remove email addresses
    text = re.sub(r'\S+@\S+', '', text)
    
    # Remove special characters but keep periods, question marks, etc.
    text = re.sub(r'[^\w\s.,?!;:()\-\'"]', ' ', text)

    # Remove HTML code
    text = re.sub(r'<[^>]+>', ' ', text)
    
    # Tokenize the text
    tokens = word_tokenize(text)

    # Tag parts of speech
    pos_tags = pos_tag(tokens)

    # Named entity recognition (NER) 
    ne_chunked = ne_chunk(pos_tags)

    # Extract entities by type
    entities = {
        'PERSON': [], 'ORGANIZATION': [], 'LOCATION': [], 
        'DATE': [], 'TIME': [], 'MONEY': [], 'PERCENT': [], 
        'FACILITY': [], 'GPE': []
    }

    # Process the named entities tree
    for chunk in ne_chunked:
        if hasattr(chunk, 'label'):
            entity_type = chunk.label()
            entity_text = ' '.join(c[0] for c in chunk)
            if entity_type in entities:
                entities[entity_type].append(entity_text)

    # Perform more extensive preprocessing for documents
    if is_document:
        # Get stopwords
        stop_words = set(stopwords.words('english'))
        
        # Filter out stopwords and lemmatize tokens - but keep relevant ones for context
        filtered_tokens = [(word, tag) for word, tag in pos_tags if word.lower() not in stop_words]

        # Initialize lemmatizer 
        lemmatizer = WordNetLemmatizer()
        processed_tokens = [lemmatizer.lemmatize(word, get_wordnet_pos(tag)) for word, tag in filtered_tokens]

        processed_text =  ' '.join(processed_tokens)
    else:
        processed_text = text
    
    # Remove extra punctuation 
    processed_text = re.sub(r'([.,!?;:])\1+', r'\1', processed_text)
    
    # Fix spacing around punctuation
    processed_text = re.sub(r'\s([.,!?;:])', r'\1', processed_text)
    
    # Clean up 
    processed_text = processed_text.strip()

    # Create POS distribution information
    # pos_counts = {}
    # for _, tag in pos_tags:
    #     pos_counts[tag] =  pos_counts.get(tag, 0) + 1
    
    return processed_text, entities


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
                doc.page_content, entities = preprocess_text(doc.page_content, True)

                # Store entities in metaadata for later use
                doc.metadata['entities'] = entities

                # Create an entity summary
                entity_summary = []
                for entity_type, entity_list in entities.items():
                    if entity_list:
                        entity_summary.append(f"{entity_type}: {', '.join(entity_list)}")
                
                if entity_summary:
                    doc.metadata['entity_summary'] = "; ".join(entity_summary)

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
                doc.page_content, entities = preprocess_text(doc.page_content, True)

                # Store entities in metaadata for later use
                doc.metadata['entities'] = entities

                # Create an entity summary
                entity_summary = []
                for entity_type, entity_list in entities.items():
                    if entity_list:
                        entity_summary.append(f"{entity_type}: {', '.join(entity_list)}")
                
                if entity_summary:
                    doc.metadata['entity_summary'] = "; ".join(entity_summary)

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
    embedding_model = OpenAIEmbeddings(
        model="text-embedding-3-large"  # Using OpenAI's most powerful embedding model
    )
    return embedding_model


def create_vector_store(chunks, embedding_model):
    vectorstore = FAISS.from_documents(documents=chunks, embedding=embedding_model)
    return vectorstore


def format_response(text):
    """
    Improve the formatting of the response text for better readability
    and ensure proper handling of Markdown formatting
    """
    if not text:
        return text

    # Process markdown headings (ensure they don't appear literally in the output)
    # Replace ### headings with proper HTML heading
    text = re.sub(r'(?m)^#+\s+(.+?)$', r'<h3>\1</h3>', text)
    
    # Convert sequential asterisks or dashes to proper bullet points
    text = re.sub(r'(?m)^(\s*[-*]\s+)', r'• ', text)
    
    # Convert bold markdown to HTML bold
    text = re.sub(r'\*\*(.+?)\*\*', r'<strong>\1</strong>', text)
    
    # Convert italic markdown to HTML italic
    text = re.sub(r'\*([^*]+?)\*', r'<em>\1</em>', text)
    
    # Convert numbered lists to consistent formatting
    text = re.sub(r'(?m)^(\s*\d+\.\s+)', r'\1', text)
    
    # Add line breaks between paragraphs if not already present
    text = re.sub(r'(?<!\n)\n(?!\n)', r'\n\n', text)
    
    # Handle section titles that might not be marked as headers
    text = re.sub(r'(?mi)^([A-Z][A-Za-z\s]+:)$', r'<strong>\1</strong>', text)
    
    # Clean up excessive newlines (no more than 2 consecutive ones)
    text = re.sub(r'\n{3,}', r'\n\n', text)
    
    # Clean up multiple spaces
    text = re.sub(r' {2,}', ' ', text)
    
    # Strip leading/trailing whitespace
    return text.strip()


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
            # Preprocess the user question for better matching
            processed_question, entities = preprocess_text(question, is_document=False)

            # Extract entity mentions for enhanced retrieval
            entity_mentions = []
            has_entities = False
            for entity_type, entity_list in entities.items():
                if entity_list:  # Check if the list is not empty
                    entity_mentions.extend(entity_list)
                    has_entities = True

            # Use a hybrid retrieval approach
            k_docs = 3  # Number of documents to retrieve
            
            if has_entities:
                # Entity-based retrieval - Use more specific search when entities are present
                entity_query = " ".join(entity_mentions)
                entity_docs = vectorstore.similarity_search(
                    entity_query,
                    k=k_docs
                )
                
                # Regular similarity search with the processed question
                similarity_docs = vectorstore.similarity_search(
                    processed_question,
                    k=k_docs
                )
                
                # Combine and deduplicate results (prioritizing entity matches)
                seen_docs = set()
                relevant_docs = []
                
                # First add entity-based results
                for doc in entity_docs:
                    doc_id = hash(doc.page_content)
                    if doc_id not in seen_docs:
                        seen_docs.add(doc_id)
                        # Add metadata to indicate this was from entity search
                        doc.metadata['retrieval_method'] = 'entity'
                        relevant_docs.append(doc)
                
                # Then add similarity-based results
                for doc in similarity_docs:
                    doc_id = hash(doc.page_content)
                    if doc_id not in seen_docs and len(relevant_docs) < k_docs:
                        seen_docs.add(doc_id)
                        # Add metadata to indicate this was from similarity search
                        doc.metadata['retrieval_method'] = 'similarity'
                        relevant_docs.append(doc)
                
                print(f"Retrieved {len(relevant_docs)} documents using hybrid entity + similarity search")
            else:
                # Fall back to regular similarity search when no entities are present
                relevant_docs = vectorstore.similarity_search(
                    processed_question,
                    k=k_docs
                )
                print(f"Retrieved {len(relevant_docs)} documents using similarity search only")
            
            if not relevant_docs:
                response_text = "I couldn't find any relevant information in the documents."
                conversation_history.append({"role": "user", "content": question})
                conversation_history.append({"role": "assistant", "content": response_text})
                return response_text
            
            # Combine contexts
            context = " ".join([doc.page_content for doc in relevant_docs])
            
            # Construct messages for the API call with improved formatting instructions
            messages = [
                {"role": "system", 
                 "content": """You are a helpful assistant that answers questions based ONLY on the provided context. 
                Use information ONLY from the context and remember previous parts of the conversation when answering.
                """}
            ]
            
            # Add conversation history (limited to last 10 exchanges to manage token limit)
            if conversation_history:
                messages.extend(conversation_history[-10:])
                
            # Add the current question with context
            messages.append({"role": "user", "content": f"Context: {context}\n\nQuestion: {question}\n\nAnswer:"})

            memory = ConversationBufferMemory(memory_key='chat_history', return_messages=True)
            # Use OpenAI API for question answering
            response = client.chat.completions.create(
                model="gpt-4o-mini",  # Best option for context adherence
                messages=messages,
                max_tokens=800,
                temperature=0.7
            )
            
            answer = response.choices[0].message.content.strip()
            
            # If answer is too short, return relevant context
            if len(answer) < 3:
                answer = relevant_docs[0].page_content[:200] + "..."
            
            # Apply formatting enhancement
            formatted_answer = format_response(answer)
            
            # Update conversation history with the original answer (not formatted)
            # to avoid compounding formatting in future responses
            conversation_history.append({"role": "user", "content": question})
            conversation_history.append({"role": "assistant", "content": answer})
                
            return formatted_answer
            
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
        embedding_model = generate_embeddings(chunks)
        vectorstore = create_vector_store(chunks, embedding_model)
        rag_pipeline = build_rag_pipeline(vectorstore)
        test_rag_pipeline(rag_pipeline)
    except Exception as e:
        print(f"Error in RAG pipeline execution: {e}")
