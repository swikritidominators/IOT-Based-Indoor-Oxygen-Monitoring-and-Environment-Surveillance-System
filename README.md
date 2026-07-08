🚀 DRDO Internship Project 2026

An intelligent IoT-powered environmental monitoring system that continuously measures Oxygen Concentration, Temperature, and Humidity, uploads data to Firebase Realtime Database, performs Machine Learning-based prediction & anomaly detection, and visualizes everything on a real-time dashboard.



📌 Overview

This project was developed during the DRDO (Defence Research and Development Organisation) Summer Internship 2026 at Centre for Fire, Explosive and Environment Safety (CFEES).
The objective of this project is to build an intelligent environmental surveillance system capable of continuously monitoring oxygen concentration, temperature, and humidity inside enclosed environments. The system leverages ESP32, Firebase Realtime Database, Machine Learning, and a React-based dashboard to provide live monitoring, predictive analytics, anomaly detection, and intelligent recommendations.



🌟 Key Features

🌡 Real-Time Temperature Monitoring
💧 Real-Time Humidity Monitoring
🫁 Continuous Oxygen Concentration Monitoring
☁ Firebase Realtime Database Integration
📡 Wi-Fi Enabled ESP32 Communication
🔋 Portable Battery-Powered Hardware
📺 16×2 LCD Live Display
🚨 Automatic Alert Generation
🤖 Machine Learning-Based Oxygen Prediction
📈 Historical Trend Analysis
⚠ Intelligent Anomaly Detection
🌐 Interactive Web Dashboard




🏗 System Architecture

                 Sensors
        ┌───────────────────────────┐
        │ DHT11 + AOF1010 Oxygen    │
        └──────────────┬────────────┘
                       │
                  ESP32 Controller
                       │
                Wi-Fi Communication
                       │
         Firebase Realtime Database
                       │
        ┌──────────────┴──────────────┐
        │                             │
 Machine Learning               React Dashboard
(Random Forest, XGBoost,      Live Monitoring,
Isolation Forest, CUSUM)      Alerts, Forecast





⚙ Working Flow

DHT11 + Oxygen Sensor
          │
          ▼
       ESP32
          │
          ▼
   Firebase Database
          │
          ▼
 Python ML Pipeline
          │
          ▼
Prediction & Alerts
          │
          ▼
 React Dashboard




 🤖 Machine Learning
The project incorporates multiple Machine Learning algorithms for predictive analytics.


Prediction Models
🌲 Random Forest Regression
⚡ XGBoost Regression

Anomaly Detection
🚨 Isolation Forest
📈 CUSUM Algorithm

Used For
Oxygen Prediction
Trend Analysis
Intelligent Recommendations
Hazard Detection
Environmental Forecasting



📊 Dashboard Features

📈 Live Sensor Readings
📉 Historical Graphs
🤖 Oxygen Forecast
🚨 Alert Management
📋 Recommendation Engine
📊 Environmental Statistics
☁ Firebase Synchronization
