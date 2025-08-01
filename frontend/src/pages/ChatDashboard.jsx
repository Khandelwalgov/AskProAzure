import React, { useState, useEffect, useRef } from "react";
import Sidebar from "../components/Sidebar";
import "./ChatDashboard.css";

export default function ChatDashboard() {
  const [messages, setMessages] = useState([]);
  const [query, setQuery] = useState("");
  const [sidebarOpen, setSidebarOpen] = useState(true);
  const logRef = useRef();

  const sendQuery = async () => {
    if (!query.trim()) return;

    setMessages(prev => [...prev, { role: "user", content: query }]);
    setQuery("");

    const uuid = localStorage.getItem("uuid");
    if (!uuid) {
      setMessages(prev => [...prev, {
        role: "bot",
        content: "⚠️ No user UUID found. Please log in again."
      }]);
      return;
    }

    try {
      const res = await fetch("https://askpro.duckdns.org/query", {
        method: "POST",
        credentials: "include",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ query, uuid })
      });

      const data = await res.json();

      if (data.error) {
        setMessages(prev => [...prev, { role: "bot", content: `❌ ${data.error}` }]);
        return;
      }

      const answer = data.answer?.trim() || "⚠️ No answer generated.";
      setMessages(prev => [...prev, { role: "bot", content: answer }]);

    } catch (err) {
      setMessages(prev => [...prev, {
        role: "bot",
        content: "❌ Network or server error. Try again later."
      }]);
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
          
            {/* {sidebarOpen ? "⬅" : "➡"} */}
            <button className="toggle-btn" onClick={() => setSidebarOpen(!sidebarOpen)}>
  {sidebarOpen ? (
    // "X" icon (Size 20x20)
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
    >
      <line x1="18" y1="6" x2="6" y2="18"></line>
      <line x1="6" y1="6" x2="18" y2="18"></line>
    </svg>
  ) : (
    // Hamburger icon (Size 20x20)
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
    >
      <line x1="3" y1="12" x2="21" y2="12"></line>
      <line x1="3" y1="6" x2="21" y2="6"></line>
      <line x1="3" y1="18" x2="21" y2="18"></line>
    </svg>
  )}
</button>

          
          <h1 className="logo">AskPro<span>.AI</span></h1>
        </div>

        <div className="chat-log" ref={logRef}>
          {messages.map((m, i) => (
            <div
              key={i}
              className={`chat-msg ${m.role}`}
            >
              <div className="bubble">{m.content}</div>
            </div>
          ))}
        </div>

        <div className="chat-input">
          <input
            value={query}
            onChange={e => setQuery(e.target.value)}
            onKeyDown={e => e.key === "Enter" && sendQuery()}
            placeholder="Ask something..."
          />
          <button onClick={sendQuery}>Send</button>
        </div>
      </div>
    </div>
  );
}
