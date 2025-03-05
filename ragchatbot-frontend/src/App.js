import React, { Component } from "react";
import ChatHistory from "./ChatHistory";
import FAQSection from "./FAQSection";
import "./styles.css";
import { Button, Switch, FormControlLabel, TextField } from "@mui/material";
import PowerIcon from "@mui/icons-material/Power";
import { motion } from "framer-motion";
import { FontAwesomeIcon } from "@fortawesome/react-fontawesome";
import { faArrowUp, faPlus, faSun, faMoon } from "@fortawesome/free-solid-svg-icons";
import AttachFileIcon from "@mui/icons-material/AttachFile";

class App extends Component {
  constructor(props) {
    super(props);
    // Load saved state from localStorage or use default state
    const savedState = JSON.parse(localStorage.getItem('chatbotState')) || {
      conversations: [],
      activeConversation: null,
      input: "",
      darkMode: false,
      attachedFiles: [],
      maxFiles: 4,
      isLoading: false,
      bookmarkedMessages: [],
      reactions: {}
    };

    this.state = savedState;
  }

  // Add componentDidUpdate to save state changes
  componentDidUpdate(prevProps, prevState) {
    // Only save specific state properties we want to persist
    const stateToSave = {
      conversations: this.state.conversations,
      activeConversation: this.state.activeConversation,
      darkMode: this.state.darkMode,
      maxFiles: this.state.maxFiles,
      bookmarkedMessages: this.state.bookmarkedMessages,
      reactions: this.state.reactions
    };
    localStorage.setItem('chatbotState', JSON.stringify(stateToSave));
  }

  // Add this helper function to generate a title from conversation
  generateConversationTitle = (messages) => {
    if (!messages || messages.length < 2) return "New Chat";
    
    // Get the first user message and bot response
    const userMessage = messages[0].text || "";
    const botResponse = messages[1].text || "";
    
    // Combine both messages and create a title
    const combinedText = userMessage + " " + botResponse;
    
    // Create title: Take first 10 chars of meaningful words
    const title = combinedText
      .split(/\s+/)
      .filter(word => word.length > 3)  // Filter out small words
      .slice(0, 2)  // Take first two meaningful words
      .join(" ")
      .substring(0, 30);  // Limit to 10 characters
      
    return title || "New Chat";
  };

  addMessage = (sender, text, files = []) => {
    const message = { sender, text, files };
    
    this.setState(prevState => {
      if (prevState.activeConversation === null) {
        // Create new conversation
        const newConversation = {
          messages: [message],
          name: "New Chat"  // Temporary name
        };
        
        const updatedConversations = [...prevState.conversations, newConversation];
        const newIndex = updatedConversations.length - 1;
        
        // Update the title after bot responds
        if (sender === "bot" && updatedConversations[newIndex].messages.length >= 2) {
          updatedConversations[newIndex].name = this.generateConversationTitle(
            updatedConversations[newIndex].messages
          );
        }
        
        return {
          conversations: updatedConversations,
          activeConversation: newIndex
        };
      } else {
        // Add to existing conversation
        const updatedConversations = [...prevState.conversations];
        updatedConversations[prevState.activeConversation].messages.push(message);
        
        // Update title if this is the bot's first response
        if (sender === "bot" && updatedConversations[prevState.activeConversation].messages.length === 2) {
          updatedConversations[prevState.activeConversation].name = 
            this.generateConversationTitle(updatedConversations[prevState.activeConversation].messages);
        }
        
        return { conversations: updatedConversations };
      }
    });
  };

  handleSend = async () => {
    const { input, attachedFiles } = this.state;
    
    // Check if we have either input or files
    if (!input.trim() && attachedFiles.length === 0) return;

    try {
      // Add message to chat immediately
      const displayMessage = input.trim() || `Uploaded ${attachedFiles.length} file(s)`;
      this.addMessage("user", displayMessage, attachedFiles);
      this.setState({ input: "", isLoading: true });

      // Create FormData
      const formData = new FormData();
      formData.append('message', input.trim());  // Send empty string if no input
      
      // Append each file with unique field name
      attachedFiles.forEach((file, index) => {
        // Debug log
        console.log(`Attaching file ${index}:`, file.name, file.type);
        formData.append(`file${index}`, file, file.name);
      });

      // Log FormData contents for debugging
      for (let pair of formData.entries()) {
        console.log('FormData contains:', pair[0], pair[1]);
      }

      const response = await fetch('http://localhost:5000/api/chat', {
        method: 'POST',
        body: formData
      });

      if (!response.ok) {
        const errorData = await response.json();
        throw new Error(errorData.error || `HTTP error! status: ${response.status}`);
      }

      const data = await response.json();
      this.addMessage("bot", data.response);
      
      // Clear attached files after successful send
      this.setState({ attachedFiles: [] });
    } catch (error) {
      console.error("Error sending message:", error);
      this.addMessage("bot", `Error: ${error.message}`);
    } finally {
      this.setState({ isLoading: false });
    }
  };

  handleInputChange = (event) => {
    this.setState({ input: event.target.value });
  };

