import React from 'react';

interface StatusCardProps {
  title: string;
  value: string;
  unit?: string;
  status?: 'normal' | 'warning' | 'danger';
  icon?: React.ReactNode;
  subtitle?: string;
  progress?: number;
  helperText?: string;
}

export default function StatusCard({ 
  title, 
  value, 
  unit, 
  status = 'normal', 
  icon, 
  subtitle, 
  progress, 
  helperText 
}: StatusCardProps) {
  // Determine color theme based on status
  const getStatusColor = () => {
    switch (status) {
      case 'normal': return 'var(--drdo-cyan)';
      case 'warning': return 'var(--drdo-orange)';
      case 'danger': return 'var(--drdo-red)';
      default: return 'var(--drdo-gray)';
    }
  };

  const isSafetyCard = title === 'Overall Safety';
  
  // Custom shadow properties for iOS
  const glowShadow = status === 'normal'
    ? '0 4px 20px rgba(0, 0, 0, 0.4)'
    : status === 'warning'
      ? '0 4px 20px rgba(255, 159, 10, 0.1)'
      : '0 4px 20px rgba(255, 69, 58, 0.15)';

  const accentColor = getStatusColor();

  return (
    <div className="ios-blur-card" style={{
      display: 'flex',
      flexDirection: 'column',
      justifyContent: 'space-between',
      minHeight: '140px',
      gap: '12px',
      borderLeft: `4px solid ${accentColor}`,
      borderColor: isSafetyCard || status !== 'normal' ? accentColor : 'var(--drdo-border)',
      boxShadow: glowShadow
    }}>
      {/* Card Header */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
        <span style={{ 
          fontSize: '0.72rem', 
          fontWeight: 700, 
          color: 'var(--drdo-text-secondary)', 
          textTransform: 'uppercase', 
          letterSpacing: '0.08em' 
        }}>
          {title}
        </span>
        <div style={{
          color: accentColor,
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center'
        }}>
          {icon}
        </div>
      </div>

      {/* Main Value Body */}
      <div style={{ display: 'flex', flexDirection: 'column', gap: '2px' }}>
        <div style={{ display: 'flex', alignItems: 'baseline', gap: '4px' }}>
          <span style={{ 
            fontSize: '2.2rem', 
            fontWeight: 700, 
            letterSpacing: '-0.02em', 
            color: 'var(--drdo-text-primary)',
            fontFamily: 'var(--font-digital)',
            lineHeight: '1'
          }}>
            {value}
          </span>
          {unit && (
            <span style={{ 
              fontSize: '1rem', 
              fontWeight: 600, 
              color: 'var(--drdo-text-secondary)',
              marginLeft: '2px'
            }}>
              {unit}
            </span>
          )}
        </div>
        {helperText && (
          <div style={{ 
            fontSize: '0.72rem', 
            color: 'var(--drdo-text-tertiary)',
            fontWeight: 500
          }}>
            {helperText}
          </div>
        )}
      </div>

      {/* Progress visual or subtitle */}
      <div>
        {progress !== undefined ? (
          <div style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
            <div style={{ 
              height: '4px', 
              width: '100%', 
              background: 'rgba(255, 255, 255, 0.08)', 
              borderRadius: '9999px',
              overflow: 'hidden'
            }}>
              <div style={{ 
                height: '100%', 
                width: `${Math.min(100, Math.max(0, progress))}%`, 
                background: accentColor,
                borderRadius: '9999px',
                transition: 'width 0.5s ease-in-out'
              }} />
            </div>
            {subtitle && (
              <span style={{ fontSize: '0.7rem', color: 'var(--drdo-text-secondary)', letterSpacing: '0.01em' }}>
                {subtitle}
              </span>
            )}
          </div>
        ) : (
          subtitle && (
            <span style={{ fontSize: '0.7rem', color: 'var(--drdo-text-secondary)', display: 'flex', alignItems: 'center', gap: '6px' }}>
              <span className="beacon-dot" style={{ width: '5px', height: '5px', '--status-color': accentColor } as React.CSSProperties} />
              {subtitle}
            </span>
          )
        )}
      </div>
    </div>
  );
}
