import { database } from "../firebase";
import { ref, get, update, query, orderByKey, limitToLast } from "firebase/database";

const API = "https://o2-sentinel-frontend.onrender.com";

const unwrap = async (res: Response) => {
  const json = await res.json();
  return json && json.success && json.data !== undefined ? json.data : json;
};


export const getSensorData = async () => {
  try {
    const sensorRef = ref(database, "sensors/room1/readings");
    const latestQuery = query(sensorRef, orderByKey(), limitToLast(1));
    const snapshot = await get(latestQuery);
    if (snapshot.exists()) {
      const val = snapshot.val();
      const keys = Object.keys(val);
      if (keys.length > 0) {
        return { ...val[keys[0]], exists: true };
      }
    }
    return {
      oxygen: 0,
      temperature: 0,
      humidity: 0,
      timestamp: null,
      exists: false
    };
  } catch (err) {
    console.error("Error fetching latest sensor data:", err);
    return {
      oxygen: 0,
      temperature: 0,
      humidity: 0,
      timestamp: null,
      exists: false
    };
  }
};

export const getAlerts = async () => {
  try {
    const snapshot = await get(ref(database, "alerts/room1"));
    if (snapshot.exists()) {
      const val = snapshot.val();
      return Object.keys(val)
        .map(key => val[key])
        .filter(alert => alert && alert.acknowledged !== true && alert.status !== "initialized");
    }
    return [];
  } catch (err) {
    console.error("Error fetching alerts:", err);
    return [];
  }
};

export const getDevices = async () => {
  const snapshot = await get(ref(database, "devices"));

  if (snapshot.exists()) {
    return snapshot.val();
  }

  return {
    status: "OFFLINE",
    battery: 0,
    lastSeen: null
  };
};

export const getSensorHistory = async () => {
  try {
    const sensorRef = ref(database, "sensors/room1/readings");
    const latestQuery = query(sensorRef, orderByKey(), limitToLast(15));
    const snapshot = await get(latestQuery);
    if (snapshot.exists()) {
      const val = snapshot.val();
      const dataList = Object.keys(val).map(key => val[key]);
      dataList.sort((a: { timestamp?: string }, b: { timestamp?: string }) => {
        const timeA = a.timestamp ? new Date(a.timestamp).getTime() : 0;
        const timeB = b.timestamp ? new Date(b.timestamp).getTime() : 0;
        return timeB - timeA;
      });
      return dataList;
    }
    return [];
  } catch (err) {
    console.error("Error fetching sensor history:", err);
    return [];
  }
};

export const getAlertHistory = async () => {
  try {
    const snapshot = await get(ref(database, "alerts/room1"));

    if (snapshot.exists()) {
      const val = snapshot.val();

      const alerts = Object.keys(val)
        .map(key => val[key])
        .filter(alert => alert && alert.status !== "initialized");

      alerts.sort((a: { timestamp?: string }, b: { timestamp?: string }) => {
          const ta = a.timestamp ? new Date(a.timestamp).getTime() : 0;
          const tb = b.timestamp ? new Date(b.timestamp).getTime() : 0;
          return tb - ta;
      });

      return alerts;
    }

    return [];
  } catch (err) {
    console.error("Error fetching alert history:", err);
    return [];
  }
};

export const acknowledgeAlert = async (id: number) => {
  try {
    const snapshot = await get(ref(database, "alerts/room1"));
    if (snapshot.exists()) {
      const alerts = snapshot.val();
      const key = Object.keys(alerts).find(k => alerts[k].id === id);
      if (key) {
        const alertRef = ref(database, `alerts/room1/${key}`);
        await update(alertRef, { acknowledged: true });
        return { success: true };
      }
    }
    return { success: false, error: "Alert not found" };
  } catch (err) {
    console.error("Error acknowledging alert:", err);
    return { success: false, error: err instanceof Error ? err.message : String(err) };
  }
};

export const getRecommendations = async () => {
  const res = await fetch(`${API}/api/recommendations`);
  return await res.json();
};

export const getSensorPredictions = async () => {
  try {
    const predictionsRef = ref(database, "predictions/room1/readings");
    const latestQuery = query(predictionsRef, orderByKey(), limitToLast(1));
    const snapshot = await get(latestQuery);
    
    if (snapshot.exists()) {
      const val = snapshot.val();
      const keys = Object.keys(val);
      if (keys.length > 0) {
        const latestRecord = val[keys[0]];
        if (latestRecord && (latestRecord.oxygen_forecast_5min !== undefined || latestRecord.oxygen_forecast_10min !== undefined)) {
          return {
            success: true,
            exists: true,
            pred5: latestRecord.oxygen_forecast_5min ?? null,
            pred10: latestRecord.oxygen_forecast_10min ?? null,
            projection: [
              latestRecord.oxygen_forecast_5min ?? null,
              latestRecord.oxygen_forecast_10min ?? null
            ].filter((v): v is number => v !== null),
            confidence: latestRecord.confidence ?? null
          };
        }
      }
    }
    return { success: false, exists: false };
  } catch (err) {
    console.error("Error fetching predictions from Firebase:", err);
    return { success: false, exists: false };
  }
};

export const getSystemStats = async () => {
  const res = await fetch(`${API}/api/stats`);
  return await res.json();
};

export const getSystemHealth = async () => {
  const res = await fetch(`${API}/api/system/health`);
  return await unwrap(res);
};

export const getSystemEvents = async () => {
  const res = await fetch(`${API}/api/system/events`);
  return await unwrap(res);
};

