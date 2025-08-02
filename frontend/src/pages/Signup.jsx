import React, { useState } from "react";
import { useNavigate, Link } from "react-router-dom";
import Beams from './Beams';

export default function Signup() {
  const [email, setEmail] = useState("");
  const [pass1, setPass1] = useState("");
  const [pass2, setPass2] = useState("");
  const [error, setError] = useState("");
  const navigate = useNavigate();

  const handleSignup = async () => {
    // if (pass1 !== pass2) {
    //   setError("Passwords do not match.");
    //   return;
    // }
    setError(""); 

  const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]{2,}$/i;

  if (!email || !pass1 || !pass2) {
    setError("Please fill in all fields.");
    return;
  }

  if (!emailRegex.test(email)) {
    setError("Invalid email format.");
    return;
  }

  if (pass1.length < 6) {
    setError("Password must be at least 6 characters long.");
    return;
  }

  if (pass1 !== pass2) {
    setError("Passwords do not match.");
    return;
  }


    try {
      const res = await fetch("/api/signup", {
        method: "POST",
        credentials: "include",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email, password: pass1, is_organization: false }),
      });
      const data = await res.json();
      if (res.ok) {
          localStorage.setItem("uuid", data.uuid); // ✅ set UUID
        navigate("/chat");
      } else {
        setError(data.error || "Signup failed.");
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
      <h1 className="glow-title">Join AskPro</h1>
      <input
        type="email"
        placeholder="Email"
        value={email}
        onChange={e => setEmail(e.target.value)}
      />
      <input
        type="password"
        placeholder="Password"
        value={pass1}
        onChange={e => setPass1(e.target.value)}
      />
      <input
        type="password"
        placeholder="Confirm Password"
        value={pass2}
        onChange={e => setPass2(e.target.value)}
      />
      <button onClick={handleSignup}>Create Account</button>
      {error && <p className="error">{error}</p>}
      <p className="form-footer">
        Already have an account? <Link to="/login">Login</Link>
      </p>
    </div>
  </div>
);
  
}
