const { getSensorData } = require("../services/sensorSimulator");
const { generateRecommendations } = require("../services/recommendationEngine");

/**
 * GET /api/recommendations
 * Resolves active safety suggestions based on current sensor readings
 */
async function getLiveRecommendations(req, res) {
  try {
    const currentReading = getSensorData();
    if (!currentReading) {
      return res.status(503).json({
        error: "Sensor telemetry temporarily offline",
      });
    }

    const suggestions = generateRecommendations(currentReading);

    return res.json({
      success: true,
      recommendations: suggestions
    });
  } catch (err) {
    console.error("Controller Error (getLiveRecommendations):", err);
    return res.status(500).json({
      error: "Internal server error generating system recommendations",
    });
  }
}

module.exports = {
  getLiveRecommendations,
};
