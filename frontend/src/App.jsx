import React from "react";
import { BrowserRouter, Routes, Route } from "react-router-dom";
import Landing from "./pages/Landing.jsx";
import Signup from "./pages/Signup.jsx";
import Login from "./pages/Login.jsx";
import ChatDashboard from "./pages/ChatDashboard.jsx";
import AdminDashboard from "./pages/AdminDashboard.jsx";
import PublicChat from "./pages/PublicChat.jsx";

function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<Landing />} />
        <Route path="/signup" element={<Signup />} />
        <Route path="/login" element={<Login />} />
        <Route path="/chat" element={<ChatDashboard />} />
        <Route path="/admin" element={<AdminDashboard />} />
        <Route path="/public/:publicId" element={<PublicChat />} />
      </Routes>
    </BrowserRouter>
  );
}

export default App;
