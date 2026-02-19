import { useState, useEffect } from 'react';

interface TimerProps {
  sessionEndTime: string;
  onExpire: () => void;
}

function Timer({ sessionEndTime, onExpire }: TimerProps) {
  const [timeRemaining, setTimeRemaining] = useState<number | null>(null);
  const [isWarning, setIsWarning] = useState(false);

  useEffect(() => {
    const utcTimeString = sessionEndTime.endsWith('Z') ? sessionEndTime : sessionEndTime + 'Z';
    const endTime = new Date(utcTimeString).getTime();

    const updateTimer = () => {
      const now = Date.now();
      const remaining = Math.max(0, Math.floor((endTime - now) / 1000));

      setTimeRemaining(remaining);
      setIsWarning(remaining <= 300);

      if (remaining <= 0) {
        onExpire();
      }
    };

    updateTimer();
    const interval = setInterval(updateTimer, 1000);

    return () => clearInterval(interval);
  }, [sessionEndTime, onExpire]);

  if (timeRemaining === null) return null;

  const minutes = Math.floor(timeRemaining / 60);
  const seconds = timeRemaining % 60;

  const styles = {
    timer: {
      position: 'fixed' as const,
      top: '20px',
      right: '20px',
      background: isWarning ? '#dc3545' : '#333',
      color: '#fff',
      padding: '12px 20px',
      borderRadius: '8px',
      fontSize: '18px',
      fontWeight: 600,
      fontFamily: 'monospace',
      boxShadow: '0 2px 8px rgba(0,0,0,0.15)',
      display: 'flex',
      alignItems: 'center',
      gap: '8px',
      animation: isWarning ? 'pulse 1s infinite' : 'none',
    },
    warning: {
      fontSize: '12px',
      fontWeight: 400,
      opacity: 0.9,
    },
  };

  return (
    <div style={styles.timer}>
      {String(minutes).padStart(2, '0')}:{String(seconds).padStart(2, '0')}
      {isWarning && <span style={styles.warning}>Time running out!</span>}
    </div>
  );
}

export default Timer;
