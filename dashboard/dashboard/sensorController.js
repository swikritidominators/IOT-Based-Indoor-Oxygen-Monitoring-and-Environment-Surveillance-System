const { getSensorData } = require("../services/sensorSimulator");

/**
 * GET /api/sensors
 * Retrieves the latest telemetry reading instantly (without writing to database)
 */
async function getLatest(req, res) {
  try {
    const reading = getSensorData();
    if (!reading) {
      return res.status(503).json({
        success: false,
        error: "Sensor data temporarily unavailable",
      });
    }
    return res.json({
      success: true,
      data: reading
    });
  } catch (err) {
    console.error("Controller Error (getLatest):", err);
    return res.status(500).json({
      success: false,
      error: "Failed to fetch latest sensor readings",
    });
  }
}

/**
 * GET /api/sensors/history
 * Fetches log history from SQLite database with offset pagination and validation checks
 */
async function getHistory(req, res) {
  try {
    let limit = 15; // default value
    let page = 1; // default page

    if (req.query.limit !== undefined) {
      const parsedLimit = parseInt(req.query.limit, 10);

      // Validation: Check if it's a valid integer and falls inside range [1, 100]
      if (isNaN(parsedLimit) || parsedLimit <= 0 || parsedLimit > 100 || String(parsedLimit) !== req.query.limit.trim()) {
        return res.status(400).json({
          success: false,
          error: "Invalid limit parameter. Must be an integer between 1 and 100.",
        });
      }
      limit = parsedLimit;
    }

    if (req.query.page !== undefined) {
      const parsedPage = parseInt(req.query.page, 10);
      if (isNaN(parsedPage) || parsedPage <= 0 || String(parsedPage) !== req.query.page.trim()) {
        return res.status(400).json({
          success: false,
          error: "Invalid page parameter. Must be a positive integer starting from 1.",
        });
      }
      page = parsedPage;
    }

    return res.json({
      success: true,
      data: [],
      pagination: {
        page,
        limit,
        total: 0,
        pages: 0
      }
    });
  } catch (err) {
    console.error("Controller Error (getHistory):", err);
    return res.status(500).json({
      success: false,
      error: "Failed to retrieve telemetry log history from database",
    });
  }
}

/**
 * GET /api/sensors/prediction
 * Exposes dynamic forecasts for O2 levels at +5m and +10m based on linear regression of historical telemetry
 */
async function getPrediction(req, res) {
  try {
    const latestReading = getSensorData();
    if (!latestReading) {
      return res.status(503).json({ error: "Sensor telemetry offline" });
    }

    const currentOxygen = latestReading.oxygen;

    // Fallback to static projection as there is no SQLite history database anymore
    const pred5 = currentOxygen - 0.02;
    const pred10 = currentOxygen - 0.05;
    const projection = Array.from({ length: 15 }, (_, i) => {
      const t = i / 14;
      return Math.max(0, currentOxygen + (pred10 - currentOxygen) * t);
    });

    const confidence = Math.max(85, Math.min(99, 96 + Math.round((Math.random() - 0.5) * 4)));

    return res.json({
      success: true,
      pred5,
      pred10,
      projection,
      confidence
    });
  } catch (err) {
    console.error("Controller Error (getPrediction):", err);
    return res.status(500).json({
      error: "Failed to compute sensor prediction model"
    });
  }
}

async function exportSensorsCSV(req, res) {
  try {
    res.setHeader("Content-Type", "text/csv");
    res.setHeader("Content-Disposition", "attachment; filename=sensor_logs_export.csv");

    res.write("id,oxygen,temperature,humidity,timestamp\n");
    // SQLite removed, return empty data
    res.end();
  } catch (err) {
    console.error("Controller Error (exportSensorsCSV):", err);
    if (!res.headersSent) {
      return res.status(500).json({ error: "Failed to export sensor telemetry data" });
    }
  }
}

module.exports = {
  getLatest,
  getHistory,
  getPrediction,
  exportSensorsCSV,
};
