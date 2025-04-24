from langchain_community.document_loaders import PyPDFLoader
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_community.vectorstores import FAISS
from langchain_community.chat_message_histories import ChatMessageHistory
from langchain_openai import OpenAIEmbeddings
from langchain.chains import create_history_aware_retriever, create_retrieval_chain
from langchain.chains.combine_documents import create_stuff_documents_chain
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_openai import ChatOpenAI
from langchain_core.runnables import RunnableWithMessageHistory
import os
import glob
import markdown
from markdown.extensions.extra import ExtraExtension
import re
from nltk import pos_tag, ne_chunk
from nltk.corpus import stopwords
from nltk.tokenize import word_tokenize
from nltk.stem import WordNetLemmatizer
from langchain_core.messages import BaseMessage

contextualize_q_system_prompt = """
            Given a chat history and the latest user question which might reference context in the chat history,
            formulate a standalone question which can be understood without the chat history. Do NOT answer the 
            question, just reforumlate it if needed and otherwise return as is."""

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
    Enhanced text preprocessing using NLTK.

    Args:
        text (str): The text to preprocess
        is_document (bool): Apply more extensive cleaning for documents
        
    Returns:
        tuple: (processed_text, entities_dict)
    """
    if not text or not isinstance(text, str):
        return text, {}
    
    text = text.lower().strip()
    text = re.sub(r'\s+', ' ', text) # Remove extra whitespace
    text = re.sub(r'http[s]?://\S+', '', text) # Remove URLs
    text = re.sub(r'\S+@\S+', '', text) # Remove email addresses
    text = re.sub(r'[^\w\s.,?!;:()\-\'"]', ' ', text) # Remove special chars
    text = re.sub(r'<[^>]+>', ' ', text) # Remove HTML
    
    tokens = word_tokenize(text)
    pos_tags = pos_tag(tokens)
    ne_chunked = ne_chunk(pos_tags)

    # Extract entities
    entities = {
        'PERSON': [], 'ORGANIZATION': [], 'LOCATION': [], 
        'DATE': [], 'TIME': [], 'MONEY': [], 'PERCENT': [], 
        'FACILITY': [], 'GPE': []
    }
    for chunk in ne_chunked:
        if hasattr(chunk, 'label'):
            entity_type = chunk.label()
            entity_text = ' '.join(c[0] for c in chunk)
            if entity_type in entities:
                entities[entity_type].append(entity_text)

    # More extensive preprocessing for documents
    if is_document:
        stop_words = set(stopwords.words('english'))
        filtered_tokens = [(word, tag) for word, tag in pos_tags if word.lower() not in stop_words]
        lemmatizer = WordNetLemmatizer()
        processed_tokens = [lemmatizer.lemmatize(word, get_wordnet_pos(tag)) for word, tag in filtered_tokens]
        processed_text = ' '.join(processed_tokens)
    else:
        processed_text = text
    
    # Clean up punctuation and spacing
    processed_text = re.sub(r'([.,!?;:])\1+', r'\1', processed_text)
    processed_text = re.sub(r'\s([.,!?;:])', r'\1', processed_text)
    processed_text = processed_text.strip()
    
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
            for doc in docs:
                doc.metadata['source'] = 'database'
                doc.metadata['is_recent'] = False
                doc.page_content, entities = preprocess_text(doc.page_content, True)
                doc.metadata['entities'] = entities
                # Optionally create entity summary if needed later
                # entity_summary = [f"{etype}: {', '.join(elist)}" for etype, elist in entities.items() if elist]
                # if entity_summary: doc.metadata['entity_summary'] = "; ".join(entity_summary)
            documents.extend(docs)
        except Exception as e:
            print(f"Warning: Error loading database file {os.path.basename(file_path)}: {e}")

    # Load from Uploaded Documents
    uploaded_files = glob.glob(os.path.join(uploaded_dir, '*.pdf'))
    for file_path in uploaded_files:
        try:
            loader = PyPDFLoader(file_path)
            docs = loader.load()
            filename = os.path.basename(file_path)
            for doc in docs:
                doc.metadata['source'] = 'uploaded'
                doc.metadata['is_recent'] = recent_files and filename in recent_files
                doc.page_content, entities = preprocess_text(doc.page_content, True)
                doc.metadata['entities'] = entities
                # Optionally create entity summary
            documents.extend(docs)
        except Exception as e:
            print(f"Warning: Error loading uploaded file {os.path.basename(file_path)}: {e}")
    
    if not documents:
        print("Warning: No documents loaded.")
        return [] # Return empty list if no documents found

    # Split into chunks
    text_splitter = RecursiveCharacterTextSplitter(
        chunk_size=1000,
        chunk_overlap=200,
        separators=["\n\n", "\n", ".", "!", "?", ",", " ", ""]
    )
    chunks = text_splitter.split_documents(documents)
    print(f"Created {len(chunks)} chunks from {len(database_files) + len(uploaded_files)} documents.")
    return chunks

def load_single_document(file_path):
    """Load and process a single document file."""
    try:
        loader = PyPDFLoader(file_path)
        docs = loader.load()
        filename = os.path.basename(file_path) # Get the base filename
        for doc in docs:
            doc.metadata['source'] = 'uploaded'
            doc.metadata['is_recent'] = True
            doc.metadata['filename'] = filename # Add filename to metadata
            doc.page_content, entities = preprocess_text(doc.page_content, True)
            doc.metadata['entities'] = entities
            # Optionally create entity summary

        text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=1000,
            chunk_overlap=200,
            separators=["\n\n", "\n", ".", "!", "?", ",", " ", ""]
        )
        chunks = text_splitter.split_documents(docs)
        print(f"Created {len(chunks)} chunks from new document: {filename}")
        return chunks

    except Exception as e:
        print(f"Error loading single file {os.path.basename(file_path)}: {e}")
        return []

def update_vector_store(vector_store, new_chunks, embedding_model):
    """Update the vector store with new document chunks."""
    if not new_chunks:
        print("No new chunks to add.")
        return vector_store

    try:
        # Assuming vector_store is Chroma or compatible with add_documents
        vector_store.add_documents(new_chunks)
        print(f"Successfully added {len(new_chunks)} new chunks to the vector store.")
        return vector_store
    except Exception as e:
        print(f"Error updating vector store: {e}")
        # Depending on the error, you might want to raise it or handle it differently
        return vector_store # Return original store on error

def generate_embeddings(chunks):
    # Using OpenAI's recommended embedding model
    embedding_model = OpenAIEmbeddings(model="text-embedding-3-large")
    return embedding_model

def create_vector_store(chunks, embedding_model):
    if not chunks:
        print("Warning: No chunks provided to create vector store.")
        # Depending on requirements, might return None or raise error
        # For now, let's return None and handle it upstream
        return None 
    vectorstore = FAISS.from_documents(documents=chunks, embedding=embedding_model)
    return vectorstore

def format_response(text):
    """Convert Markdown to HTML and clean up formatting issues."""
    if not text:
        return text

    # Convert Markdown to HTML using 'extra' extension for features like tables, fenced code blocks
    html = markdown.markdown(text, extensions=[ExtraExtension()])

    # Add class to list items that start with <strong> for styling as titles
    # Use a non-greedy match for attributes .*?
    html = re.sub(r'<li(.*?)>\s*<strong', r'<li class="list-title-item"\1><strong', html, flags=re.IGNORECASE)

    # Clean up common formatting issues from Markdown conversion
    # Remove empty <p> tags, especially those following <strong> inside <li>
    html = re.sub(r'(<strong.*?>.*?</strong>)\s*<p>\s*</p>', r'\1', html, flags=re.IGNORECASE | re.DOTALL)
    # General empty paragraph removal (handle potential attributes)
    html = re.sub(r'<p(\s+[^>]*)?>\s*</p>', '', html, flags=re.IGNORECASE)

    html = re.sub(r'<p>(.*?)</p>\s*<(ul|ol)', r'<p>\1</p><\2', html, flags=re.IGNORECASE | re.DOTALL) # Fix paragraph before list spacing
    html = re.sub(r'</li>\s*<li>', r'</li><li>', html) # Fix list item spacing
    # Make the rule removing <p> inside <li> more robust and handle potential attributes
    html = re.sub(r'<li>\s*<p(\s+[^>]*)?>(.*?)</p>\s*</li>', r'<li>\2</li>', html, flags=re.IGNORECASE | re.DOTALL) # Remove paragraph tags inside list items
    html = re.sub(r'</([uo]l)>\s*<p>', r'</\1><p>', html, flags=re.IGNORECASE | re.DOTALL) # Fix spacing after lists
    html = re.sub(r'<p><p>(.*?)</p></p>', r'<p>\1</p>', html, flags=re.IGNORECASE | re.DOTALL) # Fix double paragraph wrapping
    html = re.sub(r'</p>\s+<p>', r'</p><p>', html, flags=re.IGNORECASE) # Remove extra whitespace between paragraphs
    html = re.sub(r'(<br\s*/?>\s*){2,}', r'<br/>', html, flags=re.IGNORECASE) # Consolidate multiple breaks
    html = re.sub(r'<p>\s*<br\s*/?>', r'<p>', html, flags=re.IGNORECASE) # Remove leading breaks in paragraphs
    html = re.sub(r'<br\s*/?>\s*</p>', r'</p>', html, flags=re.IGNORECASE) # Remove trailing breaks in paragraphs

    # Attempt to remove paragraph tags wrapping list items if markdown creates <li><p>...</p></li>
    # This rule was duplicated, removing the second instance.
    # html = re.sub(r'<li>\s*<p(\s+[^>]*)?>(.*?)</p>\s*</li>', r'<li>\2</li>', html, flags=re.IGNORECASE | re.DOTALL)

    # Remove any trailing <br> tags at the very end of the response
    html = re.sub(r'(<br\s*/?>\s*)+$', '', html, flags=re.IGNORECASE)

    return html.strip()

class WindowedChatMessageHistory(ChatMessageHistory):
    """Chat message history that maintains only a window of the most recent messages."""
    
    def __init__(self, window_size=10):
        """Initialize with a window size.
        Args:
            window_size (int): Maximum number of messages (human + AI) to retain.
        """
        super().__init__()
        self._window_size = window_size 
        
    @property
    def window_size(self):
        return self._window_size
        
    @window_size.setter
    def window_size(self, value):
        self._window_size = value
        
    def add_message(self, message: BaseMessage) -> None:
        """Add a message, trimming history if it exceeds the window size."""
        super().add_message(message)
        if len(self.messages) > self._window_size:
            self.messages = self.messages[-self._window_size:]

def build_rag_pipeline(vectorstore, llm_model_name="gpt-4o-mini", history_window_size=12):
    """Builds the complete RAG pipeline with history."""
    
    if vectorstore is None:
        print("Error: Cannot build RAG pipeline without a valid vectorstore.")
        return None # Cannot proceed without a vectorstore

    llm = ChatOpenAI(
        model=llm_model_name, 
        temperature=0.3,
        max_tokens=750
    )
    
    contextualize_q_prompt = ChatPromptTemplate.from_messages([
        ("system", contextualize_q_system_prompt),
        MessagesPlaceholder("chat_history"),
        ("human", "{input}"),
    ])

    history_aware_retriever = create_history_aware_retriever(
        llm, 
        vectorstore.as_retriever(),
        contextualize_q_prompt,
    )

    qa_system_prompt = """You are a helpful assistant providing information based ONLY on the retrieved context.
    Use ONLY the provided context to answer. If the context doesn't contain the answer, state that you don't have enough information.
    Keep answers concise and relevant.

    Context: {context}"""

    qa_prompt = ChatPromptTemplate.from_messages([
        ("system", qa_system_prompt),
        MessagesPlaceholder("chat_history"),
        ("human", "{input}"),
    ])

    question_answer_chain = create_stuff_documents_chain(llm, qa_prompt)
    rag_chain = create_retrieval_chain(history_aware_retriever, question_answer_chain)
    
    # Setup conversation history store
    store = {}
    def get_session_history(session_id):
        if session_id not in store:
            store[session_id] = WindowedChatMessageHistory(window_size=history_window_size)
        return store[session_id]
    
    # Create the stateful chain
    conversational_rag_chain = RunnableWithMessageHistory(
        rag_chain,
        get_session_history,
        input_messages_key="input",
        history_messages_key="chat_history",
        output_messages_key="answer",
    )

    # Wrapper function for the API
    def qa_function(question, reset_conversation=False, session_id="default"):
        if reset_conversation:
            if session_id in store:
                store[session_id].clear()
            return "Conversation history has been reset."
        
        response = conversational_rag_chain.invoke(
            {"input": question},
            config={"configurable": {"session_id": session_id}}
        )
        
        return response["answer"]

    return qa_function


# Main execution block (optional, for testing or standalone runs)
if __name__ == "__main__":
    try:
        print("Initializing RAG pipeline components...")
        chunks = load_and_chunk_documents()
        if chunks:
            embedding_model = generate_embeddings(chunks)
            vectorstore = create_vector_store(chunks, embedding_model)
            if vectorstore:
                rag_pipeline = build_rag_pipeline(vectorstore)
                if rag_pipeline:
                    print("RAG Pipeline built successfully. Ready for testing or API.")
                    # Example test query (optional)
                    # test_question = "What are incipient cable faults?"
                    # print(f"\nTesting with: '{test_question}'")
                    # response = rag_pipeline(test_question)
                    # print(f"Response: {response}")
                else:
                    print("Failed to build RAG pipeline.")
            else:
                print("Failed to create vector store.")
        else:
            print("No document chunks loaded, cannot build pipeline.")
            
    except Exception as e:
        print(f"Error during initial setup: {e}")
