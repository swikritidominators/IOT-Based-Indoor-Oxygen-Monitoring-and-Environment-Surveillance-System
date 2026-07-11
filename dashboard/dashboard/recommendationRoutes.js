const express = require("express");
const router = express.Router();

const recommendationController = require("../controllers/recommendationController");

// Mount GET / -> controller to get live recommendation arrays
router.get("/", recommendationController.getLiveRecommendations);

module.exports = router;
