import React, { Component } from "react";
import ChatHistory from "./ChatHistory";
import "./styles.css";

class App extends Component {
  constructor(props) {
    super(props);
    this.state = {
      conversations: [],
      activeConversation: null,
      input: "",
      darkMode: false, // Track dark mode state
    };
  }

  handleSend = () => {
    const { input, activeConversation, conversations } = this.state;
    if (input.trim() === "") return;

    let newConversations = [...conversations];

    if (activeConversation === null) {
      const newConversation = {
        id: newConversations.length,
        name: input, // Name the conversation after the first query
        messages: [{ text: input, sender: "user" }, { text: "This is a hardcoded response.", sender: "bot" }],
      };
      newConversations.push(newConversation);
      this.setState({ conversations: newConversations, activeConversation: newConversation.id, input: "" });
    } else {
      newConversations[activeConversation].messages.push({ text: input, sender: "user" });
      newConversations[activeConversation].messages.push({ text: "This is a hardcoded response.", sender: "bot" });
      this.setState({ conversations: newConversations, input: "" });
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

  startNewConversation = () => {
    this.setState({ activeConversation: null, input: "" });
  };

  switchConversation = (index) => {
    this.setState({ activeConversation: index });
  };

  toggleDarkMode = () => {
    this.setState((prevState) => ({ darkMode: !prevState.darkMode }));
  };

  render() {
    const { conversations, activeConversation, input, darkMode } = this.state;
    const currentMessages = activeConversation !== null ? conversations[activeConversation].messages : [];

    return (
      <div className={`app-container ${darkMode ? "dark-mode" : "light-mode"}`}>
        <button className="toggle-mode-btn" onClick={this.toggleDarkMode}>
          {darkMode ? "Light Mode" : "Dark Mode"}
        </button>
        <div className="chat-layout">
          <ChatHistory
            conversations={conversations}
            switchConversation={this.switchConversation}
            startNewConversation={this.startNewConversation}
          />
          <div className="chat-container">
            <div className="chat-window">
              {currentMessages.map((msg, index) => (
                <div key={index} className={msg.sender === "user" ? "user-msg" : "bot-msg"}>
                  {msg.text}
                </div>
              ))}
            </div>
            <div className="input-area">
              <input
                type="text"
                placeholder="Type your query..."
                value={input}
                onChange={this.handleInputChange}
                onKeyPress={this.handleKeyPress}
              />
              <button onClick={this.handleSend}>Send</button>
              <input type="file" className="file-upload" />
            </div>
          </div>
        </div>
      </div>
    );
  }
}

export default App;
