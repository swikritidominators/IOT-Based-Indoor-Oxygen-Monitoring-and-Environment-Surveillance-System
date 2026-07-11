function generateAlerts(sensorData) {
  const alerts = [];

  // Oxygen Alerts (Operational Limits: 19.5% - 23.5%)
  if (sensorData.oxygen < 19.5 || sensorData.oxygen > 23.5) {
    alerts.push({
      type: "oxygen",
      severity: "critical",
      title: "Critical Oxygen Level",
      message: `Oxygen concentration is critical: ${sensorData.oxygen.toFixed(2)}%. Immediate action required.`,
      recommendation: "Increase ventilation immediately.",
      timestamp: new Date().toISOString()
    });
  } else if (sensorData.oxygen < 20.0 || sensorData.oxygen > 23.0) {
    alerts.push({
      type: "oxygen",
      severity: "warning",
      title: "Oxygen Level Warning",
      message: `Oxygen concentration is abnormal: ${sensorData.oxygen.toFixed(2)}%.`,
      recommendation: "Monitor oxygen closely.",
      timestamp: new Date().toISOString()
    });
  }

  // Temperature Alerts (Operational Limits: <= 28°C safe, <= 32°C warning)
  if (sensorData.temperature > 32) {
    alerts.push({
      type: "temperature",
      severity: "critical",
      title: "Critical Temperature",
      message: `Chamber core temperature critical: ${sensorData.temperature.toFixed(1)}°C.`,
      recommendation: "Activate cooling system immediately.",
      timestamp: new Date().toISOString()
    });
  } else if (sensorData.temperature > 28) {
    alerts.push({
      type: "temperature",
      severity: "warning",
      title: "High Temperature Warning",
      message: `Chamber core temperature high: ${sensorData.temperature.toFixed(1)}°C.`,
      recommendation: "Verify ventilation and thermal load.",
      timestamp: new Date().toISOString()
    });
  }

  // Humidity Alerts (Operational Limits: <= 55% safe, <= 60% warning)
  if (sensorData.humidity > 60) {
    alerts.push({
      type: "humidity",
      severity: "critical",
      title: "Critical Humidity",
      message: `Chamber humidity level critical: ${sensorData.humidity.toFixed(0)}%.`,
      recommendation: "Activate auxiliary dehumidifier loops.",
      timestamp: new Date().toISOString()
    });
  } else if (sensorData.humidity > 55) {
    alerts.push({
      type: "humidity",
      severity: "warning",
      title: "High Humidity Warning",
      message: `Chamber humidity level high: ${sensorData.humidity.toFixed(0)}%.`,
      recommendation: "Monitor dehumidifiers and condensate drains.",
      timestamp: new Date().toISOString()
    });
  }

  return alerts;
}

module.exports = { generateAlerts };