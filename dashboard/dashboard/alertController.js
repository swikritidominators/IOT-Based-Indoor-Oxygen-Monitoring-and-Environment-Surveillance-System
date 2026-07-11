/**
 * GET /api/alerts
 * Fetches all active (unacknowledged) alerts
 */
async function getActive(req, res) {
  try {
    // Return empty array since database is removed
    return res.json({
      success: true,
      data: []
    });
  } catch (err) {
    console.error("Controller Error (getActive):", err);
    return res.status(500).json({
      success: false,
      error: "Failed to fetch active alerts from database",
    });
  }
}

/**
 * GET /api/alerts/history
 * Fetches historical alert logs with optional query filters (severity, status, time, search) and limit
 */
async function getHistory(req, res) {
  try {
    let limit = 50; // default history limit
    let page = 1; // default page

    if (req.query.limit !== undefined) {
      const parsedLimit = parseInt(req.query.limit, 10);
      if (isNaN(parsedLimit) || parsedLimit <= 0 || parsedLimit > 200 || String(parsedLimit) !== req.query.limit.trim()) {
        return res.status(400).json({
          success: false,
          error: "Invalid limit parameter. Must be an integer between 1 and 200.",
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

    // Return empty array and 0 pagination metadata as SQLite database is removed
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
      error: "Failed to retrieve alert logs from database",
    });
  }
}

/**
 * PATCH /api/alerts/:id/acknowledge
 * Sets acknowledged to true (1) for a specific alert ID
 */
async function acknowledge(req, res) {
  try {
    const id = parseInt(req.params.id, 10);
    if (isNaN(id) || id <= 0) {
      return res.status(400).json({
        success: false,
        error: "Invalid alert ID. Must be a positive integer.",
      });
    }

    // Return mock success since database is removed
    return res.json({
      success: true,
      data: { id, message: `Alert ID ${id} acknowledged successfully (placeholder)` }
    });
  } catch (err) {
    console.error("Controller Error (acknowledge):", err);
    return res.status(500).json({
      success: false,
      error: "Failed to acknowledge alert in database",
    });
  }
}

async function exportAlertsCSV(req, res) {
  try {
    res.setHeader("Content-Type", "text/csv");
    res.setHeader("Content-Disposition", "attachment; filename=alerts_export.csv");

    res.write("id,type,severity,message,oxygen,temperature,humidity,timestamp,status,acknowledged,resolved_at\n");
    // SQLite removed, return empty data (only header)
    res.end();
  } catch (err) {
    console.error("Controller Error (exportAlertsCSV):", err);
    if (!res.headersSent) {
      return res.status(500).json({ error: "Failed to export alert logs" });
    }
  }
}

module.exports = {
  getActive,
  getHistory,
  acknowledge,
  exportAlertsCSV,
};
