import React, { useEffect, useRef } from "react";
import { useNavigate } from "react-router-dom";
import Typed from "typed.js";
import Beams from './Beams';

export default function Landing() {
  const nav = useNavigate();
  const typedRef = useRef(null);

  useEffect(() => {
    const typed = new Typed(typedRef.current, {
      strings: [
        "Chat with your content.",
        "Upload documents. Ask questions.",
        "Powered by GPT-4 & RAG.",
        "Your AI assistant, reimagined.",
      ],
      typeSpeed: 40,
      backSpeed: 20,
      loop: true,
    });

    return () => typed.destroy();
  }, []);

  return (
    <div className="landing">
      <div className="iridescence">
        <div style={{ width: '100%', height: '100vh', position: 'relative' }}>
          <Beams
            beamWidth={1.1}
            beamHeight={30}
            beamNumber={50}
            lightColor='#5266ff'
            speed={10}
            noiseIntensity={1.75}
            scale={0.2}
            rotation={66}
          />
        </div>
      </div>

      <div className="glass-card">
        <h1 className="glow-title">AskPro<span>.AI</span></h1>
        <p ref={typedRef} className="typing" />
        <div className="btn-group">
          <button onClick={() => nav("/login")}>Login</button>
          <button className="secondary" onClick={() => nav("/signup")}>Sign Up</button>
        </div>
      </div>
    </div>
  );
}
