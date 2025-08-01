// // src/components/Sidebar.jsx
// import React, { useEffect, useState } from 'react';
// import "../pages/ChatDashboard.css";


// function Sidebar() {
//   const [selectedFile, setSelectedFile] = useState(null);
//   const [files, setFiles] = useState([]);

//   const fetchFiles = async () => {
//     const res = await fetch("https://askpro.duckdns.org/list-files", {
//       credentials: "include",
//     });
//     const data = await res.json();
//     if (!data.error) setFiles(data);
//   };

//   useEffect(() => {
//     fetchFiles();
//   }, []);

//   const handleUpload = async () => {
//     if (!selectedFile) return;
//     const formData = new FormData();
//     formData.append("file", selectedFile);
//     const res = await fetch("https://askpro.duckdns.org/upload", {
//       method: "POST",
//       credentials: "include",
//       body: formData,
//     });
//     if (res.ok) {
//       setSelectedFile(null);
//       await fetchFiles();
//     }
//   };

//   const handleDelete = async (filename) => {
//     const res = await fetch("https://askpro.duckdns.org/delete-file", {
//       method: "POST",
//       credentials: "include",
//       headers: { "Content-Type": "application/json" },
//       body: JSON.stringify({ filename }),
//     });
//     if (res.ok) await fetchFiles();
//   };

//   const handleLogout = async () => {
//     await fetch("https://askpro.duckdns.org/logout", {
//   method: "POST",
//   credentials: "include"
// });
// localStorage.removeItem("uuid");
//     window.location.href = "/";
//   };

//   return (
//     <div style={styles.sidebar}>
//       <h2 style={styles.heading}>📁 Your Files</h2>

//       <div style={styles.uploadContainer}>
//         <input
//           type="file"
//           onChange={(e) => setSelectedFile(e.target.files[0])}
//         />
//         <button onClick={handleUpload} style={styles.uploadBtn}>Upload</button>
//       </div>

//       <div style={styles.fileList}>
//         {files.length === 0 ? (
//           <p style={styles.emptyMsg}>No files uploaded yet.</p>
//         ) : (
//           files.map((file, i) => (
//             <div key={i} style={styles.fileRow}>
//               <span style={styles.fileName}>{file}</span>
//               <button
//                 onClick={() => handleDelete(file)}
//                 style={styles.deleteBtn}
//               >
//                 ❌
//               </button>
//             </div>
//           ))
//         )}
//       </div>

//       <button onClick={handleLogout} style={styles.logoutBtn}>🚪 Logout</button>
//     </div>
//   );
// }

// const styles = {
//   sidebar: {
//     background: "#1e1e1e",
//     color: "#f1f1f1",
//     width: "280px",
//     padding: "20px",
//     // background: "#f4f6f9",
//     height: "100vh",
//     borderRight: "1px solid #ccc",
//     boxSizing: "border-box",
//   },
//   heading: {
//     marginBottom: "20px",
//     fontSize: "20px",
//     color: "#333",
//   },
//   uploadContainer: {
//     marginBottom: "20px",
//     display: "flex",
//     flexDirection: "column",
//     gap: "8px",
//   },
//   uploadBtn: {
//     padding: "6px 12px",
//     background: "#007bff",
//     color: "#fff",
//     border: "none",
//     cursor: "pointer",
//     borderRadius: "4px",
//   },
//   fileList: {
//     maxHeight: "calc(100vh - 250px)",
//     overflowY: "auto",
//   },
//   fileRow: {
//     display: "flex",
//     justifyContent: "space-between",
//     alignItems: "center",
//     padding: "6px 0",
//     borderBottom: "1px solid #ddd",
//   },
//   fileName: {
//     maxWidth: "170px",
//     overflow: "hidden",
//     textOverflow: "ellipsis",
//     whiteSpace: "nowrap",
//   },
//   deleteBtn: {
//     background: "none",
//     border: "none",
//     cursor: "pointer",
//     color: "red",
//     fontSize: "14px",
//   },
//   logoutBtn: {
//     marginTop: "20px",
//     padding: "8px 12px",
//     background: "#e74c3c",
//     color: "#fff",
//     border: "none",
//     cursor: "pointer",
//     width: "100%",
//     borderRadius: "4px",
//   },
//   emptyMsg: {
//     color: "#888",
//     fontSize: "14px",
//     marginTop: "10px",
//   },
// };

// export default Sidebar;

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

    const res = await fetch("https://askpro.duckdns.org/upload", {
      method: "POST",
      credentials: "include",
      body: formData,
    });

    if (res.ok) {
      setSelectedFile(null); // Clear selection
      fileInputRef.current.value = ""; // Reset file input
      await fetchFiles();
    }
  };

  const handleDelete = async (filename) => {
    const res = await fetch("https://askpro.duckdns.org/delete-file", {
      method: "POST",
      credentials: "include",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ filename }),
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
              <div key={i} className="file-row">
                <span className="file-name">{file}</span>
                <button
                  onClick={() => handleDelete(file)}
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