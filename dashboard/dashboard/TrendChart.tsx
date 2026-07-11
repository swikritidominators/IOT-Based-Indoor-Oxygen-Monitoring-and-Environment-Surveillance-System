import { useState, useMemo } from 'react';

interface TrendChartProps {
  title: string;
  subtitle?: string;
  data: number[];
  min?: number;
  max?: number;
  color?: string;
  unit?: string;
  currentValue?: string;
  safeMin?: number;
  safeMax?: number;
}

export default function TrendChart({ 
  title, 
  subtitle, 
  data = [], 
  min = 0, 
  max = 100, 
  color = 'var(--drdo-cyan)', 
  unit = '', 
  currentValue, 
  safeMin, 
  safeMax 
}: TrendChartProps) {
  const [timeRange, setTimeRange] = useState('24h');
  
  const width = 500;
  const height = 125;
  const paddingLeft = 38;
  const paddingRight = 12;
  const paddingTop = 12;
  const paddingBottom = 12;

  // Zoom filter data dynamically based on time-range selector
  const displayData = useMemo(() => {
    if (timeRange === '1h') return data.slice(-5);
    if (timeRange === '6h') return data.slice(-10);
    return data;
  }, [data, timeRange]);

  // Generate SVG path coordinates
  const getCoordinates = () => {
    if (displayData.length < 2) return [];
    
    return displayData.map((val, idx) => {
      const x = paddingLeft + (idx / (displayData.length - 1)) * (width - paddingLeft - paddingRight);
      
      const range = max - min || 1;
      const clampedVal = Math.max(min, Math.min(max, val));
      const y = height - paddingBottom - ((clampedVal - min) / range) * (height - paddingTop - paddingBottom);
      
      return { x, y };
    });
  };

  const coords = getCoordinates();

  // Create path command for the line chart
  const getLinePath = () => {
    if (coords.length === 0) return '';
    return coords.reduce((path, coord, idx) => {
      return idx === 0 ? `M ${coord.x} ${coord.y}` : `${path} L ${coord.x} ${coord.y}`;
    }, '');
  };

  // Create path command for the filled area underneath the line
  const getAreaPath = () => {
    if (coords.length === 0) return '';
    const linePath = getLinePath();
    const bottomY = height - paddingBottom;
    const firstX = coords[0].x;
    const lastX = coords[coords.length - 1].x;
    return `${linePath} L ${lastX} ${bottomY} L ${firstX} ${bottomY} Z`;
  };

  const linePath = getLinePath();
  const areaPath = getAreaPath();
  const latestCoord = coords[coords.length - 1];

  // Draw grid lines
  const gridLines = [];
  const gridCount = 2;
  for (let i = 0; i <= gridCount; i++) {
    const y = paddingTop + (i / gridCount) * (height - paddingTop - paddingBottom);
    gridLines.push(y);
  }

  // Draw shaded safe zone band if safe bounds are provided
  let safeZoneRect = null;
  if (safeMin !== undefined && safeMax !== undefined) {
    const range = max - min || 1;
    const ySafeMin = height - paddingBottom - ((safeMin - min) / range) * (height - paddingTop - paddingBottom);
    const ySafeMax = height - paddingBottom - ((safeMax - min) / range) * (height - paddingTop - paddingBottom);
    safeZoneRect = {
      y: Math.min(ySafeMin, ySafeMax),
      height: Math.abs(ySafeMin - ySafeMax)
    };
  }

  const gradId = `grad-${title.replace(/\s+/g, '-').toLowerCase()}`;
  const areaGradId = `area-grad-${title.replace(/\s+/g, '-').toLowerCase()}`;

  return (
    <div className="ios-blur-card" style={{
      display: 'flex',
      flexDirection: 'column',
      gap: '10px',
      flex: 1
    }}>
      {/* Header Info */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', flexWrap: 'wrap', gap: '8px' }}>
        <div style={{ display: 'flex', flexDirection: 'column' }}>
          <span style={{ 
            fontSize: '0.72rem', 
            fontWeight: 700, 
            color: 'var(--drdo-text-secondary)', 
            textTransform: 'uppercase', 
            letterSpacing: '0.08em' 
          }}>
            {title}
          </span>
          {subtitle && (
            <span style={{ fontSize: '0.62rem', color: 'var(--drdo-text-tertiary)', marginTop: '2px', fontWeight: 500 }}>
              {subtitle}
            </span>
          )}
        </div>
        
        <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
          {/* Time Range Selector */}
          <div className="ios-segmented-control" style={{ padding: '1.5px', borderRadius: '4px' }}>
            {['1h', '6h', '24h'].map(range => (
              <button
                key={range}
                onClick={() => setTimeRange(range)}
                className={`ios-segmented-item ${timeRange === range ? 'active' : ''}`}
                style={{
                  padding: '2px 8px',
                  fontSize: '0.68rem',
                  borderRadius: '3px'
                }}
              >
                {range}
              </button>
            ))}
          </div>

          {/* Current Reading */}
          <div style={{ display: 'flex', alignItems: 'baseline', gap: '1px' }}>
            <span style={{ 
              fontSize: '1.3rem', 
              fontWeight: 700, 
              color: 'var(--drdo-text-primary)',
              fontFamily: 'var(--font-digital)',
              textShadow: `0 0 10px ${color}30`
            }}>
              {currentValue !== undefined ? currentValue : (displayData[displayData.length - 1]?.toFixed(1) || '--')}
            </span>
            <span style={{ fontSize: '0.75rem', color: 'var(--drdo-text-secondary)', fontWeight: 600, marginLeft: '2px' }}>
              {unit}
            </span>
          </div>
        </div>
      </div>

      {/* SVG Sparkline Graph */}
      <div style={{ position: 'relative', width: '100%', height: `${height}px` }}>
        <svg viewBox={`0 0 ${width} ${height}`} width="100%" height="100%" style={{ overflow: 'visible' }}>
          <defs>
            <linearGradient id={gradId} x1="0" y1="0" x2="1" y2="0">
              <stop offset="0%" stopColor={color} stopOpacity="0.6" />
              <stop offset="100%" stopColor={color} stopOpacity="1" />
            </linearGradient>
            
            <linearGradient id={areaGradId} x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor={color} stopOpacity="0.15" />
              <stop offset="100%" stopColor={color} stopOpacity="0.00" />
            </linearGradient>
          </defs>

          {/* Shaded Safe Zone Band */}
          {safeZoneRect && (
            <rect 
              x={paddingLeft} 
              y={safeZoneRect.y} 
              width={width - paddingLeft - paddingRight} 
              height={safeZoneRect.height} 
              fill={color} 
              opacity="0.03" 
            />
          )}

          {/* Grid lines */}
          {gridLines.map((y, idx) => (
            <line 
              key={idx} 
              x1={paddingLeft} 
              y1={y} 
              x2={width - paddingRight} 
              y2={y} 
              stroke="var(--drdo-grid-line)" 
              strokeWidth="0.8" 
              strokeDasharray="4,4"
            />
          ))}

          {/* Y-Axis Line */}
          <line 
            x1={paddingLeft} 
            y1={paddingTop - 4} 
            x2={paddingLeft} 
            y2={height - paddingBottom} 
            stroke="var(--drdo-separator)" 
            strokeWidth="1" 
          />

          {/* Y-Axis Labels */}
          <text x={paddingLeft - 8} y={paddingTop + 3} fill="var(--drdo-text-tertiary)" fontSize="8" fontWeight="700" fontFamily="var(--font-digital)" textAnchor="end">
            {max}{unit}
          </text>
          <text x={paddingLeft - 8} y={(paddingTop + height - paddingBottom) / 2 + 3} fill="var(--drdo-text-tertiary)" fontSize="8" fontWeight="700" fontFamily="var(--font-digital)" textAnchor="end">
            {((max + min) / 2).toFixed(0)}{unit}
          </text>
          <text x={paddingLeft - 8} y={height - paddingBottom + 3} fill="var(--drdo-text-tertiary)" fontSize="8" fontWeight="700" fontFamily="var(--font-digital)" textAnchor="end">
            {min}{unit}
          </text>

          {/* Area under the line */}
          {areaPath && (
            <path d={areaPath} fill={`url(#${areaGradId})`} />
          )}

          {/* Core trend line */}
          {linePath && (
            <path 
              d={linePath} 
              fill="none" 
              stroke={`url(#${gradId})`} 
              strokeWidth="2" 
              strokeLinecap="round" 
              strokeLinejoin="round" 
              filter={`drop-shadow(0 0 3px ${color}50)`}
            />
          )}

          {/* Pulsing indicator at the latest node */}
          {latestCoord && (
            <>
              <circle 
                cx={latestCoord.x} 
                cy={latestCoord.y} 
                r="6" 
                fill={color} 
                opacity="0.4"
              >
                <animate 
                  attributeName="r" 
                  values="4;9;4" 
                  dur="2s" 
                  repeatCount="indefinite" 
                />
                <animate 
                  attributeName="opacity" 
                  values="0.5;0;0.5" 
                  dur="2s" 
                  repeatCount="indefinite" 
                />
              </circle>
              <circle 
                cx={latestCoord.x} 
                cy={latestCoord.y} 
                r="3" 
                fill={color} 
                stroke="#ffffff" 
                strokeWidth="1"
              />
            </>
          )}
        </svg>
      </div>
    </div>
  );
}
