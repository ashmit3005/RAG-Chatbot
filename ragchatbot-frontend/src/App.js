import React, { Component } from "react";
import ChatHistory from "./ChatHistory";
import FAQSection from "./FAQSection";
import "./styles.css";
import { Button, Switch, FormControlLabel, TextField } from "@mui/material";
import PowerIcon from "@mui/icons-material/Power";
import { motion } from "framer-motion";

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
        <header className="app-header">
          <PowerIcon className="app-logo" />
          <h1>PowerWise</h1>
          <p>A Domain-Knowledgeable Chatbot in Power Quality</p>
          <FormControlLabel
            control={<Switch checked={darkMode} onChange={this.toggleDarkMode} />}
            label="Dark Mode"
            className="toggle-switch"
          />
        </header>

        <div className="chat-layout">
          <ChatHistory conversations={conversations} switchConversation={this.switchConversation} startNewConversation={this.startNewConversation} />
          
          <motion.div className="chat-container">
            <div className="chat-window">
              {currentMessages.map((msg, index) => (
                <motion.div 
                  key={index}
                  className={msg.sender === "user" ? "user-msg" : "bot-msg"}
                  initial={{ opacity: 0, x: msg.sender === "user" ? 50 : -50 }}
                  animate={{ opacity: 1, x: 0 }}
                  transition={{ duration: 0.3 }}
                >
                  {msg.text}
                  {msg.file && (
                    <p className="file-attachment">📎 {msg.file.name}</p>
                  )}
                </motion.div>
              ))}
            </div>

            <div className="input-area">
              <TextField
                multiline
                minRows={1}
                maxRows={5}
                fullWidth
                placeholder="Type your query..."
                value={input}
                onChange={this.handleInputChange}
                onKeyPress={this.handleKeyPress}
                className="chat-input"
              />
              <input type="file" onChange={this.handleFileChange} className="file-upload" />
              <Button variant="contained" onClick={this.handleSend} className="send-button">Send</Button>
            </div>
          </motion.div>

          <FAQSection />
        </div>
      </div>
    );
  }
}

export default App;
