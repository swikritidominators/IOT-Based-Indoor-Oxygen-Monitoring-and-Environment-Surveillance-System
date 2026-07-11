import { useState, useEffect, useMemo } from 'react';
// import {
//   AreaChart,
//   Area,
//   LineChart,
//   Line,
//   XAxis,
//   YAxis,
//   CartesianGrid,
//   Tooltip,
//   ReferenceLine,
//   ResponsiveContainer
// } from 'recharts';
import Loader from './dashboard/components/Loader';
import {
  getSensorData,
  getDevices,
  getSensorHistory,
  getAlerts,
  getAlertHistory,
  acknowledgeAlert,
  getRecommendations,
  getSensorPredictions,
  getSystemStats,
  getSystemHealth,
  getSystemEvents,
} from "./services/api";

// Simple sparkline helper component
function Sparkline({ data, color, min, max }: { data: number[]; color: string; min: number; max: number }) {
  if (!data || data.length < 2) return null;
  const width = 80;
  const height = 30;
  const range = max - min || 1;
  const coords = data.map((val, idx) => {
    const x = (idx / (data.length - 1)) * width;
    const clamped = Math.max(min, Math.min(max, val));
    const y = height - ((clamped - min) / range) * height;
    return { x, y };
  });
  
  const path = coords.reduce((acc, coord, idx) => {
    return idx === 0 ? `M ${coord.x} ${coord.y}` : `${acc} L ${coord.x} ${coord.y}`;
  }, "");

  return (
    <svg width={width} height={height} viewBox={`0 0 ${width} ${height}`} className="chart-svg">
      <path d={path} fill="none" stroke={color} strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}

function getPercent(val: number, min: number, max: number) {
  const pct = ((val - min) / (max - min)) * 100;
  return Math.min(100, Math.max(0, pct));
}

const formatTimeSafe = (timestamp: any) => {
  if (!timestamp) return '--:--:--';
  const d = typeof timestamp === 'object' && timestamp instanceof Date ? timestamp : new Date(timestamp);
  return isNaN(d.getTime()) ? '--:--:--' : d.toLocaleTimeString();
};

const formatTime2DigitSafe = (timestamp: any) => {
  if (!timestamp) return '--:--';
  const d = typeof timestamp === 'object' && timestamp instanceof Date ? timestamp : new Date(timestamp);
  return isNaN(d.getTime()) ? '--:--' : d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
};

// const CustomTooltip = ({ active, payload }: any) => {
//   if (active && payload && payload.length) {
//     const data = payload[0].payload;
//     const value = data.oxygen !== null ? data.oxygen : data.predicted;
//     let labelText = "Historical Reading";
//     if (data.time === "+5") {
//       labelText = "Prediction (+5 min)";
//     } else if (data.time === "+10") {
//       labelText = "Prediction (+10 min)";
//     }
//     return (
//       <div 
//         className="glass-card" 
//         style={{ 
//           padding: '10px 14px', 
//           borderRadius: '12px', 
//           border: '1px solid rgba(255,255,255,0.08)', 
//           background: 'rgba(10, 10, 12, 0.95)', 
//           boxShadow: '0 8px 32px rgba(0,0,0,0.5)',
//           transform: 'none',
//           transition: 'none'
//         }}
//       >
//         <p style={{ margin: 0, fontSize: '0.72rem', color: 'var(--text-secondary)', fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.04em' }}>
//           {labelText}
//         </p>
//         <p style={{ margin: '4px 0 0 0', fontSize: '1.2rem', fontWeight: 800, fontFamily: 'var(--font-mono)', color: '#22D3EE', letterSpacing: '-0.02em' }}>
//           {value !== null && value !== undefined ? `${value.toFixed(2)}%` : '--'}
//         </p>
//       </div>
//     );
//   }
//   return null;
// };


interface Alert {
  id: number;
  message: string;
  severity: string;
  timestamp: string;
  acknowledged?: number | boolean;
  status?: string;
}


interface Recommendation {
  text: string;
  priority: string;
}

interface StatDetails {
  min: number;
  avg: number;
  max: number;
}

interface SystemStats {
  telemetry: {
    oxygen: StatDetails;
    temperature: StatDetails;
    humidity: StatDetails;
  };
  alerts: {
    total: number;
    active: number;
    resolved: number;
    acknowledged: number;
  };
}

interface SystemHealth {
  status: string;
  memory: {
    heapUsed: number;
  };
  worker?: {
    active: boolean;
  };
}

interface SystemEvent {
  timestamp: string;
  event: string;
}

export default function App() {
  const [loading, setLoading] = useState(true);
  const [systemTime, setSystemTime] = useState<Date>(new Date());
  
  // Navigation and Theme States
  const [activeNav, setActiveNav] = useState('Dashboard');
  const [theme, setTheme] = useState<'dark' | 'light'>('dark');
  
  // Interactive trends chart tabs
  const [activeTrendTab, setActiveTrendTab] = useState<'oxygen' | 'temperature' | 'humidity'>('oxygen');
  const [timeFilter, setTimeFilter] = useState<'5m' | '10m'>('10m');
  // const [predictionChartType, setPredictionChartType] = useState<'area' | 'linear'>('area');
  
  // Real-time sensor state variables
  const [oxygen, setOxygen] = useState(0);
  const [temperature, setTemperature] = useState(0);
  const [humidity, setHumidity] = useState(0);
  const [mockAnomaly, setMockAnomaly] = useState(false);
  const [deviceStatus, setDeviceStatus] = useState<{ status: string; battery: string; lastUpdated: string } | null>(null);
  const [dataSource, setDataSource] = useState<string>("synthetic");

  // Status variables for Firebase
  const [firebaseStatus, setFirebaseStatus] = useState<'CONNECTED' | 'WAITING_FOR_DATA' | 'DISCONNECTED'>('CONNECTED');
  const [lastSyncTime, setLastSyncTime] = useState<string>(new Date().toLocaleTimeString());

  // Buffer state variables (Telemetry graphs)
  const [oxygenHistory, setOxygenHistory] = useState<number[]>([]);
  const [tempHistory, setTempHistory] = useState<number[]>([]);
  const [humidityHistory, setHumidityHistory] = useState<number[]>([]);

  const [predO2_5m, setPredO2_5m] = useState<number | null>(null);
  const [predO2_10m, setPredO2_10m] = useState<number | null>(null);
  const [o2Projection, setO2Projection] = useState<number[]>([]);

  const [alerts, setAlerts] = useState<Alert[]>([]);
  const [alertsHistory, setAlertsHistory] = useState<Alert[]>([]);
  const [recommendations, setRecommendations] = useState<Recommendation[]>([]);
  const [stats, setStats] = useState<SystemStats | null>(null);
  const [health, setHealth] = useState<SystemHealth | null>(null);
  const [events, setEvents] = useState<SystemEvent[]>([]);

  // Status thresholds check
  const o2Status = useMemo(() => {
    if (oxygen < 19.5 || oxygen > 23.5) return 'critical';
    if (oxygen < 20.0 || oxygen > 23.0) return 'warning';
    return 'normal';
  }, [oxygen]);

  const tempStatus = useMemo(() => {
    if (temperature <= 28) return 'normal';
    if (temperature <= 32) return 'warning';
    return 'critical';
  }, [temperature]);

  const humStatus = useMemo(() => {
    if (humidity <= 55) return 'normal';
    if (humidity <= 60) return 'warning';
    return 'critical';
  }, [humidity]);

  const overallSafety = useMemo(() => {
    // 1. Critical safety breach takes highest precedence
    if (o2Status === 'critical' || tempStatus === 'critical' || humStatus === 'critical') return 'critical';

    // 2. Offline Firebase connection reports as warning (degraded state)
    if (firebaseStatus !== 'CONNECTED') {
      return 'warning';
    }

    // 3. Warning limits breach
    if (tempStatus === 'warning' || humStatus === 'warning') return 'warning';

    return 'normal';
  }, [o2Status, tempStatus, humStatus, firebaseStatus]);

  const isSimulated = useMemo(() => {
    return dataSource !== 'esp32_main_01';
  }, [dataSource]);

  const hudConfig = useMemo(() => {
    let hudClass = overallSafety;
    let hudText = 'SYSTEM SECURE: ALL ENVIRONMENTAL SAFETY PARAMETERS NOMINAL.';
    let hudPillText = 'SAFE';
    let hudIcon = '🛡️';

    if (overallSafety === 'critical') {
      hudClass = 'critical';
      hudText = 'CRITICAL CHAMBER BREACH: ENVIRONMENTAL CRITICAL ALARM ACTIVE!';
      hudPillText = 'CRITICAL';
      hudIcon = '🚨';
    } else if (overallSafety === 'warning') {
      hudClass = 'warning';
      hudText = 'WARNING LEVEL BREACH: SENSORS REPORTING OUT OF NOMINAL BOUNDS.';
      hudPillText = 'WARNING';
      hudIcon = '⚠️';
    } else if (firebaseStatus !== 'CONNECTED') {
      hudClass = 'warning';
      hudText = 'DEGRADED MONITORING: FIREBASE DATABASE OFFLINE. REAL-TIME TELEMETRY IS INACTIVE.';
      hudPillText = 'DEGRADED';
      hudIcon = '⚠️';
    } else if (isSimulated) {
      hudClass = 'simulated';
      hudText = 'Running in simulation mode — live ESP32 hardware not connected. All readings are synthetically generated for demo purposes.';
      hudPillText = 'SIMULATING';
      hudIcon = 'ℹ️';
    } else {
      hudClass = 'normal';
      hudText = 'SYSTEM SECURE: ALL ENVIRONMENTAL SAFETY PARAMETERS NOMINAL.';
      hudPillText = 'SAFE';
      hudIcon = '🛡️';
    }

    return { hudClass, hudText, hudPillText, hudIcon };
  }, [overallSafety, firebaseStatus, isSimulated]);

  // Load telemetry buffers
  useEffect(() => {
    let active = true;
    const loadHistory = async () => {
      try {
        const historyData = await getSensorHistory();
        if (active && Array.isArray(historyData) && historyData.length > 0) {
          const o2Vals = historyData.map((row: { oxygen?: number }) => row.oxygen ?? 0);
          const tempVals = historyData.map((row: { temperature?: number }) => row.temperature ?? 0);
          const humVals = historyData.map((row: { humidity?: number }) => row.humidity ?? 0);

          const padArray = (arr: number[], fallbackVal: number) => {
            const padSize = 15 - arr.length;
            if (padSize > 0) {
              const padding = Array.from({ length: padSize }, () => arr[0] ?? fallbackVal);
              return [...padding, ...arr];
            }
            return arr;
          };

          setOxygenHistory(padArray(o2Vals, 0));
          setTempHistory(padArray(tempVals, 0));
          setHumidityHistory(padArray(humVals, 0));
          setFirebaseStatus('CONNECTED');
          setLastSyncTime(new Date().toLocaleTimeString());
        }
      } catch (err) {
        console.error("Failed to load history:", err);
      }
    };
    loadHistory();
    return () => {
      active = false;
    };
  }, []);

  // Poll database
  useEffect(() => {
    let active = true;

    const fetchData = async () => {
      if (!mockAnomaly) {
        try {
          const sensorData = await getSensorData();
          if (active) {
            if (sensorData && sensorData.exists === false) {
              setFirebaseStatus('WAITING_FOR_DATA');
            } else {
              const o2Val = sensorData.oxygen ?? 0;
              const tempVal = sensorData.temperature ?? 0;
              const humVal = sensorData.humidity ?? 0;
              const srcVal = sensorData.source ?? "synthetic";
              setOxygen(o2Val);
              setTemperature(tempVal);
              setHumidity(humVal);
              setDataSource(srcVal);
              setOxygenHistory(prev => [...prev.slice(1), o2Val]);
              setTempHistory(prev => [...prev.slice(1), tempVal]);
              setHumidityHistory(prev => [...prev.slice(1), humVal]);
              
              const timestamp = sensorData.timestamp ? new Date(sensorData.timestamp) : new Date();
              setSystemTime(isNaN(timestamp.getTime()) ? new Date() : timestamp);
              
              setFirebaseStatus('CONNECTED');
              setLastSyncTime(new Date().toLocaleTimeString());
            }
          }
        } catch (err) {
          console.warn("Telemetry poll failed:", err);
          if (active) {
            setSystemTime(new Date());
            setFirebaseStatus('DISCONNECTED');
          }
        }
      }

      try {
        const deviceData = await getDevices();
        if (active) {
          setDeviceStatus(deviceData);
        }
      } catch (err) {
        console.warn("Devices poll failed:", err);
        if (active) {
          setDeviceStatus({ status: "Offline", battery: "0%", lastUpdated: new Date().toISOString() });
        }
      }

      try {
        const activeAlerts = await getAlerts();
        if (active) {
          setAlerts(activeAlerts);
        }
      } catch (err) {
        console.warn("Active alerts poll failed:", err);
      }

      try {
        const historyAlerts = await getAlertHistory();
        if (active) {
          setAlertsHistory(historyAlerts);
        }
      } catch (err) {
        console.warn("History alerts poll failed:", err);
      }

      try {
        const recsData = await getRecommendations();
        if (active && recsData && recsData.success) {
          setRecommendations(recsData.recommendations || []);
        }
      } catch (err) {
        console.warn("Recommendations poll failed:", err);
      }

      try {
        const predData = await getSensorPredictions();
        if (active) {
          if (predData && predData.success && predData.exists) {
            setPredO2_5m(predData.pred5);
            setPredO2_10m(predData.pred10);
            setO2Projection(predData.projection || []);
          } else {
            setPredO2_5m(null);
            setPredO2_10m(null);
            setO2Projection([]);
          }
        }
      } catch (err) {
        console.warn("Predictions poll failed:", err);
        if (active) {
          setPredO2_5m(null);
          setPredO2_10m(null);
          setO2Projection([]);
        }
      }

      try {
        const statsData = await getSystemStats();
        if (active && statsData && statsData.success && statsData.stats && statsData.stats.telemetry) {
          setStats(statsData.stats);
        }
      } catch (err) {
        console.warn("Stats poll failed:", err);
      }

      try {
        const healthData = await getSystemHealth();
        if (active && healthData && healthData.status && healthData.memory) {
          setHealth(healthData);
        }
      } catch (err) {
        console.warn("Health poll failed:", err);
      }

      try {
        const eventsData = await getSystemEvents();
        if (active && eventsData) {
          setEvents(eventsData);
        }
      } catch (err) {
        console.warn("Events poll failed:", err);
      }
    };

    fetchData();
    const pollInterval = setInterval(fetchData, 2000);

    return () => {
      active = false;
      clearInterval(pollInterval);
    };
  }, [mockAnomaly, oxygen]);

  // Simulated Anomaly Drift
  useEffect(() => {
    if (!mockAnomaly) return;

    const simulationInterval = setInterval(() => {
      setOxygen(prev => {
        const val = Math.max(18.5, prev - 0.08);
        setTimeout(() => setOxygenHistory(h => [...h.slice(1), val]), 0);
        return val;
      });
      setTemperature(prev => {
        const val = Math.min(34.5, prev + 0.3);
        setTimeout(() => setTempHistory(h => [...h.slice(1), val]), 0);
        return val;
      });
      setHumidity(prev => {
        const val = Math.min(62.0, prev + 0.5);
        setTimeout(() => setHumidityHistory(h => [...h.slice(1), val]), 0);
        return val;
      });
      setSystemTime(new Date());
    }, 1000);

    return () => clearInterval(simulationInterval);
  }, [mockAnomaly]);

  const handleAcknowledgeAlert = async (id: number) => {
    try {
      await acknowledgeAlert(id);
      setAlerts(prev => prev.filter(a => a.id !== id));
      setAlertsHistory(prev => prev.map(a => a.id === id ? { ...a, acknowledged: 1 } : a));
    } catch (err) {
      console.error("Failed to acknowledge alert:", err);
    }
  };

  const mockEventTimes = useMemo(() => {
    const timeMs = systemTime && !isNaN(systemTime.getTime()) ? systemTime.getTime() : Date.now();
    return {
      t5s: new Date(timeMs - 5000).toLocaleTimeString(),
      t10s: new Date(timeMs - 10000).toLocaleTimeString()
    };
  }, [systemTime]);



  // Summary Metrics calculations
  const avgOxygen = useMemo(() => {
    const sum = oxygenHistory.reduce((a, b) => a + b, 0);
    return sum / (oxygenHistory.length || 1);
  }, [oxygenHistory]);

  const avgTemp = useMemo(() => {
    const sum = tempHistory.reduce((a, b) => a + b, 0);
    return sum / (tempHistory.length || 1);
  }, [tempHistory]);

  const avgHumidity = useMemo(() => {
    const sum = humidityHistory.reduce((a, b) => a + b, 0);
    return sum / (humidityHistory.length || 1);
  }, [humidityHistory]);



  // const predictionChartData = useMemo(() => {
  //   const data: any[] = [];
  //   const histSlice = oxygenHistory.slice(-5);
  //   const currentVal = oxygen > 0 ? oxygen : (predO2_5m && predO2_5m > 0 ? predO2_5m : 20.9);
  //   histSlice.forEach((val, idx) => {
  //     const isNow = idx === histSlice.length - 1;
  //     const minsAgo = (histSlice.length - 1 - idx) * 5;
  //     const timeLabel = isNow ? "Now" : `-${minsAgo}`;
  //     data.push({
  //       time: timeLabel,
  //       oxygen: Number(val.toFixed(2)),
  //       predicted: isNow ? Number(val.toFixed(2)) : null
  //     });
  //   });
  //   if (data.length === 0) {
  //     data.push({
  //       time: "Now",
  //       oxygen: Number(currentVal.toFixed(2)),
  //       predicted: Number(currentVal.toFixed(2))
  //     });
  //   }
  //   const next5 = o2Projection[0] ?? predO2_5m;
  //   const next10 = o2Projection[1] ?? predO2_10m;
  //   if (next5 !== null && next5 !== undefined) {
  //     data.push({
  //       time: "+5",
  //       oxygen: null,
  //       predicted: Number(next5.toFixed(2))
  //     });
  //   }
  //   if (next10 !== null && next10 !== undefined) {
  //     data.push({
  //       time: "+10",
  //       oxygen: null,
  //       predicted: Number(next10.toFixed(2))
  //     });
  //   }
  //   return data;
  // }, [oxygenHistory, o2Projection, predO2_5m, predO2_10m, oxygen]);

  // Custom Trend Line Plotter
  const selectedTrendData = useMemo(() => {
    if (activeTrendTab === 'oxygen') return oxygenHistory;
    if (activeTrendTab === 'temperature') return tempHistory;
    return humidityHistory;
  }, [activeTrendTab, oxygenHistory, tempHistory, humidityHistory]);

  const timeFilteredData = useMemo(() => {
    if (timeFilter === '5m') return selectedTrendData.slice(-5);
    return selectedTrendData.slice(-10);
  }, [selectedTrendData, timeFilter]);

  const trendRange = useMemo(() => {
    if (timeFilteredData.length === 0) {
      if (activeTrendTab === 'oxygen') return { min: 15, max: 25, unit: '%', color: '#0A84FF', label: 'Oxygen' };
      if (activeTrendTab === 'temperature') return { min: 0, max: 50, unit: '°C', color: '#FFD60A', label: 'Temperature' };
      return { min: 0, max: 100, unit: '%', color: '#00f0ff', label: 'Humidity' };
    }
    let dataMin = Math.min(...timeFilteredData);
    let dataMax = Math.max(...timeFilteredData);
    if (activeTrendTab === 'oxygen' && dataMax - dataMin < 0.5) {
      const mid = (dataMax + dataMin) / 2;
      dataMin = mid - 0.25;
      dataMax = mid + 0.25;
    } else if (activeTrendTab === 'temperature' && dataMax - dataMin < 1.0) {
      const mid = (dataMax + dataMin) / 2;
      dataMin = mid - 0.5;
      dataMax = mid + 0.5;
    } else if (activeTrendTab === 'humidity' && dataMax - dataMin < 2.0) {
      const mid = (dataMax + dataMin) / 2;
      dataMin = mid - 1.0;
      dataMax = mid + 1.0;
    }
    
    const dataRange = dataMax - dataMin;
    
    if (activeTrendTab === 'oxygen') {
      const min = Math.max(15, Number((dataMin - dataRange * 0.1).toFixed(1)));
      const max = Math.min(25, Number((dataMax + dataRange * 0.1).toFixed(1)));
      return { min, max, unit: '%', color: '#0A84FF', label: 'Oxygen' };
    }
    if (activeTrendTab === 'temperature') {
      const min = Math.max(0, Number((dataMin - dataRange * 0.1).toFixed(1)));
      const max = Math.min(50, Number((dataMax + dataRange * 0.1).toFixed(1)));
      return { min, max, unit: '°C', color: '#FFD60A', label: 'Temperature' };
    }
    const min = Math.max(0, Number((dataMin - dataRange * 0.1).toFixed(1)));
    const max = Math.min(100, Number((dataMax + dataRange * 0.1).toFixed(1)));
    return { min, max, unit: '%', color: '#00f0ff', label: 'Humidity' };
  }, [activeTrendTab, timeFilteredData]);

  // SVG Trend Chart Coordinates
  const trendSvgCoords = useMemo(() => {
    const w = 550;
    const h = 200;
    const padding = { left: 40, right: 20, top: 20, bottom: 30 };
    const dataRange = trendRange.max - trendRange.min || 1;
    
    if (timeFilteredData.length < 2) return { line: '', area: '', points: [], gridLines: [] };
    
    const points = timeFilteredData.map((val, idx) => {
      const x = padding.left + (idx / (timeFilteredData.length - 1)) * (w - padding.left - padding.right);
      const clamped = Math.max(trendRange.min, Math.min(trendRange.max, val));
      const y = h - padding.bottom - ((clamped - trendRange.min) / dataRange) * (h - padding.top - padding.bottom);
      return { x, y, value: val };
    });

    const line = points.reduce((acc, p, idx) => {
      return idx === 0 ? `M ${p.x} ${p.y}` : `${acc} L ${p.x} ${p.y}`;
    }, '');

    const area = `${line} L ${points[points.length - 1].x} ${h - padding.bottom} L ${points[0].x} ${h - padding.bottom} Z`;

    const gridLines = [0, 0.25, 0.5, 0.75, 1].map(pct => {
      const y = padding.top + pct * (h - padding.top - padding.bottom);
      const val = trendRange.max - pct * dataRange;
      return { y, val };
    });

    return { line, area, points, gridLines };
  }, [timeFilteredData, trendRange]);

  // Forecast SVG coordinates
  const forecastSvgCoords = useMemo(() => {
    const w = 300;
    const h = 180;
    const padding = { left: 35, right: 15, top: 15, bottom: 25 };

    const histSlice = oxygenHistory.slice(-5);
    const projSlice = o2Projection.slice(0, 6);
    const totalSteps = histSlice.length + projSlice.length;

    // Calculate dynamic axis range
    const allVals = [...histSlice, ...projSlice];
    if (allVals.length === 0) {
      return {
        histPath: '',
        predPath: '',
        confidenceBand: '',
        gridLines: [],
        dividerX: 0,
        dividerY: 0,
        latestValue: 0
      };
    }
    let dataMin = Math.min(...allVals);
    let dataMax = Math.max(...allVals);
    if (dataMax - dataMin < 0.5) {
      const mid = (dataMax + dataMin) / 2;
      dataMin = mid - 0.25;
      dataMax = mid + 0.25;
    }
    const dataRange = dataMax - dataMin;
    const minVal = Math.max(15, Number((dataMin - dataRange * 0.1).toFixed(2)));
    const maxVal = Math.min(25, Number((dataMax + dataRange * 0.1).toFixed(2)));
    const range = maxVal - minVal;

    const histPoints = histSlice.map((val, idx) => {
      const x = padding.left + (idx / (totalSteps - 1)) * (w - padding.left - padding.right);
      const clamped = Math.max(minVal, Math.min(maxVal, val));
      const y = h - padding.bottom - ((clamped - minVal) / range) * (h - padding.top - padding.bottom);
      return { x, y };
    });

    const predPoints = projSlice.map((val, idx) => {
      const x = padding.left + ((idx + histSlice.length) / (totalSteps - 1)) * (w - padding.left - padding.right);
      const clamped = Math.max(minVal, Math.min(maxVal, val));
      const y = h - padding.bottom - ((clamped - minVal) / range) * (h - padding.top - padding.bottom);
      return { x, y };
    });

    const histPath = histPoints.reduce((acc, p, idx) => idx === 0 ? `M ${p.x} ${p.y}` : `${acc} L ${p.x} ${p.y}`, '');
    const predPath = predPoints.length > 0 
      ? (histPoints.length > 0 
          ? `M ${histPoints[histPoints.length - 1].x} ${histPoints[histPoints.length - 1].y} ` 
          : `M ${predPoints[0].x} ${predPoints[0].y} `) 
        + predPoints.reduce((acc, p) => `${acc} L ${p.x} ${p.y}`, '') 
      : '';

    const upperPoints = predPoints.map((p, idx) => {
      const deviation = 0.12 * (idx + 1);
      const clamped = Math.max(minVal, Math.min(maxVal, o2Projection[idx] + deviation));
      const y = h - padding.bottom - ((clamped - minVal) / range) * (h - padding.top - padding.bottom);
      return { x: p.x, y };
    });

    const lowerPoints = predPoints.map((p, idx) => {
      const deviation = 0.12 * (idx + 1);
      const clamped = Math.max(minVal, Math.min(maxVal, o2Projection[idx] - deviation));
      const y = h - padding.bottom - ((clamped - minVal) / range) * (h - padding.top - padding.bottom);
      return { x: p.x, y };
    });

    let confidenceBand = '';
    if (upperPoints.length > 0) {
      const startX = histPoints.length > 0 ? histPoints[histPoints.length - 1].x : upperPoints[0].x;
      const startY = histPoints.length > 0 ? histPoints[histPoints.length - 1].y : upperPoints[0].y;
      const upperStr = upperPoints.reduce((acc, p) => `${acc} L ${p.x} ${p.y}`, `M ${startX} ${startY}`);
      const lowerStr = [...lowerPoints].reverse().reduce((acc, p) => `${acc} L ${p.x} ${p.y}`, '');
      confidenceBand = `${upperStr} ${lowerStr} Z`;
    }

    const gridLines = [minVal, (minVal + maxVal) / 2, maxVal].map(val => {
      const y = h - padding.bottom - ((val - minVal) / range) * (h - padding.top - padding.bottom);
      return { y, val };
    });

    const latestHistPoint = histPoints[histPoints.length - 1];

    return {
      histPath,
      predPath,
      confidenceBand,
      gridLines,
      dividerX: latestHistPoint?.x || 0,
      dividerY: latestHistPoint?.y || 0,
      latestValue: histSlice[histSlice.length - 1] ?? 0
    };
  }, [oxygenHistory, o2Projection]);

  // Modular components definition
  const oxygenCard = (
    <div className="glass-card kpi-card">
      <div className="kpi-header">
        <div className="kpi-icon-wrapper blue">
          <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
            <circle cx="12" cy="12" r="10" />
            <path d="M12 2a15.3 15.3 0 0 1 4 10 15.3 15.3 0 0 1-4 10 15.3 15.3 0 0 1-4-10 15.3 15.3 0 0 1 4-10z" />
          </svg>
        </div>
        <span className={`kpi-status-badge ${o2Status}`}>{o2Status}</span>
      </div>
      <div>
        <div className="kpi-title">Oxygen Concentration</div>
        <div className="kpi-value-group">
          <span className="kpi-value">{oxygen.toFixed(2)}</span>
          <span className="kpi-unit">%</span>
        </div>
      </div>
      <div className="kpi-footer" style={{ flexDirection: 'column', alignItems: 'stretch', gap: '10px' }}>
        <div>
          <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.65rem', color: 'var(--text-secondary)', fontWeight: 600, marginBottom: '4px' }}>
            <span>Min: 19.5%</span>
            <span style={{ fontSize: '0.62rem', color: 'var(--text-tertiary)' }}>Safe Range</span>
            <span>Max: 23.5%</span>
          </div>
          <div style={{ height: '4px', width: '100%', background: 'rgba(255, 255, 255, 0.08)', borderRadius: '2px', position: 'relative' }}>
            <div style={{
              position: 'absolute',
              left: `${getPercent(oxygen, 19.5, 23.5)}%`,
              top: '50%',
              transform: 'translate(-50%, -50%)',
              width: '8px',
              height: '8px',
              borderRadius: '50%',
              background: o2Status === 'normal' ? 'var(--color-success)' : o2Status === 'warning' ? 'var(--color-warning)' : 'var(--color-critical)',
              boxShadow: `0 0 6px ${o2Status === 'normal' ? 'var(--color-success)' : o2Status === 'warning' ? 'var(--color-warning)' : 'var(--color-critical)'}`,
              transition: 'left 0.3s cubic-bezier(0.16, 1, 0.3, 1)'
            }} />
          </div>
        </div>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <div style={{ fontSize: '0.62rem', color: 'var(--text-tertiary)' }}>Interval: 5s | Live</div>
          <div className="sparkline-container">
            <Sparkline data={oxygenHistory} color="#0A84FF" min={18} max={25} />
          </div>
        </div>
      </div>
    </div>
  );

  const humidityCard = (
    <div className="glass-card kpi-card">
      <div className="kpi-header">
        <div className="kpi-icon-wrapper cyan">
          <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
            <path d="M12 22a7 7 0 0 0 7-7c0-4.3-7-11-7-11S5 10.7 5 15a7 7 0 0 0 7 7z" />
          </svg>
        </div>
        <span className={`kpi-status-badge ${humStatus}`}>{humStatus}</span>
      </div>
      <div>
        <div className="kpi-title">Humidity</div>
        <div className="kpi-value-group">
          <span className="kpi-value">{humidity.toFixed(1)}</span>
          <span className="kpi-unit">%</span>
        </div>
      </div>
      <div className="kpi-footer" style={{ flexDirection: 'column', alignItems: 'stretch', gap: '10px' }}>
        <div>
          <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.65rem', color: 'var(--text-secondary)', fontWeight: 600, marginBottom: '4px' }}>
            <span>Min: 40%</span>
            <span style={{ fontSize: '0.62rem', color: 'var(--text-tertiary)' }}>Ideal Range</span>
            <span>Max: 60%</span>
          </div>
          <div style={{ height: '4px', width: '100%', background: 'rgba(255, 255, 255, 0.08)', borderRadius: '2px', position: 'relative' }}>
            <div style={{
              position: 'absolute',
              left: `${getPercent(humidity, 40, 60)}%`,
              top: '50%',
              transform: 'translate(-50%, -50%)',
              width: '8px',
              height: '8px',
              borderRadius: '50%',
              background: humStatus === 'normal' ? 'var(--color-success)' : humStatus === 'warning' ? 'var(--color-warning)' : 'var(--color-critical)',
              boxShadow: `0 0 6px ${humStatus === 'normal' ? 'var(--color-success)' : humStatus === 'warning' ? 'var(--color-warning)' : 'var(--color-critical)'}`,
              transition: 'left 0.3s cubic-bezier(0.16, 1, 0.3, 1)'
            }} />
          </div>
        </div>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <div style={{ fontSize: '0.62rem', color: 'var(--text-tertiary)' }}>Interval: 5s | Live</div>
          <div className="sparkline-container">
            <Sparkline data={humidityHistory} color="#00f0ff" min={20} max={80} />
          </div>
        </div>
      </div>
    </div>
  );

  const temperatureCard = (
    <div className="glass-card kpi-card">
      <div className="kpi-header">
        <div className="kpi-icon-wrapper orange">
          <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
            <path d="M14 14.76V3.5a2.5 2.5 0 0 0-5 0v11.26a4.5 4.5 0 1 0 5 0z" />
          </svg>
        </div>
        <span className={`kpi-status-badge ${tempStatus}`}>{tempStatus}</span>
      </div>
      <div>
        <div className="kpi-title">Temperature</div>
        <div className="kpi-value-group">
          <span className="kpi-value">{temperature.toFixed(1)}</span>
          <span className="kpi-unit">°C</span>
        </div>
      </div>
      <div className="kpi-footer" style={{ flexDirection: 'column', alignItems: 'stretch', gap: '10px' }}>
        <div>
          <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.65rem', color: 'var(--text-secondary)', fontWeight: 600, marginBottom: '4px' }}>
            <span>Min: 20°C</span>
            <span style={{ fontSize: '0.62rem', color: 'var(--text-tertiary)' }}>Ideal Range</span>
            <span>Max: 30°C</span>
          </div>
          <div style={{ height: '4px', width: '100%', background: 'rgba(255, 255, 255, 0.08)', borderRadius: '2px', position: 'relative' }}>
            <div style={{
              position: 'absolute',
              left: `${getPercent(temperature, 20, 30)}%`,
              top: '50%',
              transform: 'translate(-50%, -50%)',
              width: '8px',
              height: '8px',
              borderRadius: '50%',
              background: tempStatus === 'normal' ? 'var(--color-success)' : tempStatus === 'warning' ? 'var(--color-warning)' : 'var(--color-critical)',
              boxShadow: `0 0 6px ${tempStatus === 'normal' ? 'var(--color-success)' : tempStatus === 'warning' ? 'var(--color-warning)' : 'var(--color-critical)'}`,
              transition: 'left 0.3s cubic-bezier(0.16, 1, 0.3, 1)'
            }} />
          </div>
        </div>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <div style={{ fontSize: '0.62rem', color: 'var(--text-tertiary)' }}>Interval: 5s | Live</div>
          <div className="sparkline-container">
            <Sparkline data={tempHistory} color="#FFD60A" min={15} max={40} />
          </div>
        </div>
      </div>
    </div>
  );



  // const predictionAreaCard = null;

  const trendsCard = (
    <div className="glass-card" style={{ width: '100%' }}>
      <div className="chart-header" style={{ flexDirection: 'column', alignItems: 'flex-start', gap: '12px' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', width: '100%', alignItems: 'center' }}>
          <div>
            <h3 className="card-title">Environmental Parameter Trends</h3>
            <span style={{ fontSize: '0.8rem', color: 'var(--text-secondary)' }}>Historic database telemetry sweeps</span>
          </div>

        </div>
        
        <div style={{ display: 'flex', gap: '12px', width: '100%', justifyContent: 'space-between', borderTop: '1px solid rgba(255,255,255,0.04)', paddingTop: '10px' }}>
          <div className="chart-filters" style={{ background: 'rgba(255, 255, 255, 0.02)' }}>
            {(['oxygen', 'temperature', 'humidity'] as const).map(tab => (
              <button 
                key={tab} 
                className={`filter-btn ${activeTrendTab === tab ? 'active' : ''}`}
                onClick={() => setActiveTrendTab(tab)}
              >
                {tab.toUpperCase()}
              </button>
            ))}
          </div>

          <div className="chart-filters">
            {(['5m', '10m'] as const).map(f => (
              <button 
                key={f} 
                className={`filter-btn ${timeFilter === f ? 'active' : ''}`}
                onClick={() => setTimeFilter(f)}
              >
                {f === '5m' ? '5 MIN' : '10 MIN'}
              </button>
            ))}
          </div>
        </div>
      </div>

      <div className="trend-chart-body" style={{ marginTop: '16px' }}>
        <svg width="100%" height="100%" viewBox="0 0 550 200" preserveAspectRatio="none">
          <defs>
            <linearGradient id="trendGrad" x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor={trendRange.color} stopOpacity="0.25" />
              <stop offset="100%" stopColor={trendRange.color} stopOpacity="0.0" />
            </linearGradient>
          </defs>
          
          {/* Grid Lines */}
          {trendSvgCoords.gridLines.map((line, idx) => (
            <line key={idx} x1="40" y1={line.y} x2="530" y2={line.y} stroke="rgba(255,255,255,0.03)" strokeWidth="1" />
          ))}
          {trendSvgCoords.gridLines.map((line, idx) => (
            <text key={idx} x="32" y={line.y + 4} fill="var(--text-secondary)" fontSize="8.5" textAnchor="end" fontFamily="var(--font-mono)">
              {line.val.toFixed(1)}
            </text>
          ))}

          {/* Shaded Area */}
          {trendSvgCoords.area && (
            <path d={trendSvgCoords.area} fill="url(#trendGrad)" />
          )}

          {/* Plot Line */}
          {trendSvgCoords.line && (
            <path d={trendSvgCoords.line} fill="none" stroke={trendRange.color} strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round" />
          )}

          {/* Nodes */}
          {trendSvgCoords.points.map((pt, idx) => {
            const isLatest = idx === trendSvgCoords.points.length - 1;
            return (
              <g key={idx}>
                <circle 
                  cx={pt.x} 
                  cy={pt.y} 
                  r={isLatest ? 4.5 : 2.5} 
                  fill={isLatest ? '#fff' : trendRange.color} 
                  stroke={isLatest ? trendRange.color : 'none'} 
                  strokeWidth={isLatest ? 2 : 0} 
                  style={{ cursor: 'pointer' }}
                />
                {isLatest && (
                  <g>
                    {/* Pointer line connecting tooltip to point */}
                    <line x1={pt.x} y1={pt.y} x2={pt.x} y2={pt.y - 12} stroke="rgba(255,255,255,0.4)" strokeWidth="1" />
                    {/* Tooltip box centered over point */}
                    <rect x={pt.x - 30} y={pt.y - 30} width="60" height="18" rx="4" fill="rgba(0,0,0,0.85)" stroke="var(--border-subtle)" strokeWidth="1" />
                    <text x={pt.x} y={pt.y - 18} fill="#fff" fontSize="9" fontWeight="700" textAnchor="middle" fontFamily="var(--font-mono)">
                      {pt.value.toFixed(2)}{trendRange.unit}
                    </text>
                  </g>
                )}
              </g>
            );
          })}
        </svg>
      </div>
    </div>
  );

  const forecastCard = (
    <div className="glass-card" style={{ width: '100%' }}>
      <h3 className="card-title" style={{ marginBottom: '6px' }}>Oxygen Concentration Forecast</h3>
      <div style={{ fontSize: '0.75rem', color: 'var(--text-secondary)', display: 'flex', flexDirection: 'column', gap: '3px', marginBottom: '8px' }}>
        <span>Model: <strong>Linear Least-Squares Regression</strong></span>
        <span>Horizon: <strong>Next 10 Minutes</strong></span>
        <span>Projections: <strong>
          +5m: {predO2_5m !== null && predO2_5m !== undefined ? `${predO2_5m.toFixed(2)}%` : '--'} | 
          +10m: {predO2_10m !== null && predO2_10m !== undefined ? `${predO2_10m.toFixed(2)}%` : '--'}
        </strong></span>
      </div>
      
      <div style={{ height: '140px', width: '100%', marginTop: '12px' }}>
        <svg width="100%" height="100%" viewBox="0 0 300 180" preserveAspectRatio="none">
          <defs>
            <linearGradient id="forecastBandGrad" x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor="#0A84FF" stopOpacity="0.08" />
              <stop offset="100%" stopColor="#0A84FF" stopOpacity="0.0" />
            </linearGradient>
          </defs>

          {/* Grid Lines */}
          {forecastSvgCoords.gridLines.map((line, idx) => (
            <line key={idx} x1="35" y1={line.y} x2="285" y2={line.y} stroke="rgba(255,255,255,0.06)" strokeWidth="1" />
          ))}
          {forecastSvgCoords.gridLines.map((line, idx) => (
            <text key={idx} x="28" y={line.y + 3} fill="var(--text-secondary)" fontSize="8" textAnchor="end" fontFamily="var(--font-mono)">
              {line.val.toFixed(1)}%
            </text>
          ))}

          {/* Shaded Confidence Ribbon */}
          {forecastSvgCoords.confidenceBand && (
            <path d={forecastSvgCoords.confidenceBand} fill="url(#forecastBandGrad)" />
          )}

          {/* Historical line segment */}
          {forecastSvgCoords.histPath && (
            <path d={forecastSvgCoords.histPath} fill="none" stroke="var(--text-secondary)" strokeWidth="2.0" strokeLinecap="round" />
          )}

          {/* Forecast projection line */}
          {forecastSvgCoords.predPath && (
            <path d={forecastSvgCoords.predPath} fill="none" stroke="#0A84FF" strokeWidth="2.5" strokeDasharray="3,3" strokeLinecap="round" />
          )}

          {/* Highlighted current dot and dynamic tooltip */}
          {forecastSvgCoords.dividerX > 0 && (
            <g>
              {/* Pointer line connecting tooltip to current dot */}
              <line x1={forecastSvgCoords.dividerX} y1={forecastSvgCoords.dividerY} x2={forecastSvgCoords.dividerX} y2={forecastSvgCoords.dividerY - 14} stroke="rgba(255,255,255,0.4)" strokeWidth="1" />
              {/* Tooltip box centered over current dot */}
              <rect x={forecastSvgCoords.dividerX - 30} y={forecastSvgCoords.dividerY - 32} width="60" height="18" rx="4" fill="rgba(0,0,0,0.85)" stroke="var(--border-subtle)" strokeWidth="1" />
              <text x={forecastSvgCoords.dividerX} y={forecastSvgCoords.dividerY - 20} fill="#fff" fontSize="9.5" fontWeight="700" textAnchor="middle" fontFamily="var(--font-mono)">
                {forecastSvgCoords.latestValue.toFixed(2)}%
              </text>

              {/* Highlighted current dot */}
              <circle cx={forecastSvgCoords.dividerX} cy={forecastSvgCoords.dividerY} r="5" fill="#fff" stroke="#0A84FF" strokeWidth="2" />
              <circle cx={forecastSvgCoords.dividerX} cy={forecastSvgCoords.dividerY} r="2.5" fill="#0A84FF" />
            </g>
          )}

          {/* Current Time Divider */}
          {forecastSvgCoords.dividerX > 0 && (
            <g>
              <line x1={forecastSvgCoords.dividerX} y1="15" x2={forecastSvgCoords.dividerX} y2="155" stroke="#0A84FF" strokeWidth="1" strokeOpacity="0.5" />
              <text x={forecastSvgCoords.dividerX} y="165" fill="#0A84FF" fontSize="7" fontWeight="700" textAnchor="middle">
                CURRENT TIME
              </text>
            </g>
          )}
        </svg>
      </div>

      <div className="forecast-progress-container" style={{ marginTop: '12px' }}>
        <div style={{ fontSize: '0.7rem', color: 'var(--text-secondary)', fontStyle: 'italic' }}>
          Forecast Summary: O₂ levels projected to remain stable within nominal safe margins.
        </div>
      </div>
    </div>
  );

  const overviewCard = (
    <div className="glass-card" style={{ width: '100%' }}>
      <h3 className="card-title">Live Environment Overview</h3>
      
      <div className="environment-info-list">

        <div className="env-info-item">
          <span className="env-info-label">Indoor Air Status</span>
          <span className="env-info-value" style={{ color: overallSafety === 'critical' ? 'var(--color-critical)' : 'var(--color-success)' }}>
            {overallSafety === 'critical' ? 'POOR' : 'EXCELLENT'}
          </span>
        </div>
        {health && (
          <div className="env-info-item">
            <span className="env-info-label">Server Memory</span>
            <span className="env-info-value">{(health.memory.heapUsed / 1024 / 1024).toFixed(1)} MB</span>
          </div>
        )}
        {events.length > 0 && (
          <div className="env-info-item">
            <span className="env-info-label">Latest Sys Event</span>
            <span className="env-info-value" style={{ color: 'var(--accent-blue)', fontSize: '0.8rem' }}>{events[0].event}</span>
          </div>
        )}
        <div className="env-info-item" style={{ borderBottom: 'none' }}>
          <span className="env-info-label">Last Sensor Sync</span>
          <span className="env-info-value">{systemTime.toLocaleTimeString()}</span>
        </div>
      </div>

      {/* Real-time Activity Logs */}
      <div style={{ marginTop: '16px', borderTop: '1px solid rgba(255,255,255,0.04)', paddingTop: '10px' }}>
        <span style={{ fontSize: '0.72rem', color: 'var(--text-secondary)', fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.04em' }}>
          System Activity Log
        </span>
        <div style={{ display: 'flex', flexDirection: 'column', gap: '6px', maxHeight: '110px', overflowY: 'auto', marginTop: '6px', paddingRight: '4px' }}>
          {events.length === 0 ? (
            <>
              <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.68rem' }}>
                <span style={{ color: 'var(--text-tertiary)' }}>[{systemTime.toLocaleTimeString()}]</span>
                <span style={{ fontWeight: 600 }}>Firebase Synced</span>
                <span style={{ color: 'var(--color-success)' }}>SUCCESS</span>
              </div>
              <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.68rem' }}>
                <span style={{ color: 'var(--text-tertiary)' }}>[{mockEventTimes.t5s}]</span>
                <span style={{ fontWeight: 600 }}>Telemetry Update</span>
                <span style={{ color: 'var(--color-success)' }}>ONLINE</span>
              </div>
              <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.68rem' }}>
                <span style={{ color: 'var(--text-tertiary)' }}>[{mockEventTimes.t10s}]</span>
                <span style={{ fontWeight: 600 }}>Forecast Generated</span>
                <span style={{ color: 'var(--accent-blue)' }}>SUCCESS</span>
              </div>
            </>
          ) : (
            events.slice(0, 5).map((evt, idx) => (
              <div key={idx} style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.68rem' }}>
                <span style={{ color: 'var(--text-tertiary)' }}>[{formatTimeSafe(evt.timestamp)}]</span>
                <span style={{ fontWeight: 600, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', maxWidth: '120px' }}>{evt.event}</span>
                <span style={{ color: evt.event.includes('STARTUP') || evt.event.includes('NOMINAL') ? 'var(--color-success)' : 'var(--color-warning)' }}>
                  {evt.event.includes('STARTUP') ? 'OK' : 'ACTIVE'}
                </span>
              </div>
            ))
          )}
        </div>
      </div>
    </div>
  );

  const alertsCard = (
    <div className="glass-card" style={{ width: '100%' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '16px' }}>
        <div>
          <h3 className="card-title">Recent Alerts</h3>
          <div style={{ fontSize: '0.72rem', color: 'var(--text-secondary)', display: 'flex', gap: '8px', marginTop: '4px' }}>
            <span>Active: <strong style={{ color: 'var(--color-critical)' }}>{alerts.length}</strong></span>
            <span>Resolved: <strong style={{ color: 'var(--color-success)' }}>{stats ? stats.alerts.resolved : alertsHistory.filter(a => a.status === 'Resolved').length}</strong></span>
            <span>Total: <strong style={{ color: 'var(--text-primary)' }}>{alertsHistory.length}</strong></span>
          </div>
        </div>
        <button className="ack-btn" style={{ border: 'none', fontSize: '0.72rem' }}>VIEW ALL</button>
      </div>

      <div className="alerts-list">
        {alerts.length === 0 ? (
          <div style={{ color: 'var(--text-tertiary)', fontSize: '0.85rem', textAlign: 'center', marginTop: '40px', fontWeight: 600 }}>
            NO RECENT SECURITY ALERTS
          </div>
        ) : (
          alerts.slice(0, 4).map(alert => (
            <div key={alert.id} className="alert-row">
              <div className="alert-row-meta">
                <span className={`alert-dot ${alert.severity === 'critical' ? 'critical' : 'warning'}`} />
                <div className="alert-message">{alert.message}</div>
              </div>
              <div className="alert-time">
                {formatTime2DigitSafe(alert.timestamp)}
              </div>
              <button className="ack-btn" onClick={() => handleAcknowledgeAlert(alert.id)}>ACK</button>
            </div>
          ))
        )}
      </div>
    </div>
  );

  const summaryCard = (
    <div className="glass-card" style={{ width: '100%' }}>
      <h3 className="card-title" style={{ marginBottom: '14px' }}>Today's Summary</h3>
      
      <div className="summary-grid" style={{ gridTemplateColumns: '1fr', gap: '10px' }}>
        
        {/* Telemetry Stats Grid */}
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: '6px', fontSize: '0.72rem', borderBottom: '1px solid rgba(255,255,255,0.04)', paddingBottom: '8px' }}>
          <div style={{ display: 'flex', flexDirection: 'column', gap: '2px' }}>
            <span style={{ color: 'var(--text-secondary)', fontWeight: 600 }}>O₂ MIN / AVG / MAX</span>
            <span style={{ fontFamily: 'var(--font-mono)', fontWeight: 700 }}>
              {stats ? `${stats.telemetry.oxygen.min.toFixed(2)}%` : (oxygenHistory.length > 0 ? `${Math.min(...oxygenHistory).toFixed(2)}%` : '0.00%')} / {avgOxygen.toFixed(2)}% / {stats ? `${stats.telemetry.oxygen.max.toFixed(2)}%` : (oxygenHistory.length > 0 ? `${Math.max(...oxygenHistory).toFixed(2)}%` : '0.00%')}
            </span>
          </div>
          <div style={{ display: 'flex', flexDirection: 'column', gap: '2px' }}>
            <span style={{ color: 'var(--text-secondary)', fontWeight: 600 }}>TEMP MIN / AVG / MAX</span>
            <span style={{ fontFamily: 'var(--font-mono)', fontWeight: 700 }}>
              {stats ? `${stats.telemetry.temperature.min.toFixed(1)}°C` : (tempHistory.length > 0 ? `${Math.min(...tempHistory).toFixed(1)}°C` : '0.0°C')} / {avgTemp.toFixed(1)}°C / {stats ? `${stats.telemetry.temperature.max.toFixed(1)}°C` : (tempHistory.length > 0 ? `${Math.max(...tempHistory).toFixed(1)}°C` : '0.0°C')}
            </span>
          </div>
          <div style={{ display: 'flex', flexDirection: 'column', gap: '2px' }}>
            <span style={{ color: 'var(--text-secondary)', fontWeight: 600 }}>HUM MIN / AVG / MAX</span>
            <span style={{ fontFamily: 'var(--font-mono)', fontWeight: 700 }}>
              {stats ? `${stats.telemetry.humidity.min.toFixed(0)}%` : (humidityHistory.length > 0 ? `${Math.min(...humidityHistory).toFixed(0)}%` : '0%')} / {avgHumidity.toFixed(0)}% / {stats ? `${stats.telemetry.humidity.max.toFixed(0)}%` : (humidityHistory.length > 0 ? `${Math.max(...humidityHistory).toFixed(0)}%` : '0%')}
            </span>
          </div>
        </div>

        {/* Incidents Summary Grid */}
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: '4px', fontSize: '0.7rem', textAlign: 'center', color: 'var(--text-secondary)' }}>
          <div>
            <div>TOTAL</div>
            <div style={{ color: 'var(--text-primary)', fontWeight: 700, fontSize: '0.85rem', fontFamily: 'var(--font-mono)' }}>{stats ? stats.alerts.total : alertsHistory.length}</div>
          </div>
          <div>
            <div style={{ color: 'var(--color-critical)' }}>ACTIVE</div>
            <div style={{ color: 'var(--color-critical)', fontWeight: 700, fontSize: '0.85rem', fontFamily: 'var(--font-mono)' }}>{stats ? stats.alerts.active : alerts.length}</div>
          </div>
          <div>
            <div style={{ color: 'var(--color-success)' }}>RESOLVED</div>
            <div style={{ color: 'var(--color-success)', fontWeight: 700, fontSize: '0.85rem', fontFamily: 'var(--font-mono)' }}>{stats ? stats.alerts.resolved : alertsHistory.filter(a => a.status === 'Resolved').length}</div>
          </div>
          <div>
            <div style={{ color: 'var(--color-warning)' }}>ACK</div>
            <div style={{ color: 'var(--color-warning)', fontWeight: 700, fontSize: '0.85rem', fontFamily: 'var(--font-mono)' }}>{stats ? stats.alerts.acknowledged : alertsHistory.filter(a => a.acknowledged === 1).length}</div>
          </div>
        </div>

      </div>
    </div>
  );

  const getFirebaseStatusColor = () => {
    if (firebaseStatus === 'CONNECTED') return 'var(--color-success)';
    if (firebaseStatus === 'WAITING_FOR_DATA') return 'var(--color-warning)';
    return 'var(--color-critical)';
  };

  const getFirebaseStatusText = () => {
    if (firebaseStatus === 'CONNECTED') return 'CONNECTED';
    if (firebaseStatus === 'WAITING_FOR_DATA') return 'WAITING FOR DATA';
    return 'DISCONNECTED';
  };

  const firebaseCard = (
    <div className="status-grid-item" style={{ width: '100%' }}>
      <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke={getFirebaseStatusColor()} strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
        <path d="M5 12.55a11 11 0 0 1 14.08 0" />
        <path d="M1.42 9a16 16 0 0 1 21.16 0" />
        <path d="M8.53 16.11a6 6 0 0 1 6.95 0" />
        <line x1="12" y1="20" x2="12.01" y2="20" />
      </svg>
      <div className="status-grid-label-group">
        <span className="status-grid-label">Firebase Database</span>
        <span className="status-grid-value" style={{ color: getFirebaseStatusColor() }}>
          {getFirebaseStatusText()}
        </span>
      </div>
    </div>
  );

  const sensorStatusCard = useMemo(() => {
    const batteryStr = deviceStatus?.battery ?? '98%';
    const batteryPct = parseInt(batteryStr) || 100;
    const batteryColor = batteryPct < 20 
      ? 'var(--color-critical)' 
      : batteryPct < 50 
        ? 'var(--color-warning)' 
        : 'var(--text-primary)';

    const rssiVal = deviceStatus?.status === 'Online' ? -62 : -100;
    const rssiStr = deviceStatus?.status === 'Online' ? `${rssiVal} dBm` : 'N/A';
    const rssiColor = rssiVal <= -85 
      ? 'var(--color-critical)' 
      : rssiVal <= -75 
        ? 'var(--color-warning)' 
        : 'var(--text-primary)';

    const commTime = (deviceStatus && deviceStatus.lastUpdated) 
      ? formatTimeSafe(deviceStatus.lastUpdated) 
      : formatTimeSafe(systemTime);

    return (
      <div className="status-grid-item" style={{ flexDirection: 'column', alignItems: 'flex-start', gap: '8px', width: '100%' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
          <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="var(--accent-blue)" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
            <rect x="2" y="2" width="20" height="8" rx="2" ry="2" />
            <rect x="2" y="14" width="20" height="8" rx="2" ry="2" />
          </svg>
          <div className="status-grid-label-group">
            <span className="status-grid-label">Sensor Status</span>
            <span className="status-grid-value" style={{ color: isSimulated ? 'var(--accent-blue)' : 'var(--color-success)' }}>
              {isSimulated ? 'SIMULATED' : 'LIVE (ESP32)'}
            </span>
          </div>
        </div>
        
        <div style={{ display: 'flex', gap: '20px', fontSize: '0.68rem', color: 'var(--text-secondary)', borderTop: '1px solid rgba(255,255,255,0.04)', paddingTop: '8px', width: '100%' }}>
          {/* Left Column - Hardware */}
          <div style={{ display: 'flex', flexDirection: 'column', gap: '5px', flex: 1 }}>
            <div style={{ fontWeight: 700, fontSize: '0.62rem', color: 'var(--text-tertiary)', textTransform: 'uppercase', letterSpacing: '0.04em', marginBottom: '2px' }}>Hardware</div>
            <div style={{ display: 'flex', justifyContent: 'space-between' }}>
              <span>Controller:</span>
              <strong style={{ color: 'var(--text-primary)' }}>ESP32 Node</strong>
            </div>
            <div style={{ display: 'flex', justifyContent: 'space-between' }}>
              <span>DHT Sensor:</span>
              <strong style={{ color: 'var(--color-success)' }}>ACTIVE</strong>
            </div>
            <div style={{ display: 'flex', justifyContent: 'space-between' }}>
              <span>MQ135 Gas:</span>
              <strong style={{ color: 'var(--color-success)' }}>CALIBRATED</strong>
            </div>
            <div style={{ display: 'flex', justifyContent: 'space-between' }}>
              <span>Firmware:</span>
              <strong style={{ color: 'var(--text-primary)' }}>v1.0.8</strong>
            </div>
          </div>

          {/* Right Column - Connection & Power */}
          <div style={{ display: 'flex', flexDirection: 'column', gap: '5px', flex: 1 }}>
            <div style={{ fontWeight: 700, fontSize: '0.62rem', color: 'var(--text-tertiary)', textTransform: 'uppercase', letterSpacing: '0.04em', marginBottom: '2px' }}>Link & Power</div>
            <div style={{ display: 'flex', justifyContent: 'space-between' }}>
              <span>WiFi Link:</span>
              <strong style={{ color: deviceStatus?.status === 'Online' ? 'var(--color-success)' : 'var(--color-critical)' }}>
                {deviceStatus?.status === 'Online' ? 'CONNECTED' : 'DISCONNECTED'}
              </strong>
            </div>
            <div style={{ display: 'flex', justifyContent: 'space-between' }}>
              <span>RSSI:</span>
              <strong style={{ color: rssiColor }}>{rssiStr}</strong>
            </div>
            <div style={{ display: 'flex', justifyContent: 'space-between' }}>
              <span>Battery:</span>
              <strong style={{ color: batteryColor }}>{batteryStr}</strong>
            </div>
            <div style={{ display: 'flex', justifyContent: 'space-between' }}>
              <span>Comm:</span>
              <strong style={{ color: 'var(--text-primary)' }}>{commTime}</strong>
            </div>
          </div>
        </div>
      </div>
    );
  }, [deviceStatus, systemTime]);

  const recCard = (
    <div className="status-grid-item rec-card" style={{ flexGrow: 1, width: '100%' }}>
      <div style={{ display: 'flex', flexDirection: 'column', gap: '4px' }}>
        <div className="rec-title-group">
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
            <path d="M18 8A6 6 0 0 0 6 8c0 7-3 9-3 9h18s-3-2-3-9" />
            <path d="M13.73 21a2 2 0 0 1-3.46 0" />
          </svg>
          <span>Sentinel Directive</span>
        </div>
        <div className="rec-text">
          {recommendations.length > 0 ? recommendations[0].text : (
            overallSafety === 'critical' 
              ? 'CRITICAL ALERT: Initiate emergency oxygen supply. Clear the monitoring space immediately!' 
              : overallSafety === 'warning' 
                ? 'WARNING: Open ambient fresh air vents and verify ventilation loops.' 
                : 'SAFE: Atmospheric index is fully within nominal bounds. No action required.'
          )}
        </div>
      </div>
    </div>
  );


  return (
    <div className={`app-container ${theme}-theme`}>
      {loading && <Loader onComplete={() => setLoading(false)} />}
      
      {/* LEFT SIDEBAR */}
      <aside className="sidebar">
        <div className="sidebar-brand">
          <div className="sidebar-logo">
            <span>O₂</span> Sentinel
          </div>
          <div className="sidebar-subtitle">Environmental Monitor</div>
        </div>

        <nav className="sidebar-nav">
          {[
            { name: 'Dashboard', icon: <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><rect x="3" y="3" width="7" height="7"></rect><rect x="14" y="3" width="7" height="7"></rect><rect x="14" y="14" width="7" height="7"></rect><rect x="3" y="14" width="7" height="7"></rect></svg> },
            { name: 'Live Data', icon: <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><polyline points="22 12 18 12 15 21 9 3 6 12 2 12"></polyline></svg> },
            { name: 'Predictions', icon: <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><line x1="18" y1="20" x2="18" y2="10"></line><line x1="12" y1="20" x2="12" y2="4"></line><line x1="6" y1="20" x2="6" y2="14"></line></svg> },
            { name: 'Alerts', icon: <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z"></path><line x1="12" y1="9" x2="12" y2="13"></line><line x1="12" y1="17" x2="12.01" y2="17"></line></svg> },
            { name: 'Reports', icon: <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"></path><polyline points="14 2 14 8 20 8"></polyline><line x1="16" y1="13" x2="8" y2="13"></line><line x1="16" y1="17" x2="8" y2="17"></line><polyline points="10 9 9 9 8 9"></polyline></svg> },
            { name: 'Settings', icon: <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><circle cx="12" cy="12" r="3"></circle><path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 1 1-2.83 2.83l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-4 0v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 1 1-2.83-2.83l.06-.06a1.65 1.65 0 0 0 .33-1.82 1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1 0-4h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 1 1 2.83-2.83l.06.06a1.65 1.65 0 0 0 1.82.33H9a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 4 0v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 1 1 2.83 2.83l-.06.06a1.65 1.65 0 0 0-.33 1.82V9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 0 4h-.09a1.65 1.65 0 0 0-1.51 1z"></path></svg> }
          ].map(item => (
            <a 
              key={item.name} 
              className={`nav-item ${activeNav === item.name ? 'active' : ''}`}
              onClick={() => setActiveNav(item.name)}
            >
              {item.icon}
              {item.name}
            </a>
          ))}
        </nav>

        <div className="sidebar-card">
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="#0A84FF" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
              <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z" />
            </svg>
            <div className="sidebar-card-title">Breathe Better</div>
          </div>
          <div className="sidebar-card-subtitle">Real-time environmental monitoring for safer spaces.</div>
          <svg style={{ marginTop: '4px', opacity: 0.8 }} width="100%" height="50" viewBox="0 0 150 50">
            <path d="M10,40 Q40,10 75,40 T140,40" fill="none" stroke="rgba(10, 132, 255, 0.4)" strokeWidth="3" />
            <path d="M20,35 Q50,15 85,35 T130,35" fill="none" stroke="rgba(10, 132, 255, 0.2)" strokeWidth="2" />
          </svg>
        </div>
      </aside>

      {/* MAIN CONTENT AREA */}
      <main className="main-content fade-in">
        
        {/* TOP HEADER */}
        <header className="top-header">
          <div className="header-title-group">
            <h1 className="header-title">{activeNav}</h1>
            <div className="header-subtitle">Real-Time Environmental Monitoring</div>
          </div>

          <div className="header-controls">
            {health && (
              <div style={{ display: 'flex', gap: '14px', fontSize: '0.78rem', color: 'var(--text-secondary)', background: 'rgba(255,255,255,0.02)', padding: '6px 12px', border: '1px solid var(--border-subtle)', borderRadius: 'var(--border-radius-sm)', marginRight: '10px' }}>
                <span>SRV: <strong style={{ color: health.status === 'HEALTHY' ? 'var(--color-success)' : 'var(--color-critical)' }}>{health.status}</strong></span>
                <span>MEM: <strong>{(health.memory.heapUsed / 1024 / 1024).toFixed(1)}MB</strong></span>
                <span>WRK: <strong style={{ color: health.worker?.active ? 'var(--color-success)' : 'var(--text-secondary)' }}>{health.worker?.active ? 'ACTIVE' : 'INACTIVE'}</strong></span>
              </div>
            )}
            {/* DB Link Indicator */}
            <div className="status-indicator">
              <span className={`status-dot ${firebaseStatus === 'CONNECTED' ? 'active' : firebaseStatus === 'WAITING_FOR_DATA' ? 'warning' : 'critical'}`} />
              <span style={{ fontSize: '0.72rem', color: 'var(--text-secondary)' }}>DB: <strong style={{ color: firebaseStatus === 'CONNECTED' ? 'var(--color-success)' : firebaseStatus === 'WAITING_FOR_DATA' ? 'var(--color-warning)' : 'var(--color-critical)' }}>{firebaseStatus === 'CONNECTED' ? 'ONLINE' : firebaseStatus === 'WAITING_FOR_DATA' ? 'WAITING' : 'OFFLINE'}</strong></span>
            </div>

            {/* Sensor Link Indicator */}
            <div className="status-indicator" title={isSimulated ? 'Data source: simulated telemetry (hardware sensor not connected)' : 'Data source: live ESP32 hardware'}>
              <span className={`status-dot ${isSimulated ? 'simulated' : 'active'}`} />
              <span style={{ fontSize: '0.72rem', color: 'var(--text-secondary)' }}>
                {isSimulated ? 'SOURCE: ' : 'SENSOR: '}
                <strong style={{ color: isSimulated ? 'var(--accent-blue)' : 'var(--color-success)' }}>
                  {isSimulated ? 'SIMULATED' : 'LIVE (ESP32)'}
                </strong>
              </span>
            </div>

            {/* Live Indicator */}
            <div className="status-indicator">
              <span className={`status-dot active pulse`} />
              <span>LIVE</span>
            </div>
            
            <div className="header-time">
              Clock: <span style={{ color: 'var(--text-primary)', fontFamily: 'var(--font-mono)', marginRight: '12px' }}>{systemTime.toLocaleTimeString()}</span>
              Last sync: <span style={{ color: 'var(--text-primary)', fontFamily: 'var(--font-mono)' }}>{lastSyncTime}</span>
            </div>

            <select className="date-selector" defaultValue="today">
              <option value="today">Today, {new Date().toLocaleDateString(undefined, { month: 'short', day: 'numeric' })}</option>
              <option value="yesterday">Yesterday</option>
            </select>

            <button className="theme-button" onClick={() => setTheme(prev => prev === 'dark' ? 'light' : 'dark')}>
              {theme === 'dark' ? (
                <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
                  <circle cx="12" cy="12" r="5" />
                  <line x1="12" y1="1" x2="12" y2="3" />
                  <line x1="12" y1="21" x2="12" y2="23" />
                  <line x1="4.22" y1="4.22" x2="5.64" y2="5.64" />
                  <line x1="18.36" y1="18.36" x2="19.78" y2="19.78" />
                  <line x1="1" y1="12" x2="3" y2="12" />
                  <line x1="21" y1="12" x2="23" y2="12" />
                  <line x1="4.22" y1="19.78" x2="5.64" y2="18.36" />
                  <line x1="18.36" y1="5.64" x2="19.78" y2="4.22" />
                </svg>
              ) : (
                <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
                  <path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z" />
                </svg>
              )}
            </button>
          </div>
        </header>

        {/* Dynamic Safety HUD Banner */}
        <div className={`hud-banner ${hudConfig.hudClass}`}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
            <span style={{ fontSize: '1.25rem' }}>{hudConfig.hudIcon}</span>
            <span>{hudConfig.hudText}</span>
          </div>
          <span className={`hud-pill ${hudConfig.hudClass}`}>{hudConfig.hudPillText}</span>
        </div>

        {/* SECTION RENDERING CONDITIONAL BLOCKS */}
        {activeNav === 'Dashboard' && (
          <>
            {/* TOP KPI SECTION */}
            <section className="kpi-row">
              {oxygenCard}
              {humidityCard}
              {temperatureCard}
            </section>

            {/* MIDDLE SECTION */}
            <section className="middle-grid">
              {trendsCard}
              {forecastCard}
            </section>



            {/* LOWER SECTION */}
            <section className="lower-grid">
              {overviewCard}
              {alertsCard}
              {summaryCard}
            </section>

            {/* FOOTER METRICS AND STATUSES */}
            <section className="status-grid-row">
              {firebaseCard}
              {sensorStatusCard}
              {recCard}
            </section>
          </>
        )}

        {activeNav === 'Live Data' && (
          <div style={{ display: 'flex', flexDirection: 'column', gap: '32px' }}>
            {/* KPI Cards Row */}
            <section className="kpi-row">
              {oxygenCard}
              {humidityCard}
              {temperatureCard}
            </section>
            
            {/* Full size parameter trends */}
            <section style={{ display: 'grid', gridTemplateColumns: '1fr', gap: '24px' }}>
              {trendsCard}
            </section>
          </div>
        )}

        {activeNav === 'Predictions' && (
          <section style={{ display: 'grid', gridTemplateColumns: '1.2fr 1fr', gap: '24px' }}>
            <div style={{ display: 'flex', flexDirection: 'column', gap: '24px' }}>
              {forecastCard}
            </div>
            <div style={{ display: 'flex', flexDirection: 'column', gap: '24px' }}>
              {recCard}
              {overviewCard}
            </div>
          </section>
        )}

        {activeNav === 'Alerts' && (
          <section style={{ display: 'grid', gridTemplateColumns: '1.5fr 1fr', gap: '24px' }}>
            {alertsCard}
            <div style={{ display: 'flex', flexDirection: 'column', gap: '24px' }}>
              {summaryCard}
              {recCard}
            </div>
          </section>
        )}

        {activeNav === 'Reports' && (
          <section style={{ display: 'grid', gridTemplateColumns: '1.5fr 1fr', gap: '24px' }}>
            {summaryCard}
            <div style={{ display: 'flex', flexDirection: 'column', gap: '24px' }}>
              <div className="glass-card" style={{ padding: '24px' }}>
                <h3 className="card-title" style={{ marginBottom: '14px' }}>Telemetry Reports</h3>
                <p style={{ fontSize: '0.85rem', color: 'var(--text-secondary)', marginBottom: '20px', lineHeight: 1.5 }}>
                  Retrieve securely logged chamber telemetry sweeps and system clock statuses. Use the buttons below to export files or print the layout sheets.
                </p>
                <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
                  <button 
                    onClick={() => {
                      window.open('http://localhost:5000/api/sensors/export', '_blank');
                    }}
                    style={{ background: 'rgba(10, 132, 255, 0.08)', border: '1px solid var(--accent-blue)', color: 'var(--accent-blue)', fontSize: '0.85rem', fontWeight: 700, padding: '12px', borderRadius: '8px', cursor: 'pointer', textAlign: 'center' }}
                  >
                    EXPORT CSV ARCHIVE
                  </button>
                  <button 
                    onClick={async () => {
                      const dataStr = "data:text/json;charset=utf-8," + encodeURIComponent(JSON.stringify({ oxygenHistory, tempHistory, humidityHistory }));
                      const downloadAnchor = document.createElement('a');
                      downloadAnchor.setAttribute("href", dataStr);
                      downloadAnchor.setAttribute("download", `telemetry_logs_${Date.now()}.json`);
                      document.body.appendChild(downloadAnchor);
                      downloadAnchor.click();
                      downloadAnchor.remove();
                    }}
                    style={{ background: 'rgba(0, 240, 255, 0.08)', border: '1px solid #00f0ff', color: '#00f0ff', fontSize: '0.85rem', fontWeight: 700, padding: '12px', borderRadius: '8px', cursor: 'pointer', textAlign: 'center' }}
                  >
                    DOWNLOAD RAW TELEMETRY JSON
                  </button>
                  <button 
                    onClick={() => window.print()}
                    style={{ background: 'rgba(255, 255, 255, 0.04)', border: '1px solid var(--border-subtle)', color: 'var(--text-primary)', fontSize: '0.85rem', fontWeight: 700, padding: '12px', borderRadius: '8px', cursor: 'pointer', textAlign: 'center' }}
                  >
                    PRINT REPORT SHEET
                  </button>
                </div>
              </div>
            </div>
          </section>
        )}

        {activeNav === 'Settings' && (
          <section style={{ display: 'grid', gridTemplateColumns: '1.2fr 1fr', gap: '24px' }}>
            {sensorStatusCard}
            <div style={{ display: 'flex', flexDirection: 'column', gap: '24px' }}>
              {firebaseCard}
              <div className="glass-card" style={{ padding: '24px' }}>
                <h3 className="card-title" style={{ marginBottom: '14px' }}>Simulations Control</h3>
                <p style={{ fontSize: '0.8rem', color: 'var(--text-secondary)', marginBottom: '16px', lineHeight: 1.5 }}>
                  Triggers environmental air simulation logs and database drift anomaly handlers.
                </p>
                <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', background: 'rgba(255, 255, 255, 0.02)', padding: '12px 16px', borderRadius: 'var(--border-radius-sm)', border: '1px solid var(--border-subtle)' }}>
                  <div>
                    <span style={{ fontSize: '0.85rem', fontWeight: 700, color: 'var(--text-primary)' }}>SIMULATE BREACH</span>
                    <div style={{ fontSize: '0.72rem', color: 'var(--text-secondary)' }}>Triggers O₂ depletion loop</div>
                  </div>
                  <label className="ios-switch">
                    <input 
                      type="checkbox" 
                      checked={mockAnomaly} 
                      onChange={(e) => setMockAnomaly(e.target.checked)} 
                    />
                    <span className="ios-slider"></span>
                  </label>
                </div>
              </div>
            </div>
          </section>
        )}

      </main>
    </div>
  );
}