  handleKeyPress = (event) => {
    if (event.key === "Enter") {
      this.handleSend();
    }
  };

  handleFileUpload = (event) => {
    const files = Array.from(event.target.files);
    console.log('Files selected:', files.map(f => f.name));  // Debug log
    
    if (this.state.attachedFiles.length + files.length > this.state.maxFiles) {
      alert(`Maximum ${this.state.maxFiles} files allowed`);
      return;
    }
    
    this.setState(prevState => ({
      attachedFiles: [...prevState.attachedFiles, ...files]
    }));
  };

  startNewConversation = () => {
    this.setState({ activeConversation: null, input: "", attachedFiles: [] });
  };

  switchConversation = (index) => {
    this.setState({ activeConversation: index });
  };

  toggleDarkMode = () => {
    this.setState((prevState) => ({ darkMode: !prevState.darkMode }));
  };

  // Add a method to clear saved state
  clearSavedState = () => {
    localStorage.removeItem('chatbotState');
    window.location.reload();
  };

  handleReaction = (messageId, reaction) => {
    this.setState(prevState => ({
      reactions: {
        ...prevState.reactions,
        [messageId]: reaction
      }
    }));
  };

  toggleBookmark = (messageId) => {
    this.setState(prevState => ({
      bookmarkedMessages: prevState.bookmarkedMessages.includes(messageId)
        ? prevState.bookmarkedMessages.filter(id => id !== messageId)
        : [...prevState.bookmarkedMessages, messageId]
    }));
  };

