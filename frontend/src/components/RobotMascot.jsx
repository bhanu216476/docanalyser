import React, { useState, useEffect } from 'react';

/**
 * Enhanced RobotMascot component - MADDY AI Companion
 * Modes:
 * - 'hero': Interactive waving mascot for the empty/welcome hero state.
 * - 'thinking': Animated mascot actively researching and thinking for chat generation.
 * - 'scanning': Animated laser-scanning mascot for document uploads.
 * - 'idle': Compact, friendly floating mascot for avatar bubbles and corner button.
 */
export default function RobotMascot({
  size = 'lg',
  mode = 'idle',
  speech = null,
  onClick = null,
  className = '',
  style = {}
}) {
  const [isWinking, setIsWinking] = useState(false);
  const [internalSpeech, setInternalSpeech] = useState(speech);
  const [thoughtIcon, setThoughtIcon] = useState('💡');

  const isHero = mode === 'hero' || size === 'hero';
  const isThinking = mode === 'thinking';
  const isScanning = mode === 'scanning';

  const width = isHero ? 96 : size === 'lg' ? 76 : size === 'md' ? 54 : 42;
  const height = isHero ? 96 : size === 'lg' ? 76 : size === 'md' ? 54 : 42;

  // Cycle thinking icons while generating response to avoid user boredom
  useEffect(() => {
    if (!isThinking) return;
    const icons = ['📄', '🔍', '💡', '✨', '⚙️', '📚'];
    let idx = 0;
    const interval = setInterval(() => {
      idx = (idx + 1) % icons.length;
      setThoughtIcon(icons[idx]);
    }, 1200);
    return () => clearInterval(interval);
  }, [isThinking]);

  const handleClick = (e) => {
    setIsWinking(true);
    if (!speech) {
      const friendlyPhrases = [
        "I'm ready to explore your documents! ✨",
        "Ask me anything or request a summary! 📚",
        "I love discovering insights for you! 💕",
        "Let's dive into your knowledge base! 🚀"
      ];
      const randomPhrase = friendlyPhrases[Math.floor(Math.random() * friendlyPhrases.length)];
      setInternalSpeech(randomPhrase);
      setTimeout(() => setInternalSpeech(null), 3200);
    }
    setTimeout(() => setIsWinking(false), 900);
    if (onClick) onClick(e);
  };

  const displaySpeech = speech !== null ? speech : internalSpeech;

  return (
    <div
      onClick={handleClick}
      className={`mascot-container ${className}`}
      style={{
        cursor: 'pointer',
        userSelect: 'none',
        display: 'inline-flex',
        flexDirection: 'column',
        alignItems: 'center',
        position: 'relative',
        ...style
      }}
      title="MADDY — AI Document Companion (Click to interact!)"
    >
      {/* Speech Bubble / Thought Bubble */}
      {displaySpeech && (
        <div className={isHero ? "mascot-speech-bubble" : "floating-bot-bubble"}>
          {displaySpeech}
        </div>
      )}

      {/* Floating Thinking Bubble when generating response */}
      {isThinking && (
        <div
          style={{
            position: 'absolute',
            top: '-24px',
            right: '-16px',
            background: 'var(--s1)',
            border: '1.5px solid var(--ac)',
            borderRadius: '50%',
            width: '26px',
            height: '26px',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            fontSize: '13px',
            boxShadow: '0 4px 12px var(--mascot-glow)',
            animation: 'mascotBubbleFloat 2s ease-in-out infinite',
            zIndex: 10
          }}
          title="Maddy is processing"
        >
          {thoughtIcon}
        </div>
      )}

      {/* Robot Figure */}
      <div className="mascot-figure" style={{ position: 'relative' }}>
        {/* Glowing Aura Ring */}
        <div
          className={isHero || isThinking ? "maddy-aura-pulse" : ""}
          style={{
            position: 'absolute',
            inset: isHero ? '-14px' : '-6px',
            borderRadius: '50%',
            background: 'radial-gradient(circle, var(--mascot-glow) 0%, transparent 70%)',
            pointerEvents: 'none',
            zIndex: 0
          }}
        />

        {/* Orbiting Particle for Thinking Mode */}
        {isThinking && <div className="maddy-orbit-particle" />}

        <svg
          width={width}
          height={height}
          viewBox="0 0 100 100"
          fill="none"
          xmlns="http://www.w3.org/2000/svg"
          style={{ position: 'relative', zIndex: 1, overflow: 'visible' }}
        >
          {/* Animated Hover Thruster Shadow */}
          <ellipse
            cx="50"
            cy="95"
            rx="24"
            ry="4.5"
            fill="var(--ac)"
            opacity="0.3"
            filter="blur(3px)"
          />

          {/* Floating Thruster Base */}
          <ellipse
            cx="50"
            cy="84"
            rx="13"
            ry="4.5"
            fill="var(--ac)"
            opacity="0.9"
          />
          <path
            d="M44 82L50 88L56 82"
            stroke="var(--ac)"
            strokeWidth="3"
            strokeLinecap="round"
          />

          {/* Antenna Glowing Waves */}
          <circle
            cx="50"
            cy="9"
            r="8"
            stroke="var(--ac)"
            strokeWidth="1.5"
            opacity="0.4"
            className="maddy-antenna-wave"
          />
          <circle
            cx="50"
            cy="9"
            r="12"
            stroke="var(--ac)"
            strokeWidth="1"
            opacity="0.2"
            className="maddy-antenna-wave-outer"
          />

          {/* Top Antenna Pole & Glowing Bulb */}
          <line
            x1="50"
            y1="22"
            x2="50"
            y2="10"
            stroke="var(--ac)"
            strokeWidth="3.5"
            strokeLinecap="round"
          />
          <circle cx="50" cy="9" r="4.5" fill="var(--ac)" />
          <circle cx="50" cy="8" r="1.8" fill="#FFFFFF" />

          {/* Head Base */}
          <rect
            x="18"
            y="22"
            width="64"
            height="58"
            rx="26"
            fill="var(--mascot-body)"
            stroke="var(--bd)"
            strokeWidth="2.5"
          />

          {/* Left Headphone Ear */}
          <rect x="8" y="38" width="10" height="24" rx="5" fill="var(--ac)" />
          <circle cx="13" cy="50" r="3" fill="#FFFFFF" opacity="0.85" />

          {/* Right Headphone Ear */}
          <rect x="82" y="38" width="10" height="24" rx="5" fill="var(--ac)" />
          <circle cx="87" cy="50" r="3" fill="#FFFFFF" opacity="0.85" />

          {/* Waving Arm on Right (Active in Hero/Waving mode) */}
          {isHero && (
            <g className="maddy-waving-arm">
              <path
                d="M84 46C91 42 95 32 94 24"
                stroke="var(--ac)"
                strokeWidth="4"
                strokeLinecap="round"
              />
              <circle cx="94" cy="23" r="4.5" fill="var(--ac)" />
              <circle cx="94" cy="22" r="1.8" fill="#FFFFFF" />
              {/* Cute Wave Sparkle */}
              <text x="98" y="18" fontSize="11" fill="var(--ac)">✨</text>
            </g>
          )}

          {/* Dark Digital Visor Screen */}
          <rect
            x="26"
            y="32"
            width="48"
            height="36"
            rx="14"
            fill="var(--mascot-visor)"
          />

          {/* Eyes Group (Scanning in Thinking mode, Blinking in Idle/Hero mode) */}
          <g className={isThinking ? "maddy-eyes-scanning" : ""}>
            {/* Left Eye */}
            <rect
              x="34"
              y={isWinking ? "48" : "42"}
              width="8"
              height={isWinking ? "3" : "14"}
              rx={isWinking ? "1.5" : "4"}
              fill="var(--mascot-eye)"
              className={!isWinking && !isThinking ? "maddy-eye-blink" : ""}
            />

            {/* Right Eye */}
            <rect
              x="58"
              y="42"
              width="8"
              height="14"
              rx="4"
              fill="var(--mascot-eye)"
              className={!isThinking ? "maddy-eye-blink" : ""}
            />

            {/* Sparkle Highlights inside Eyes */}
            {!isWinking && (
              <>
                <circle cx="36" cy="44.5" r="1.5" fill="#FFFFFF" />
                <circle cx="60" cy="44.5" r="1.5" fill="#FFFFFF" />
              </>
            )}

            {/* Cute Feminine Eyelash Accents */}
            <path
              d="M33 41L30 38M43 41L45 38"
              stroke="var(--mascot-eye)"
              strokeWidth="1.2"
              strokeLinecap="round"
              opacity="0.8"
            />
            <path
              d="M57 41L55 38M67 41L69 38"
              stroke="var(--mascot-eye)"
              strokeWidth="1.2"
              strokeLinecap="round"
              opacity="0.8"
            />
          </g>

          {/* Friendly Smile Arc */}
          <path
            d="M45 59C47.5 61.5 52.5 61.5 55 59"
            stroke="var(--mascot-eye)"
            strokeWidth="2.2"
            strokeLinecap="round"
          />

          {/* Cute Pink/Accent Cheek Blush */}
          <circle cx="31" cy="57" r="2.5" fill="#F472B6" opacity="0.65" />
          <circle cx="69" cy="57" r="2.5" fill="#F472B6" opacity="0.65" />

          {/* Scanning Laser Beam in Scanning Mode */}
          {isScanning && (
            <line
              x1="20"
              y1="90"
              x2="80"
              y2="90"
              stroke="#38BDF8"
              strokeWidth="2.5"
              strokeLinecap="round"
              filter="blur(1px)"
            />
          )}
        </svg>
      </div>
    </div>
  );
}
