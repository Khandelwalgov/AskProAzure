import React, { useEffect, useRef, useState } from "react";
import { apiUrl } from "../api";
import "../pages/ChatDashboard.css";

function Sidebar({ className }) {
  const [selectedFile, setSelectedFile] = useState(null);
  const [files, setFiles] = useState([]);
  const fileInputRef = useRef(null);

  const fetchFiles = async () => {
    const res = await fetch(apiUrl("/list-files"), {
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

  const handleFileChange = (event) => {
    const file = event.target.files[0];
    if (file) {
      setSelectedFile(file);
      handleUpload(file);
    }
  };

  const handleUpload = async (fileToUpload) => {
    if (!fileToUpload) return;

    const formData = new FormData();
    formData.append("file", fileToUpload);

    try {
      const res = await fetch(apiUrl("/upload"), {
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
      setSelectedFile(null);
      if (fileInputRef.current) fileInputRef.current.value = "";
    }
  };

  const handleDelete = async (fileId) => {
    const res = await fetch(apiUrl("/delete-file"), {
      method: "POST",
      credentials: "include",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ file_id: fileId }),
    });
    if (res.ok) await fetchFiles();
  };

  const handleLogout = async () => {
    await fetch(apiUrl("/logout"), {
      method: "POST",
      credentials: "include",
    });
    localStorage.removeItem("uuid");
    window.location.href = "/";
  };

  const handleView = async (fileId) => {
    const res = await fetch(apiUrl(`/view-file/${fileId}`), {
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
        <h2 className="sidebar-heading">Your Files</h2>
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
            files.map((file) => (
              <div key={file.id} className="file-row">
                <span className="file-name">{file.filename}</span>
                <div className="file-actions">
                  <button onClick={() => handleView(file.id)} className="view-btn">
                    <svg
                      xmlns="http://www.w3.org/2000/svg"
                      width="18"
                      height="18"
                      viewBox="0 0 24 24"
                      fill="none"
                      stroke="currentColor"
                      strokeWidth="2"
                      strokeLinecap="round"
                      strokeLinejoin="round"
                    >
                      <path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"></path>
                      <circle cx="12" cy="12" r="3"></circle>
                    </svg>
                  </button>
                  <button
                    onClick={() => handleDelete(file.id)}
                    className="delete-btn"
                  >
                    &times;
                  </button>
                </div>
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
