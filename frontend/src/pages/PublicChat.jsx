import React, { useEffect, useRef, useState } from "react";
import { useParams } from "react-router-dom";
import ReactMarkdown from "react-markdown";
import rehypeSanitize from "rehype-sanitize";
import CitationList from "../components/CitationList";
import { apiUrl } from "../api";
import "./PublicChat.css";

export default function PublicChat() {
  const { publicId } = useParams();
  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState("");
  const [title, setTitle] = useState("AskPro Chat");
  const [linkError, setLinkError] = useState("");
  const [loading, setLoading] = useState(false);
  const logRef = useRef(null);

  useEffect(() => {
    const loadMeta = async () => {
      try {
        const res = await fetch(apiUrl(`/public-chat/${publicId}/meta`));
        const data = await res.json();
        if (!res.ok) {
          setLinkError(data.error || "Chat link is unavailable.");
          return;
        }
        setTitle(data.chat_title || "AskPro Chat");
        document.title = data.chat_title || "AskPro Chat";
      } catch {
        setLinkError("Chat link is unavailable.");
      }
    };

    loadMeta();
  }, [publicId]);

  const sendMessage = async () => {
    const message = input.trim();
    if (!message || loading || linkError) return;

    setMessages((prev) => [...prev, { role: "user", content: message }]);
    setInput("");
    setLoading(true);

    try {
      const res = await fetch(apiUrl(`/public-chat/${publicId}`), {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ message }),
      });
      const data = await res.json();
      setMessages((prev) => [
        ...prev,
        {
          role: "bot",
          content: res.ok ? data.answer : data.error || "Request failed",
          citations: res.ok ? data.citations || data.sources || [] : [],
        },
      ]);
    } catch {
      setMessages((prev) => [...prev, { role: "bot", content: "Network error" }]);
    } finally {
      setLoading(false);
      requestAnimationFrame(() => {
        if (logRef.current) logRef.current.scrollTop = logRef.current.scrollHeight;
      });
    }
  };

  return (
    <main className="public-chat-shell">
      <section className="public-chat-window">
        <header>
          <h1>{title}</h1>
        </header>
        <div className="public-chat-log" ref={logRef}>
          {linkError ? (
            <p className="public-empty">{linkError}</p>
          ) : messages.length === 0 ? (
            <p className="public-empty">Ask a question.</p>
          ) : null}
          {messages.map((message, index) => (
            <div className={`public-msg ${message.role}`} key={`${message.role}-${index}`}>
              <div className="public-bubble">
                <ReactMarkdown rehypePlugins={[rehypeSanitize]}>{message.content}</ReactMarkdown>
                <CitationList citations={message.citations} />
              </div>
            </div>
          ))}
          {loading && <div className="public-loading">Thinking...</div>}
        </div>
        <div className="public-chat-input">
          <input
            value={input}
            onChange={(event) => setInput(event.target.value)}
            onKeyDown={(event) => event.key === "Enter" && sendMessage()}
            placeholder="Type your question"
            disabled={Boolean(linkError)}
          />
          <button onClick={sendMessage} disabled={loading || Boolean(linkError)}>
            Send
          </button>
        </div>
      </section>
    </main>
  );
}
