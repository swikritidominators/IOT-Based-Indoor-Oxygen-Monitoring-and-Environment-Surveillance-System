/**
 * Evaluates telemetry readings and outputs prioritized suggestions
 */
function generateRecommendations(sensorData) {
  const recommendations = [];

  // 1. Oxygen Metrics
  if (sensorData.oxygen < 20.0) {
    recommendations.push({
      metric: "oxygen",
      priority: "high",
      text: "Increase fresh air ventilation immediately to offset hypoxia risks.",
      action: "ACTIVATE_VENTILATION"
    });
    recommendations.push({
      metric: "oxygen",
      priority: "medium",
      text: "Reduce room occupancy limit and clear non-essential lab personnel.",
      action: "REDUCE_OCCUPANCY"
    });
    recommendations.push({
      metric: "oxygen",
      priority: "medium",
      text: "Verify fresh air supply dampers are fully open on primary HVAC units.",
      action: "CHECK_HVAC_DAMPERS"
    });
  }

  // 2. Temperature Metrics
  if (sensorData.temperature > 28) {
    recommendations.push({
      metric: "temperature",
      priority: sensorData.temperature > 32 ? "high" : "medium",
      text: "Inspect active cooling systems and HVAC compressor units.",
      action: "CHECK_COOLING_COMPRESSOR"
    });
    recommendations.push({
      metric: "temperature",
      priority: "low",
      text: "Reduce chamber thermal load by powering down non-critical diagnostics equipment.",
      action: "REDUCE_THERMAL_LOAD"
    });
  }

  // 3. Humidity Metrics
  if (sensorData.humidity > 55) {
    recommendations.push({
      metric: "humidity",
      priority: sensorData.humidity > 60 ? "high" : "medium",
      text: "Enable secondary dehumidification loops and verify condensed drain lines.",
      action: "ACTIVATE_DEHUMIDIFIERS"
    });
    recommendations.push({
      metric: "humidity",
      priority: "low",
      text: "Verify auxiliary exhaust ventilation flow lines are unblocked.",
      action: "VERIFY_EXHAUST_DAMPERS"
    });
  }

  return recommendations;
}

module.exports = { generateRecommendations };
