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
import openai
import markdown
from markdown.extensions.extra import ExtraExtension
import re
from nltk import pos_tag, ne_chunk
from nltk.corpus import stopwords
from nltk.tokenize import word_tokenize
from nltk.stem import WordNetLemmatizer

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

    # Convert Markdown to HTML
    html = markdown.markdown(text, extensions=[ExtraExtension()])
    
    # Clean up issues with paragraph spacing and lists
    
    # Fix paragraph tags immediately before lists that cause extra spacing
    html = re.sub(r'<p>(.*?)</p>\s*<(ul|ol)', r'<p>\1</p><\2', html)
    
    # Remove empty paragraphs that might add extra spacing
    html = re.sub(r'<p>\s*</p>', '', html)
    
    # Fix spacing between list items by removing any extra line breaks or spaces
    html = re.sub(r'</li>\s*<li>', r'</li><li>', html)
    
    # Remove paragraph tags inside list items which cause extra spacing
    html = re.sub(r'<li><p>(.*?)</p></li>', r'<li>\1</li>', html)
    
    # Remove extra spacing after lists
    html = re.sub(r'</([uo]l)>\s*<p>', r'</\1><p>', html)
    
    # Fix double paragraph wrapping
    html = re.sub(r'<p><p>(.*?)</p></p>', r'<p>\1</p>', html)
    
    # Remove extra whitespace between paragraphs
    html = re.sub(r'</p>\s+<p>', r'</p><p>', html)
    
    # Fix excessive line breaks that might appear in the HTML
    html = re.sub(r'<br\s*/?>\s*<br\s*/?>', r'<br/>', html)
    
    # Remove any leading/trailing <br> tags inside paragraphs
    html = re.sub(r'<p>\s*<br\s*/?>|<br\s*/?>\s*</p>', r'<p>', html)
    
    return html


def build_rag_pipeline(vectorstore, llm="gpt-4o-mini", existing_history=None):
    # Initialize llm
    llm = ChatOpenAI(
        model=llm, 
        temperature=0.3
    )
    
    contextualize_q_prompt = ChatPromptTemplate.from_messages([
        ("system", contextualize_q_system_prompt),
        MessagesPlaceholder("chat_history"),
        ("human", "{input}"),
    ])

    # Create a retriever with history awareness
    history_aware_retriever = create_history_aware_retriever(
        llm, 
        vectorstore.as_retriever(),
        contextualize_q_prompt,
    )

    # Create the question-answering chain
    qa_system_prompt = """You are a helpful assistant that provides information based ONLY on the documents in your knowledge base.
    Use ONLY the following pieces of retrieved context to answer the question and only include outside information if it is explicitly mentioned in the context
    and relevant to the question and document content.
    If you don't know the answer or if the context doesn't contain relevant information, say you don't have enough information to answer.
    Remain conversational and engaging in your responses while keeping the answers concise and relevant.

    Context: {context}"""

    qa_prompt = ChatPromptTemplate.from_messages([
        ("system", qa_system_prompt),
        MessagesPlaceholder("chat_history"),
        ("human", "{input}"),
    ])

    # Create the document chain
    question_answer_chain = create_stuff_documents_chain(llm, qa_prompt)
    
    # Create the retrieval chain
    rag_chain = create_retrieval_chain(history_aware_retriever, question_answer_chain)
    
    # Set up conversation history storage
    store = {}

    def get_session_history(session_id):
        if session_id not in store:
            store[session_id] = ChatMessageHistory()
        return store[session_id]
    
    # Create a stateful conversational chain
    conversational_rag_chain = RunnableWithMessageHistory(
        rag_chain,
        get_session_history,
        input_messages_key="input",
        history_messages_key="chat_history",
        output_messages_key="answer",
    )

    # Create a wrapper function to match your existing interface
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

def test_rag_pipeline(rag_pipeline):
    # Test with conversational queries that build upon each other
    conversation = [
        "Who is the 45th president of the USA?",
        "When did he take office?",
        "What were some major policies during his term?",
        "What year was the Shinkansen name first used?",
        "How fast can these trains go?",
    ]
    
    print("Testing conversational capabilities:")
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
