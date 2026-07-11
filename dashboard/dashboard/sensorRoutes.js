const express = require("express");
const router = express.Router();

const sensorController = require("../controllers/sensorController");

// Route mappings delegated directly to the controller layer
router.get("/", sensorController.getLatest);
router.get("/history", sensorController.getHistory);
router.get("/prediction", sensorController.getPrediction);
router.get("/export", sensorController.exportSensorsCSV);

module.exports = router;