// src/components/Sidebar.jsx
import React, { useEffect, useState, useRef } from 'react';
import "../pages/ChatDashboard.css"; // We will use the main CSS file

function Sidebar({ className }) {
  const [selectedFile, setSelectedFile] = useState(null);
  const [files, setFiles] = useState([]);
  const fileInputRef = useRef(null);

  const fetchFiles = async () => {
    const res = await fetch("https://askpro.duckdns.org/list-files", {
      credentials: "include",
    });
    const data = await res.json();
    if (res.ok && !data.error) {
      setFiles(data);
    } else {
      setFiles([]);
    }
  };

  useEffect(() => {
    fetchFiles();
  }, []);

  const handleFileChange = (e) => {
    const file = e.target.files[0];
    if (file) {
      setSelectedFile(file);
      // Automatically trigger upload when a file is selected
      handleUpload(file);
    }
  };

  const handleUpload = async (fileToUpload) => {
  if (!fileToUpload) return;
  const formData = new FormData();
  formData.append("file", fileToUpload);

  try {
    const res = await fetch("https://askpro.duckdns.org/upload", {
      method: "POST",
      credentials: "include",
      body: formData,
    });

    const data = await res.json();
    if (!res.ok) {
      alert(data.error || "Upload failed");
    } else {
      await fetchFiles();
    }
  } catch (err) {
    alert("Something went wrong during upload.");
    console.error("Upload error:", err);
  } finally {
    // ✅ Always reset after upload attempt
    setSelectedFile(null);
    if (fileInputRef.current) fileInputRef.current.value = "";
  }
};


  const handleDelete = async (fileId) => {
    const res = await fetch("https://askpro.duckdns.org/delete-file", {
      method: "POST",
      credentials: "include",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ file_id: fileId }),
    });
    if (res.ok) await fetchFiles();
  };

  const handleLogout = async () => {
    await fetch("https://askpro.duckdns.org/logout", {
      method: "POST",
      credentials: "include"
    });
    localStorage.removeItem("uuid");
    window.location.href = "/";
  };
const handleView = async (fileId) => {
  const res = await fetch(`https://askpro.duckdns.org/view-file/${fileId}`, {
    credentials: "include",
  });
  const data = await res.json();
  if (res.ok && data.url) {
    window.open(data.url, "_blank");
  } else {
    alert("Failed to load file.");
  }
};

  return (
    <div className={`sidebar ${className}`}>
      <div>
        <h2 className="sidebar-heading">📁 Your Files</h2>
        <div className="upload-section">
          <input
            type="file"
            onChange={handleFileChange}
            className="hidden-file-input"
            ref={fileInputRef}
            id="file-upload"
          />
          <label htmlFor="file-upload" className="upload-btn">
            {selectedFile ? `Uploading: ${selectedFile.name}` : "Upload New File"}
          </label>
        </div>
        <div className="file-list">
          {files.length === 0 ? (
            <p className="empty-msg">No files uploaded yet.</p>
          ) : (
            files.map((file, i) => (
              <div key={file.id} className="file-row">
                <span className="file-name">{file.filename}</span>
                <button onClick={() => handleView(file.id)} className="view-btn">👁️</button>
                <button
                  onClick={() => handleDelete(file.id)}
                  className="delete-btn"
                >
                  &times;
                </button>
              </div>
            ))
          )}
        </div>
      </div>
      <button onClick={handleLogout} className="logout-btn">
        Logout
      </button>
    </div>
  );
}

export default Sidebar;