import React from "react";
import { Button } from "@mui/material";

class ChatHistory extends React.Component {
  render() {
    return (
      <div className="history-panel">
        <h3>Conversations</h3>
        <Button variant="outlined" className="new-chat-btn" onClick={this.props.startNewConversation}>+ New Chat</Button>
        {this.props.conversations.map((conv, index) => (
          <div key={index} onClick={() => this.props.switchConversation(index)} className="conversation-tab">
            {conv.name}
          </div>
        ))}
      </div>
    );
  }
}

export default ChatHistory;
