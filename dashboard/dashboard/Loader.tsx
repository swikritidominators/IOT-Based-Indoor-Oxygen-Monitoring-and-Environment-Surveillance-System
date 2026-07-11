import { useEffect, useState } from 'react';

interface LoaderProps {
  onComplete: () => void;
}

export default function Loader({ onComplete }: LoaderProps) {
  const [progress, setProgress] = useState(0);
  const [statusText, setStatusText] = useState('INITIALIZING SECURE LINK...');
  const [fadeOut, setFadeOut] = useState(false);

  useEffect(() => {
    // DRDO Tactical Loading Status messages
    const getStatusMessage = (p: number) => {
      if (p < 20) return 'ESTABLISHING SECURE telemetry LINK...';
      if (p < 40) return 'CALIBRATING DEBEL ELECTROCHEMICAL SENSORS...';
      if (p < 65) return 'SYNCING CHAMBER ATMOSPHERE HISTORY GRID...';
      if (p < 85) return 'VERIFYING O2 ALARM THRESHOLD LIMITS...';
      return 'ALL LIFE SUPPORT SYSTEMS NOMINAL';
    };

    const interval = setInterval(() => {
      setProgress(prev => {
        const increment = Math.floor(Math.random() * 5) + 8; // fast, high-performance loader (8% to 12%)
        const next = Math.min(100, prev + increment);
        setStatusText(getStatusMessage(next));
        
        if (next === 100) {
          clearInterval(interval);
          setTimeout(() => {
            setFadeOut(true);
            setTimeout(() => {
              onComplete();
            }, 400);
          }, 300);
        }
        return next;
      });
    }, 100);

    return () => clearInterval(interval);
  }, [onComplete]);

  return (
    <div className={`loader-overlay ${fadeOut ? 'fade-out' : ''}`}>
      <div className="loader-container">
        <div className="loader-logo-wrapper">
          <div className="loader-logo-ring"></div>
          <div className="loader-logo-icon">
            <svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
              <circle cx="12" cy="12" r="10" />
              <path d="M12 2a15.3 15.3 0 0 1 4 10 15.3 15.3 0 0 1-4 10 15.3 15.3 0 0 1-4-10 15.3 15.3 0 0 1 4-10z" />
            </svg>
          </div>
        </div>
        
        <h1 className="loader-title">O₂ SENTINEL</h1>
        
        <div className="loader-progress-track">
          <div className="loader-progress-bar" style={{ width: `${progress}%` }}></div>
        </div>
        
        <div className="loader-status-text">
          {statusText} <span style={{ fontWeight: 700, color: 'var(--drdo-cyan)' }}>{progress}%</span>
        </div>
      </div>
    </div>
  );
}
