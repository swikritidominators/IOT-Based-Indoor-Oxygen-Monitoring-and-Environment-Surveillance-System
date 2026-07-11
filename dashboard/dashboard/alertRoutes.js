const express = require("express");
const router = express.Router();

const alertController = require("../controllers/alertController");

// Endpoint definitions routed directly to controller handlers
router.get("/", alertController.getActive);
router.get("/history", alertController.getHistory);
router.get("/export", alertController.exportAlertsCSV);
router.patch("/:id/acknowledge", alertController.acknowledge);

module.exports = router;