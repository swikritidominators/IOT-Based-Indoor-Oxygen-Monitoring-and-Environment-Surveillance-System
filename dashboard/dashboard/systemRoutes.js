const express = require("express");
const router = express.Router();

const systemController = require("../controllers/systemController");

// Mount GET / -> systemController.getSystemStatus
router.get("/", systemController.getSystemStatus);

// Mount GET /health -> systemController.getHealth
router.get("/health", systemController.getHealth);

// Mount GET /events -> systemController.getEvents
router.get("/events", systemController.getEvents);

module.exports = router;
