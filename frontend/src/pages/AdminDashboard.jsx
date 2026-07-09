import React, { useEffect, useMemo, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import { apiUrl } from "../api";
import "./AdminDashboard.css";

export default function AdminDashboard() {
  const [config, setConfig] = useState(null);
  const [systemPrompt, setSystemPrompt] = useState("");
  const [chatTitle, setChatTitle] = useState("AskPro Chat");
  const [apiEnabled, setApiEnabled] = useState(true);
  const [publicEnabled, setPublicEnabled] = useState(true);
  const [allowedOrigins, setAllowedOrigins] = useState("*");
  const [selectedFile, setSelectedFile] = useState(null);
  const [status, setStatus] = useState("");
  const [error, setError] = useState("");
  const fileInputRef = useRef(null);
  const navigate = useNavigate();

  const publicLink = useMemo(() => {
    if (!config?.public_path) return "";
    return `${window.location.origin}${config.public_path}`;
  }, [config]);

  const apiEndpoint = useMemo(() => apiUrl(config?.api_endpoint || "/api/chat"), [config]);
  const apiKey = config?.api_key || "askpro_key";

  const fetchSnippet = useMemo(() => `fetch("${apiEndpoint}", {
  method: "POST",
  headers: {
    "Content-Type": "application/json",
    "X-API-Key": "${apiKey}"
  },
  body: JSON.stringify({ message })
})`, [apiEndpoint, apiKey]);

  const curlSnippet = useMemo(() => `curl -X POST "${apiEndpoint}" \
  -H "Content-Type: application/json" \
  -H "X-API-Key: ${apiKey}" \
  -d '{"message":"Question here"}'`, [apiEndpoint, apiKey]);

  const iframeSnippet = useMemo(() => {
    if (!publicLink) return "";
    return `<iframe src="${publicLink}" width="420" height="640" style="border:0;border-radius:8px;overflow:hidden"></iframe>`;
  }, [publicLink]);

  const fetchConfig = async () => {
    setError("");
    const res = await fetch(apiUrl("/admin/config"), { credentials: "include" });
    const data = await res.json();
    if (!res.ok) {
      setError(data.error || "Unable to load admin configuration.");
      return;
    }
    setConfig(data);
    setSystemPrompt(data.system_prompt || "");
    setChatTitle(data.chat_title || "AskPro Chat");
    setApiEnabled(Boolean(data.api_enabled));
    setPublicEnabled(Boolean(data.public_enabled));
    setAllowedOrigins(data.allowed_origins || "*");
  };

  useEffect(() => {
    fetchConfig();
  }, []);

  const uploadFile = async (file) => {
    if (!file) return;
    setSelectedFile(file);
    setStatus("Uploading document...");
    setError("");

    const formData = new FormData();
    formData.append("file", file);

    try {
      const res = await fetch(apiUrl("/upload"), {
        method: "POST",
        credentials: "include",
        body: formData,
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.error || "Upload failed");
      setStatus("Document added to corpus.");
      await fetchConfig();
    } catch (err) {
      setError(err.message);
    } finally {
      setSelectedFile(null);
      if (fileInputRef.current) fileInputRef.current.value = "";
    }
  };

  const deleteFile = async (fileId) => {
    setStatus("Deleting document...");
    setError("");
    const res = await fetch(apiUrl("/delete-file"), {
      method: "POST",
      credentials: "include",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ file_id: fileId }),
    });
    const data = await res.json();
    if (!res.ok) {
      setError(data.error || "Delete failed");
      return;
    }
    setStatus("Document removed.");
    await fetchConfig();
  };

  const saveConfig = async () => {
    setStatus("Saving configuration...");
    setError("");
    const res = await fetch(apiUrl("/admin/config"), {
      method: "POST",
      credentials: "include",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        system_prompt: systemPrompt,
        chat_title: chatTitle,
        api_enabled: apiEnabled,
        public_enabled: publicEnabled,
        allowed_origins: allowedOrigins,
      }),
    });
    const data = await res.json();
    if (!res.ok) {
      setError(data.error || "Configuration save failed");
      return;
    }
    setSystemPrompt(data.system_prompt);
    setChatTitle(data.chat_title);
    setApiEnabled(Boolean(data.api_enabled));
    setPublicEnabled(Boolean(data.public_enabled));
    setAllowedOrigins(data.allowed_origins || "*");
    setConfig((prev) => ({ ...prev, ...data }));
    setStatus("Configuration saved.");
  };

  const regenerateKey = async () => {
    setStatus("Regenerating API key...");
    setError("");
    const res = await fetch(apiUrl("/admin/regenerate-api-key"), {
      method: "POST",
      credentials: "include",
    });
    const data = await res.json();
    if (!res.ok) {
      setError(data.error || "Could not regenerate API key");
      return;
    }
    setConfig((prev) => ({ ...prev, api_key: data.api_key }));
    setStatus("API key regenerated.");
  };

  const copyText = async (value, label) => {
    await navigator.clipboard.writeText(value);
    setStatus(`${label} copied.`);
  };

  const logout = async () => {
    await fetch(apiUrl("/logout"), { method: "POST", credentials: "include" });
    localStorage.removeItem("uuid");
    navigate("/");
  };

  if (error && !config) {
    return (
      <main className="admin-shell admin-centered">
        <section className="admin-panel narrow">
          <h1>Admin access</h1>
          <p className="admin-error">{error}</p>
          <button onClick={() => navigate("/login")}>Login</button>
        </section>
      </main>
    );
  }

  return (
    <main className="admin-shell">
      <header className="admin-topbar">
        <div>
          <h1>AskPro Admin</h1>
          <p>{config?.email || "Organization workspace"}</p>
        </div>
        <div className="admin-actions">
          {status && <span className="admin-status">{status}</span>}
          <button onClick={logout}>Logout</button>
        </div>
      </header>

      {error && <div className="admin-error full">{error}</div>}

      <section className="admin-grid">
        <div className="admin-panel corpus-panel">
          <div className="panel-heading">
            <h2>Document Corpus</h2>
            <label className="admin-upload-btn">
              <input
                type="file"
                ref={fileInputRef}
                onChange={(event) => uploadFile(event.target.files[0])}
              />
              {selectedFile ? selectedFile.name : "Add Document"}
            </label>
          </div>
          <div className="admin-file-list">
            {config?.files?.length ? (
              config.files.map((file) => (
                <div className="admin-file-row" key={file.id}>
                  <span>{file.filename}</span>
                  <button onClick={() => deleteFile(file.id)}>Remove</button>
                </div>
              ))
            ) : (
              <p className="muted">No corpus documents yet.</p>
            )}
          </div>
        </div>

        <div className="admin-panel settings-panel">
          <div className="panel-heading">
            <h2>Workspace Settings</h2>
            <button onClick={saveConfig}>Save All</button>
          </div>
          <label>Chat Title</label>
          <input
            className="admin-text-input"
            value={chatTitle}
            onChange={(event) => setChatTitle(event.target.value)}
            placeholder="AskPro Chat"
          />
          <label className="admin-toggle">
            <input
              type="checkbox"
              checked={apiEnabled}
              onChange={(event) => setApiEnabled(event.target.checked)}
            />
            API access enabled
          </label>
          <label className="admin-toggle">
            <input
              type="checkbox"
              checked={publicEnabled}
              onChange={(event) => setPublicEnabled(event.target.checked)}
            />
            Hosted chat link enabled
          </label>
          <label>Allowed API Origins</label>
          <textarea
            className="admin-small-textarea"
            value={allowedOrigins}
            onChange={(event) => setAllowedOrigins(event.target.value)}
            spellCheck="false"
          />
        </div>

        <div className="admin-panel prompt-panel">
          <div className="panel-heading">
            <h2>System Prompt</h2>
            <button onClick={saveConfig}>Save All</button>
          </div>
          <textarea
            value={systemPrompt}
            onChange={(event) => setSystemPrompt(event.target.value)}
            spellCheck="false"
          />
        </div>

        <div className="admin-panel integration-panel">
          <div className="panel-heading">
            <h2>API Access</h2>
            <button onClick={regenerateKey}>Regenerate</button>
          </div>
          {!apiEnabled && <p className="muted">API access is currently disabled.</p>}
          <label>Endpoint</label>
          <div className="copy-row">
            <code>{apiEndpoint}</code>
            <button onClick={() => copyText(apiEndpoint, "Endpoint")}>Copy</button>
          </div>
          <label>API Key</label>
          <div className="copy-row">
            <code>{config?.api_key || ""}</code>
            <button onClick={() => copyText(config?.api_key || "", "API key")}>Copy</button>
          </div>
          <pre>{fetchSnippet}</pre>
          <pre>{curlSnippet}</pre>
        </div>

        <div className="admin-panel link-panel">
          <div className="panel-heading">
            <h2>Hosted Chat Link</h2>
            <button disabled={!publicEnabled} onClick={() => copyText(publicLink, "Hosted chat link")}>Copy</button>
          </div>
          {!publicEnabled && <p className="muted">Hosted chat link is currently disabled.</p>}
          <div className="copy-row wide">
            <code>{publicLink}</code>
            <button disabled={!publicEnabled} onClick={() => window.open(publicLink, "_blank")}>Open</button>
          </div>
          <label>Embed Snippet</label>
          <pre>{iframeSnippet}</pre>
          <button disabled={!publicEnabled} onClick={() => copyText(iframeSnippet, "Embed snippet")}>Copy Embed</button>
        </div>
      </section>
    </main>
  );
}
