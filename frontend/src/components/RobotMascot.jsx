import React, { useState } from 'react';

/**
 * RobotMascot component - MADDY AI Study Buddy
 * Features:
 * - Antenna radar pulse animation
 * - Blinking digital visor eyes
 * - Interactive click greetings & winks
 * - Floating hover physics & glowing thruster
 */
export default function RobotMascot({
  size = 'lg',
  speech = null,
  onClick = null,
  className = '',
  style = {}
}) {
  const [isWinking, setIsWinking] = useState(false);
  const [internalSpeech, setInternalSpeech] = useState(speech);
  const isLarge = size === 'lg';
  const width = isLarge ? 88 : 46;
  const height = isLarge ? 88 : 46;

  const handleClick = (e) => {
    setIsWinking(true);
    if (!speech) {
      setInternalSpeech("I'm ready to analyze your documents! ✨");
      setTimeout(() => setInternalSpeech(null), 3000);
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
        ...style
      }}
      title="MADDY — AI Document Assistant (Click to interact!)"
    >
      {/* Speech Bubble */}
      {displaySpeech && (
        <div className={isLarge ? "mascot-speech-bubble" : "floating-bot-bubble"}>
          {displaySpeech}
        </div>
      )}

      {/* Robot Figure */}
      <div className="mascot-figure">
        {/* Glowing Aura Ring behind Maddy */}
        <div
          style={{
            position: 'absolute',
            inset: isLarge ? '-10px' : '-5px',
            borderRadius: '50%',
            background: 'radial-gradient(circle, var(--mascot-glow) 0%, transparent 70%)',
            pointerEvents: 'none',
            zIndex: 0
          }}
        />

        <svg
          width={width}
          height={height}
          viewBox="0 0 100 100"
          fill="none"
          xmlns="http://www.w3.org/2000/svg"
          style={{ position: 'relative', zIndex: 1 }}
        >
          {/* Animated Hover Thruster Shadow */}
          <ellipse
            cx="50"
            cy="94"
            rx="24"
            ry="4.5"
            fill="var(--ac)"
            opacity="0.25"
            filter="blur(3px)"
          />

          {/* Floating Lower Neck / Thruster */}
          <ellipse
            cx="50"
            cy="84"
            rx="13"
            ry="4.5"
            fill="var(--ac)"
            opacity="0.9"
          />
          <path
            d="M44 82L50 87L56 82"
            stroke="var(--ac)"
            strokeWidth="3"
            strokeLinecap="round"
          />

          {/* Antenna Glowing Radar Waves (Animated) */}
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

          {/* Top Antenna */}
          <line
            x1="50"
            y1="22"
            x2="50"
            y2="10"
            stroke="var(--ac)"
            strokeWidth="3.5"
            strokeLinecap="round"
          />
          <circle
            cx="50"
            cy="9"
            r="4.5"
            fill="var(--ac)"
          />
          <circle
            cx="50"
            cy="8"
            r="1.8"
            fill="#FFFFFF"
          />

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

          {/* Left Headphone Ear with Ring */}
          <rect
            x="8"
            y="38"
            width="10"
            height="24"
            rx="5"
            fill="var(--ac)"
          />
          <circle
            cx="13"
            cy="50"
            r="3"
            fill="#FFFFFF"
            opacity="0.85"
          />

          {/* Right Headphone Ear with Ring */}
          <rect
            x="82"
            y="38"
            width="10"
            height="24"
            rx="5"
            fill="var(--ac)"
          />
          <circle
            cx="87"
            cy="50"
            r="3"
            fill="#FFFFFF"
            opacity="0.85"
          />

          {/* Dark Digital Visor Screen */}
          <rect
            x="26"
            y="32"
            width="48"
            height="36"
            rx="14"
            fill="var(--mascot-visor)"
          />

          {/* Left Eye (with blink/wink) */}
          <rect
            x="34"
            y={isWinking ? "48" : "42"}
            width="8"
            height={isWinking ? "3" : "14"}
            rx={isWinking ? "1.5" : "4"}
            fill="var(--mascot-eye)"
            className={!isWinking ? "maddy-eye-blink" : ""}
          />

          {/* Right Eye */}
          <rect
            x="58"
            y="42"
            width="8"
            height="14"
            rx="4"
            fill="var(--mascot-eye)"
            className="maddy-eye-blink"
          />

          {/* Highlights inside eyes */}
          {!isWinking && (
            <>
              <circle cx="36" cy="44.5" r="1.5" fill="#FFFFFF" />
              <circle cx="60" cy="44.5" r="1.5" fill="#FFFFFF" />
            </>
          )}

          {/* Friendly Smile Arc */}
          <path
            d="M45 59C47.5 61.5 52.5 61.5 55 59"
            stroke="var(--mascot-eye)"
            strokeWidth="2.2"
            strokeLinecap="round"
          />

          {/* Cute Pink/Accent Cheek Blush */}
          <circle cx="31" cy="57" r="2.2" fill="var(--ac)" opacity="0.5" />
          <circle cx="69" cy="57" r="2.2" fill="var(--ac)" opacity="0.5" />
        </svg>
      </div>
    </div>
  );
}
