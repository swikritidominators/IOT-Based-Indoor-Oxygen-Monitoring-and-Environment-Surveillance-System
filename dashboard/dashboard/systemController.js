const fs = require("fs");
const path = require("path");

/**
 * GET /api/system/health
 * Checks server memory, uptime, DB size, and background worker state
 */
async function getHealth(req, res) {
  try {
    // 1. Server Uptime
    const uptime = process.uptime();

    // 2. Process Memory usage
    const memory = process.memoryUsage();

    // 3. Database file size - set to 0 as SQLite is removed
    const dbSize = 0;

    // 4. Background Logging Worker Check - set to false as SQLite background worker is removed
    const workerActive = false;

    return res.json({
      success: true,
      data: {
        status: "HEALTHY",
        uptime,
        memory: {
          rss: memory.rss,
          heapTotal: memory.heapTotal,
          heapUsed: memory.heapUsed,
        },
        database: {
          size: dbSize,
          path: "database.db (removed)",
        },
        worker: {
          active: workerActive,
        },
      },
    });
  } catch (err) {
    console.error("Controller Error (getHealth):", err);
    return res.status(500).json({
      success: false,
      error: "Failed to query system health parameters",
    });
  }
}

/**
 * GET /api/system/events
 * Fetches system event timeline logs
 */
async function getEvents(req, res) {
  try {
    // Return empty timeline array since database is removed
    return res.json({
      success: true,
      data: [],
    });
  } catch (err) {
    console.error("Controller Error (getEvents):", err);
    return res.status(500).json({
      success: false,
      error: "Failed to fetch system events log timeline",
    });
  }
}

/**
 * GET /api/system
 * Retrieves overall system service status metadata
 */
async function getSystemStatus(req, res) {
  try {
    return res.json({
      success: true,
      data: {
        status: "ONLINE",
        name: "O₂ Sentinel Environmental Monitoring System API",
        version: "1.0.0",
        timestamp: new Date().toISOString()
      }
    });
  } catch (err) {
    console.error("Controller Error (getSystemStatus):", err);
    return res.status(500).json({
      success: false,
      error: "Failed to fetch overall system status",
    });
  }
}

module.exports = {
  getHealth,
  getEvents,
  getSystemStatus,
};
