const express = require("express");
const router = express.Router();

const statsController = require("../controllers/statsController");

// Mount GET / -> controller to retrieve aggregated stats
router.get("/", statsController.getSystemStats);

module.exports = router;
