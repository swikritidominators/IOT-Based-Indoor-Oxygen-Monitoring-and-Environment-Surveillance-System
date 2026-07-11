

interface PredictionChartProps {
  title: string;
  history: number[];
  projection: number[];
  min?: number;
  max?: number;
  color?: string;
  unit?: string;
  summaryText?: string;
}

export default function PredictionChart({ 
  title, 
  history = [], 
  projection = [], 
  min = 0, 
  max = 100, 
  color = 'var(--drdo-cyan)', 
  unit = '%', 
  summaryText 
}: PredictionChartProps) {
  const width = 500;
  const height = 125;
  const paddingLeft = 38;
  const paddingRight = 12;
  const paddingTop = 12;
  const paddingBottom = 12;

  const totalPoints = history.length + projection.length;
  if (totalPoints < 2) return null;

  // Calculate coordinates for history and projection series
  const getCoordinates = (series: number[], startIndex: number) => {
    return series.map((val, idx) => {
      const globalIdx = startIndex + idx;
      const x = paddingLeft + (globalIdx / (totalPoints - 1)) * (width - paddingLeft - paddingRight);
      
      const range = max - min || 1;
      const clampedVal = Math.max(min, Math.min(max, val));
      const y = height - paddingBottom - ((clampedVal - min) / range) * (height - paddingTop - paddingBottom);
      
      return { x, y };
    });
  };

  const historyCoords = getCoordinates(history, 0);
  const projectionCoords = getCoordinates(projection, history.length - 1);

  // Helper to generate SVG path string
  const getPathString = (coords: { x: number; y: number }[]) => {
    if (coords.length === 0) return '';
    return coords.reduce((path, coord, idx) => {
      return idx === 0 ? `M ${coord.x} ${coord.y}` : `${path} L ${coord.x} ${coord.y}`;
    }, '');
  };

  const historyPath = getPathString(historyCoords);
  const projectionPath = getPathString(projectionCoords);

  // Generate Confidence Interval shaded region coordinates (funnel expanding towards the future)
  const getConfidenceAreaPath = () => {
    if (projectionCoords.length === 0) return '';
    const upperPoints: { x: number; y: number }[] = [];
    const lowerPoints: { x: number; y: number }[] = [];
    
    projectionCoords.forEach((coord, idx) => {
      const factor = idx / (projectionCoords.length - 1);
      const dy = 14 * factor; // grows from 0px to 14px variance at +10m
      
      upperPoints.push({ x: coord.x, y: coord.y - dy });
      // unshift to reverse order and create a closed loop path
      lowerPoints.unshift({ x: coord.x, y: coord.y + dy });
    });
    
    const points = [...upperPoints, ...lowerPoints];
    return points.reduce((path, coord, idx) => {
      return idx === 0 ? `M ${coord.x} ${coord.y}` : `${path} L ${coord.x} ${coord.y}`;
    }, '') + ' Z';
  };

  const confidencePath = getConfidenceAreaPath();

  // Position of the "Now" divider line
  const nowX = historyCoords.length > 0 
    ? historyCoords[historyCoords.length - 1].x 
    : paddingLeft;

  const gradId = `pred-grad-${title.replace(/\s+/g, '-').toLowerCase()}`;
  const areaGradId = `pred-area-grad-${title.replace(/\s+/g, '-').toLowerCase()}`;

  return (
    <div className="ios-blur-card" style={{
      display: 'flex',
      flexDirection: 'column',
      gap: '10px',
      flex: 1
    }}>
      {/* Header Info */}
      <div style={{ display: 'flex', flexDirection: 'column', gap: '4px' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <span style={{ 
            fontSize: '0.72rem', 
            fontWeight: 700, 
            color: 'var(--drdo-text-secondary)', 
            textTransform: 'uppercase', 
            letterSpacing: '0.08em' 
          }}>
            {title}
          </span>
          <span style={{ 
            fontSize: '0.68rem', 
            color: '#070c15', 
            background: 'var(--drdo-cyan)',
            padding: '2px 10px',
            borderRadius: '2px',
            fontWeight: 700,
            letterSpacing: '0.04em',
            textTransform: 'uppercase',
            boxShadow: '0 2px 8px rgba(0, 240, 255, 0.25)'
          }}>
            DEBEL Forecast Model
          </span>
        </div>
        {summaryText && (
          <div style={{ fontSize: '0.74rem', color: 'var(--drdo-text-secondary)', fontWeight: 500 }}>
            {summaryText}
          </div>
        )}
      </div>

      {/* SVG Graph */}
      <div style={{ position: 'relative', width: '100%', height: `${height}px` }}>
        <svg viewBox={`0 0 ${width} ${height}`} width="100%" height="100%" style={{ overflow: 'visible' }}>
          <defs>
            <linearGradient id={gradId} x1="0" y1="0" x2="1" y2="0">
              <stop offset="0%" stopColor={color} stopOpacity="0.7" />
              <stop offset="100%" stopColor={color} stopOpacity="1" />
            </linearGradient>
            <linearGradient id={areaGradId} x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor={color} stopOpacity="0.15" />
              <stop offset="100%" stopColor={color} stopOpacity="0.0" />
            </linearGradient>
          </defs>

          {/* Grid lines */}
          {[1, 2].map((i) => {
            const y = paddingTop + (i / 3) * (height - paddingTop - paddingBottom);
            return (
              <line 
                key={i} 
                x1={paddingLeft} 
                y1={y} 
                x2={width - paddingRight} 
                y2={y} 
                stroke="var(--drdo-grid-line)" 
                strokeWidth="0.8" 
                strokeDasharray="4,4"
              />
            );
          })}

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

          {/* Confidence Band Envelope (Widening uncertainty funnel) */}
          {confidencePath && (
            <path 
              d={confidencePath} 
              fill={color} 
              opacity="0.05" 
              stroke="var(--drdo-separator)" 
              strokeWidth="0.5" 
              strokeDasharray="2,2" 
            />
          )}

          {/* Historical Area Under Curve */}
          {historyCoords.length > 0 && (
            <path 
              d={`${historyPath} L ${nowX} ${height - paddingBottom} L ${historyCoords[0].x} ${height - paddingBottom} Z`} 
              fill={`url(#${areaGradId})`} 
            />
          )}

          {/* Historical Path (Solid) */}
          {historyPath && (
            <path 
              d={historyPath} 
              fill="none" 
              stroke={`url(#${gradId})`} 
              strokeWidth="2" 
              strokeLinecap="round" 
              strokeLinejoin="round" 
              filter={`drop-shadow(0 0 3px ${color}40)`}
            />
          )}

          {/* Projected Path (Dashed) */}
          {projectionPath && (
            <path 
              d={projectionPath} 
              fill="none" 
              stroke={color} 
              strokeWidth="1.8" 
              strokeLinecap="round" 
              strokeLinejoin="round" 
              strokeDasharray="4,4"
              opacity="0.8"
            />
          )}

          {/* "NOW" Vertical Divider Line */}
          <line 
            x1={nowX} 
            y1={paddingTop - 4} 
            x2={nowX} 
            y2={height - paddingBottom} 
            stroke="var(--drdo-text-tertiary)" 
            strokeWidth="1.2" 
            strokeDasharray="3,3"
          />

          {/* Labels inside graph */}
          <text x={nowX - 6} y={height - paddingBottom - 8} fill="var(--drdo-text-secondary)" fontSize="8" fontWeight="700" textAnchor="end">
            NOW
          </text>
          <text x={width - paddingRight} y={height - paddingBottom - 8} fill="var(--drdo-text-tertiary)" fontSize="8" fontWeight="700" textAnchor="end">
            +60 MIN
          </text>

          {/* Indicator Dot at current moment */}
          {historyCoords.length > 0 && (
            <circle 
              cx={nowX} 
              cy={historyCoords[historyCoords.length - 1].y} 
              r="4" 
              fill="#ffffff" 
              stroke={color} 
              strokeWidth="2"
            />
          )}

          {/* Indicator Dot at 10m end */}
          {projectionCoords.length > 0 && (
            <circle 
              cx={projectionCoords[projectionCoords.length - 1].x} 
              cy={projectionCoords[projectionCoords.length - 1].y} 
              r="3" 
              fill={color} 
              stroke="#ffffff" 
              strokeWidth="1"
            />
          )}
        </svg>
      </div>

      {/* Footer Scale Details */}
      <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.62rem', color: 'var(--drdo-text-tertiary)', fontWeight: 600 }}>
        <span>PAST 15M (ACTUAL)</span>
        <span>FUTURE 10M (CONFIDENCE MARGIN: ±0.5%)</span>
      </div>
    </div>
  );
}
