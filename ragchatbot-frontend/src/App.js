import React, { Component } from "react";
import ChatHistory from "./ChatHistory";
import FAQSection from "./FAQSection";
import "./styles.css";
import { Button, Switch, FormControlLabel, TextField } from "@mui/material";
import PowerIcon from "@mui/icons-material/Power";
import { motion } from "framer-motion";
import { FontAwesomeIcon } from "@fortawesome/react-fontawesome";
import { faArrowUp, faPlus, faSun, faMoon } from "@fortawesome/free-solid-svg-icons";

class App extends Component {
  constructor(props) {
    super(props);
    this.state = {
      conversations: [],
      activeConversation: null,
      input: "",
      darkMode: false,
      attachedFile: null,
    };
  }

  handleSend = async () => {
    const { input, activeConversation, conversations, attachedFile } = this.state;
    if (input.trim() === "" && !attachedFile) return;

    let newConversations = [...conversations];
    const userMessage = { text: input, sender: "user", file: attachedFile };

    try {
        // Add user message immediately
        if (activeConversation === null) {
            const newConversation = {
                id: newConversations.length,
                name: input || "New Query",
                messages: [userMessage],
            };
            newConversations.push(newConversation);
            this.setState({ 
                conversations: newConversations, 
                activeConversation: newConversation.id, 
                input: "" 
            });
        } else {
            newConversations[activeConversation].messages.push(userMessage);
            this.setState({ conversations: newConversations, input: "" });
        }

        // Log the request for debugging
        console.log('Sending request:', input);
        
        const response = await fetch('/api/chat', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({ message: input }),
        });

        const data = await response.json();
        console.log('Received response:', data); // Add this line for debugging
        
        // Add bot response
        const botMessage = { 
            text: data.response || "No response from server", 
            sender: "bot" 
        };
        if (activeConversation === null) {
            newConversations[newConversations.length - 1].messages.push(botMessage);
        } else {
            newConversations[activeConversation].messages.push(botMessage);
        }
        
        this.setState({ 
            conversations: newConversations,
            attachedFile: null
        });
    } catch (error) {
        console.error('Error:', error);
        const errorMessage = { 
            text: "Sorry, there was an error processing your request.", 
            sender: "bot" 
        };
        if (activeConversation === null) {
            newConversations[newConversations.length - 1].messages.push(errorMessage);
        } else {
            newConversations[activeConversation].messages.push(errorMessage);
        }
        this.setState({ 
            conversations: newConversations,
            attachedFile: null
        });
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

  handleFileChange = (event) => {
    this.setState({ attachedFile: event.target.files[0] });
  };

  startNewConversation = () => {
    this.setState({ activeConversation: null, input: "", attachedFile: null });
  };

  switchConversation = (index) => {
    this.setState({ activeConversation: index });
  };

  toggleDarkMode = () => {
    this.setState((prevState) => ({ darkMode: !prevState.darkMode }));
  };

  render() {
    const { conversations, activeConversation, input, darkMode, attachedFile } = this.state;
    const currentMessages = activeConversation !== null ? conversations[activeConversation].messages : [];

    return (
      <div className={`app-container ${darkMode ? "dark-mode" : "light-mode"}`}>
        
        <div className="absolute top-4 right-4 flex items-center gap-2">
  <FontAwesomeIcon icon={faSun} className="text-gray-400 text-lg" />
  <Switch checked={darkMode} onChange={this.toggleDarkMode} />
  <FontAwesomeIcon icon={faMoon} className="text-gray-400 text-lg" />
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
      className={`message ${msg.sender === "user" ? "user-msg" : "bot-msg"}`}
      initial={{ opacity: 0, x: msg.sender === "user" ? 50 : -50 }}
      animate={{ opacity: 1, x: 0 }}
      transition={{ duration: 0.3 }}
    >
      {msg.text}
    </motion.div>
  ))}
</div>



<div className="input-area relative flex items-center p-3 rounded-full shadow-lg w-full bg-[var(--chat-bg)] text-[var(--text-color)]">
  <div className="flex-grow px-4">
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
      }}
    />
  </div>
  <div className="flex items-center gap-2 pr-2">
    {/* File Upload Button with Tooltip */}
    <div className="relative group">
      <label className="cursor-pointer flex items-center justify-center w-12 h-12 rounded-full transition bg-[var(--btn-bg)] hover:opacity-80">
        <input type="file" onChange={this.handleFileChange} className="hidden" />
        <FontAwesomeIcon icon={faPlus} className="text-[var(--btn-text)] text-xl" />
      </label>
      <span className="absolute -top-14 left-1/2 transform -translate-x-1/2 scale-0 group-hover:scale-100 transition bg-[var(--chat-bg)] text-[var(--text-color)] text-sm font-semibold px-2 py-1 rounded-md shadow-md border border-[var(--text-color)]">
        Attach File
      </span>
    </div>

    {/* Send Button with Tooltip */}
    <div className="relative group">
      <button
        onClick={this.handleSend}
        className="flex items-center justify-center w-12 h-12 rounded-full transition bg-[var(--btn-bg)] hover:opacity-80"
      >
        <FontAwesomeIcon icon={faArrowUp} className="text-[var(--btn-text)] text-xl" />
      </button>
      <span className="absolute -top-9 left-1/2 transform -translate-x-1/2 scale-0 group-hover:scale-100 transition bg-[var(--chat-bg)] text-[var(--text-color)] text-sm font-semibold px-2 py-1 rounded-md shadow-md border border-[var(--text-color)]">
        Send
      </span>
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