  render() {
    const { conversations = [], activeConversation, input = "", darkMode = false, attachedFiles = [] } = this.state;
    const currentMessages = activeConversation !== null && conversations[activeConversation] 
      ? conversations[activeConversation].messages 
      : [];

    return (
      <div className={`app-container ${darkMode ? "dark-mode" : "light-mode"}`}>
        <div className="absolute top-4 right-4 flex items-center gap-2">
          <FontAwesomeIcon icon={faSun} className="text-gray-400 text-lg" />
          <Switch checked={darkMode} onChange={this.toggleDarkMode} />
          <FontAwesomeIcon icon={faMoon} className="text-gray-400 text-lg" />
          <button
            onClick={this.clearSavedState}
            className="ml-4 px-3 py-1 rounded-md bg-red-500 text-white text-sm hover:bg-red-600 transition-colors"
          >
            Clear History
          </button>
        </div>
        <div className={`chat-layout ${this.state.isOpen ? "sidebar-expanded" : ""}`} >
          <ChatHistory 
            conversations={conversations} 
            switchConversation={this.switchConversation} 
            startNewConversation={this.startNewConversation} 
            selectedConversation={activeConversation} 
            toggleSidebar={(isOpen) => this.setState({ isOpen })} 
          />

          <motion.div className={"chat-container"}>
            <div className="chat-header flex items-center gap-2 p-4">
              <PowerIcon className="text-[var(--text-color)]" fontSize="large" />
              <h1 className="text-4xl font-bold text-[var(--text-color)]">PowerWise - A Power Quality ChatBot</h1>
            </div>

            <div className="chat-window p-4 mb-4 mx-10 bg-white dark:bg-gray-800 rounded-lg shadow-lg overflow-y-auto">
              {currentMessages.map((msg, index) => (
                <motion.div
                  key={index}
                  className={`message flex ${msg.sender === "user" ? "justify-end" : "justify-start"} mb-6`}
                  initial={{ opacity: 0, x: msg.sender === "user" ? 50 : -50 }}
                  animate={{ opacity: 1, x: 0 }}
                  transition={{ duration: 0.3 }}
                >
                  <div className={`max-w-[70%] p-3 rounded-lg ${
                    msg.sender === "user" 
                      ? "bg-purple-600 text-white ml-auto" 
                      : "bg-gray-200 dark:bg-gray-700 text-gray-900 dark:text-gray-100 mr-auto"
                  }`}>
                    {msg.text}
                    {msg.files && msg.files.length > 0 && (
                      <div className="flex flex-col gap-2 mt-2 pt-2 border-t border-white/20">
                        {msg.files.map((file, index) => (
                          <div key={index} className="flex items-center gap-2">
                            <div className="w-6 h-6 bg-purple-500 rounded-lg flex items-center justify-center">
                              <AttachFileIcon className="text-white" fontSize="small" />
                            </div>
                            <span className="text-sm">{file.name}</span>
                          </div>
                        ))}
                      </div>
                    )}
                  </div>
                </motion.div>
              ))}
              {this.state.isLoading && (
                <motion.div 
                  className="flex justify-start mt-6"
                  initial={{ opacity: 0 }}
                  animate={{ opacity: 1 }}
                >
                  <div className="bg-gray-200 dark:bg-gray-700 p-3 rounded-lg">
                    <div className="flex items-center space-x-2">
                      <div className="w-2 h-2 bg-gray-500 rounded-full animate-bounce" />
                      <div className="w-2 h-2 bg-gray-500 rounded-full animate-bounce" style={{ animationDelay: "0.2s" }} />
                      <div className="w-2 h-2 bg-gray-500 rounded-full animate-bounce" style={{ animationDelay: "0.4s" }} />
                    </div>
                  </div>
                </motion.div>
              )}
            </div>

            <div className="input-area relative flex flex-col p-4 rounded-lg shadow-lg w-[95%] bg-[var(--chat-bg)] text-[var(--text-color)] mb-8 mx-auto">
              {/* Show attached files above input if present */}
              {attachedFiles.length > 0 && (
                <div className="flex flex-wrap gap-2 px-2 py-2 mb-2">
                  {attachedFiles.map((file, index) => (
                    <div key={index} className={`flex items-center gap-2 ${
                      darkMode ? 'bg-gray-700' : 'bg-gray-200'
                    } rounded-lg px-3 py-2`}>
                      <div className="w-6 h-6 bg-purple-500 rounded-lg flex items-center justify-center">
                        <AttachFileIcon className="text-white" fontSize="small" />
                      </div>
                      <span className="text-sm truncate max-w-[150px] text-[var(--text-color)]">{file.name}</span>
                      <button 
                        onClick={() => {
                          const newFiles = [...attachedFiles];
                          newFiles.splice(index, 1);
                          this.setState({ attachedFiles: newFiles });
                        }}
                        className={`${
                          darkMode ? 'text-gray-300 hover:text-white' : 'text-gray-500 hover:text-gray-700'
                        } ml-2`}
                      >
                        <svg xmlns="http://www.w3.org/2000/svg" className="h-4 w-4" viewBox="0 0 20 20" fill="currentColor">
                          <path fillRule="evenodd" d="M4.293 4.293a1 1 0 011.414 0L10 8.586l4.293-4.293a1 1 0 111.414 1.414L11.414 10l4.293 4.293a1 1 0 01-1.414 1.414L10 11.414l-4.293 4.293a1 1 0 01-1.414-1.414L8.586 10 4.293 5.707a1 1 0 010-1.414z" clipRule="evenodd" />
                        </svg>
                      </button>
                    </div>
                  ))}
                </div>
              )}
              
              {/* Input area and buttons */}
              <div className="flex items-center gap-2">
                <div className="flex-grow px-2 w-[90%]">
                  <TextField
                    multiline
                    minRows={1}
                    maxRows={5}
                    fullWidth
                    placeholder="Type your query..."
                    value={input}
                    onChange={this.handleInputChange}
                    onKeyPress={this.handleKeyPress}
                    className="chat-input bg-transparent border-none focus:ring-0 focus:outline-none w-full text-[var(--text-color)]"
                    InputProps={{
                      disableUnderline: true,
                      style: { 
                        color: 'var(--text-color)',
                        padding: '12px 16px',
                        fontSize: '1rem',
                        lineHeight: '1.75',
                        minHeight: '48px',
                        width: '100%',
                      },
                      classes: {
                        input: darkMode ? 'text-white placeholder-gray-400' : 'text-black placeholder-gray-600'
                      }
                    }}
                    sx={{
                      width: '100%',
                      '& .MuiInputBase-root': {
                        padding: '8px 12px',
                        alignItems: 'center',
                        width: '100%',
                      },
                      '& .MuiInputBase-input': {
                        color: 'var(--text-color)',
                        padding: '4px 8px',
                      },
                      '& .MuiInputBase-input::placeholder': {
                        color: darkMode ? 'rgba(255, 255, 255, 0.5)' : 'rgba(0, 0, 0, 0.5)',
                        opacity: 1,
                      },
                    }}
                  />
                </div>
                <div className="flex items-center gap-2">
                  {/* File Upload Button */}
                  <div className="relative group">
                    <label className={`cursor-pointer flex items-center justify-center w-12 h-12 rounded-full transition ${
                      attachedFiles.length >= this.state.maxFiles ? 'bg-gray-400' : 'bg-[var(--btn-bg)]'
                    } hover:opacity-80`}>
                      <input 
                        type="file" 
                        onChange={this.handleFileUpload} 
                        className="hidden" 
                        accept=".pdf,.doc,.docx,.txt"
                        multiple
                        disabled={attachedFiles.length >= this.state.maxFiles}
                      />
                      <FontAwesomeIcon icon={faPlus} className="text-[var(--btn-text)] text-xl" />
                    </label>
                    <span className="absolute -top-14 left-1/2 transform -translate-x-1/2 scale-0 group-hover:scale-100 transition bg-[var(--chat-bg)] text-[var(--text-color)] text-sm font-semibold px-2 py-1 rounded-md shadow-md border border-[var(--text-color)]">
                      {attachedFiles.length >= this.state.maxFiles ? 'Max files reached' : 'Attach File'}
                    </span>
                  </div>

                  {/* Send Button */}
                  <button
                    onClick={this.handleSend}
                    className="flex items-center justify-center w-12 h-12 rounded-full transition bg-[var(--btn-bg)] hover:opacity-80"
                  >
                    <FontAwesomeIcon icon={faArrowUp} className="text-[var(--btn-text)]" />
                  </button>
                </div>
              </div>
            </div>
          </motion.div>

          <FAQSection />
        </div>
      </div>
    );
  }
}

export default App;
