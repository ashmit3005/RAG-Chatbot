import React, { useState } from "react";
import { MenuIcon } from "lucide-react"; // Icon for toggle

const ChatHistory = ({ conversations, switchConversation, startNewConversation, selectedConversation, toggleSidebar }) => {
  const [isOpen, setIsOpen] = useState(false);

  return (
    <div
      className={`transition-all duration-300 shadow-md h-full fixed top-0 left-0 flex flex-col 
      ${isOpen ? "w-72" : "w-16"} bg-[var(--chat-bg)] text-[var(--text-color)]`}
    >
      {/* Sidebar Toggle Button */}
      <button
        className="p-4 hover:bg-[var(--btn-bg)] transition-all text-[var(--text-color)]"
        onClick={() => {
          setIsOpen(!isOpen);
          toggleSidebar(!isOpen);
        }}
      >
        <MenuIcon size={24} />
      </button>

      {/* Sidebar Content (only visible when open) */}
      {isOpen && (
        <div className="p-4 flex flex-col space-y-3">
          <h3 className="text-lg font-semibold">Past Conversations</h3>
          <button
            className="p-2 rounded-md bg-[var(--btn-bg)] text-[var(--btn-text)] hover:opacity-80 transition-all"
            onClick={startNewConversation}
          >
            New Chat+
          </button>
          <div className="flex flex-col space-y-2">
            {conversations.map((conv, index) => (
              <div
                key={index}
                onClick={() => switchConversation(index)}
                className={`p-2 rounded-md cursor-pointer transition-all ${
                  selectedConversation === index
                    ? "bg-[var(--btn-bg)] text-[var(--btn-text)]"
                    : "hover:bg-gray-500"
                }`}
              >
                {conv.name}
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
};

export default ChatHistory;
