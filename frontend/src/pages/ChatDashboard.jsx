import React, { useEffect, useRef, useState } from "react";
import ReactMarkdown from "react-markdown";
import rehypeSanitize from "rehype-sanitize";
import Sidebar from "../components/Sidebar";
import CitationList from "../components/CitationList";
import { apiUrl } from "../api";
import "./ChatDashboard.css";

export default function ChatDashboard() {
  const [messages, setMessages] = useState([]);
  const [query, setQuery] = useState("");
  const [sidebarOpen, setSidebarOpen] = useState(true);
  const logRef = useRef();

  const sendQuery = async () => {
    const question = query.trim();
    if (!question) return;

    setMessages((prev) => [...prev, { role: "user", content: question }]);
    setQuery("");

    const uuid = localStorage.getItem("uuid");
    if (!uuid) {
      setMessages((prev) => [
        ...prev,
        { role: "bot", content: "No user UUID found. Please log in again." },
      ]);
      return;
    }

    try {
      const res = await fetch(apiUrl("/query"), {
        method: "POST",
        credentials: "include",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ query: question, uuid }),
      });

      const data = await res.json();

      if (data.error) {
        setMessages((prev) => [...prev, { role: "bot", content: data.error }]);
        return;
      }

      const answer = data.answer?.trim() || "No answer generated.";
      setMessages((prev) => [
        ...prev,
        {
          role: "bot",
          content: answer,
          citations: data.citations || data.sources || [],
        },
      ]);
    } catch {
      setMessages((prev) => [
        ...prev,
        { role: "bot", content: "Network or server error. Try again later." },
      ]);
    }
  };

  useEffect(() => {
    if (logRef.current) {
      logRef.current.scrollTop = logRef.current.scrollHeight;
    }
  }, [messages]);

  return (
    <div className="dashboard-container">
      <Sidebar className={sidebarOpen ? "open" : ""} />

      <div className={`main-chat ${sidebarOpen ? "sidebar-open" : ""}`}>
        <div className="chat-header">
          <button className="toggle-btn" onClick={() => setSidebarOpen(!sidebarOpen)}>
            {sidebarOpen ? (
              <svg
                xmlns="http://www.w3.org/2000/svg"
                width="20"
                height="20"
                viewBox="0 0 24 24"
                fill="none"
                stroke="currentColor"
                strokeWidth="2.5"
                strokeLinecap="round"
                strokeLinejoin="round"
                aria-hidden="true"
              >
                <line x1="18" y1="6" x2="6" y2="18" />
                <line x1="6" y1="6" x2="18" y2="18" />
              </svg>
            ) : (
              <svg
                xmlns="http://www.w3.org/2000/svg"
                width="20"
                height="20"
                viewBox="0 0 24 24"
                fill="none"
                stroke="currentColor"
                strokeWidth="2.5"
                strokeLinecap="round"
                strokeLinejoin="round"
                aria-hidden="true"
              >
                <line x1="3" y1="12" x2="21" y2="12" />
                <line x1="3" y1="6" x2="21" y2="6" />
                <line x1="3" y1="18" x2="21" y2="18" />
              </svg>
            )}
          </button>

          <h1 className="logo">
            AskPro<span>.AI</span>
          </h1>
        </div>

        <div className="chat-log" ref={logRef}>
          {messages.map((message, index) => (
            <div key={`${message.role}-${index}`} className={`chat-msg ${message.role}`}>
              <div className="bubble">
                <ReactMarkdown rehypePlugins={[rehypeSanitize]}>{message.content}</ReactMarkdown>
                <CitationList citations={message.citations} />
              </div>
            </div>
          ))}
        </div>

        <div className="chat-input">
          <input
            value={query}
            onChange={(event) => setQuery(event.target.value)}
            onKeyDown={(event) => event.key === "Enter" && sendQuery()}
            placeholder="Ask something..."
          />
          <button onClick={sendQuery}>Send</button>
        </div>
      </div>
    </div>
  );
}
