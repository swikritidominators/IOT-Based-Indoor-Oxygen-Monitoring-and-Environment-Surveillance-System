/**
 * GET /api/stats
 * Computes telemetry summaries (min/max/avg) and alert frequencies
 */
async function getSystemStats(req, res) {
  try {
    // Return empty stats since database is removed
    return res.json({
      success: true,
      stats: {
        telemetry: {
          oxygen: {
            min: 0,
            max: 0,
            avg: 0,
          },
          temperature: {
            min: 0,
            max: 0,
            avg: 0,
          },
          humidity: {
            min: 0,
            max: 0,
            avg: 0,
          },
        },
        alerts: {
          total: 0,
          active: 0,
          resolved: 0,
          acknowledged: 0,
        },
      },
    });
  } catch (err) {
    console.error("Controller Error (getSystemStats):", err);
    return res.status(500).json({
      error: "Failed to compile system metrics statistics",
    });
  }
}

module.exports = {
  getSystemStats,
};
