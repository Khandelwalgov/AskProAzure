import React, { useState } from "react";
import { useNavigate, Link } from "react-router-dom";
import Beams from './Beams';

export default function Login() {
  const [email, setEmail] = useState("");
  const [pass, setPass] = useState("");
  const [error, setError] = useState("");
  const navigate = useNavigate();

  const handleLogin = async () => {
    try {
      const res = await fetch("https://askpro.duckdns.org/login", {
        method: "POST",
        credentials: "include",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email, password: pass }),
      });
      const data = await res.json();
      if (res.ok) {
          localStorage.setItem("uuid", data.uuid); // ✅ set UUID
        navigate("/chat");
      } else {
        setError(data.error || "Login failed.");
      }
    } catch (e) {
      setError("Network error");
    }
  };

  return (
  <div className="auth-page">
    <div className="iridescence">
    <Beams
      beamWidth={1.1}
      beamHeight={30}
      beamNumber={50}
      lightColor="#5266ff"
      speed={10}
      noiseIntensity={1.75}
      scale={0.2}
      rotation={66}
    />
    </div>
    <div className="glass-card auth-card">
      <h1 className="glow-title">Welcome Back</h1>
      <input
        type="email"
        placeholder="Email"
        value={email}
        onChange={e => setEmail(e.target.value)}
      />
      <input
        type="password"
        placeholder="Password"
        value={pass}
        onChange={e => setPass(e.target.value)}
      />
      <button onClick={handleLogin}>Login</button>
      {error && <p className="error">{error}</p>}
      <p className="form-footer">
        New here? <Link to="/signup">Sign Up</Link>
      </p>
    </div>
  </div>
);
  
}
