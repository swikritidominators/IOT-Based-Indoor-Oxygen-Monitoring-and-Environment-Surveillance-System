# O₂ Sentinel — Environmental Monitoring Dashboard

O₂ Sentinel is a state-of-the-art, premium environmental telemetry dashboard built with **React**, **TypeScript**, and **Vite**. Inspired by clean, premium Apple/iOS dark-mode aesthetics, this dashboard provides real-time monitoring, analytics, and forecast metrics for vital atmospheric conditions: **Oxygen Concentration**, **Temperature**, and **Humidity**.

---

## 🌟 Key Features

### 1. Premium iOS-Inspired Design System (`src/index.css`)
*   **Aesthetics**: Glassmorphism (`backdrop-filter: blur`), dark mode palettes, deep rich backgrounds, and harmonious pastel-saturated accents (`system-blue`, `system-green`, `system-orange`, `system-red`).
*   **Micro-Animations**: Custom loader animations, smooth state transitions, pulsing status beacons, warning banners, and button interactions.
*   **Responsive Layout**: Adapts gracefully from mobile viewports to large-screen dashboards, transitioning components seamlessly into stacking column layouts.

### 2. Interactive Telemetry Simulation (`src/App.tsx`)
*   **Nominal Telemetry Drift**: Naturally drifts and fluctuates telemetry values every 1.5 seconds.
*   **Simulate Drift/Anomaly Toggle**: Allows users to force-drift the variables into warning and danger zones to test safety protocols.
*   **Dynamic Alarm Banner**: Displays alerts with pulsating borders when thresholds are breached.
*   **Live Digital Log Console**: Features an auto-scrolling terminal feed documenting every telemetry sync checklist event.

### 3. Lightweight Custom SVG Data Visualizations
*   **Trend Sparklines (`src/dashboard/components/TrendChart.jsx`)**: Responsive SVG line graphs with custom time-ranges (`5 min`, `10 min`), shaded acceptable safe-zone bands, grid lines, and real-time pulsing cursor points.
*   **Predictive Analysis Chart (`src/dashboard/components/PredictionChart.jsx`)**: Maps past historical data against forward-looking projections (+30 and +60 minutes) bounded by a custom-shaded statistical confidence funnel showing widening variance in future projections.

### 4. Modular Dashboard Components
*   **`Loader.tsx`**: A cinematic startup loader that simulates device/sensor calibration stages with responsive status texts and animated loading arcs.
*   **Large Oxygen Display**: Features a prominent centered card layout displaying real-time oxygen values, safety limits, and status alarms.
*   **`StatusCard.jsx`**: Visually maps specific metric status thresholds (Safe, Warning, Danger), incorporating radial layout meters, custom parameter SVGs, and threshold ranges.

---

## 🛠️ Technology Stack
*   **Core Framework**: React 19
*   **Language**: TypeScript & Modern ES6+ JavaScript
*   **Build Tool**: Vite 8 & npm
*   **Styles**: Pure CSS3 (custom custom-properties / variables, no Tailwind CSS or heavy external libraries)
*   **Charts**: Custom, inline responsive SVG generation (zero bulky graphing library dependencies)
*   **Real-time Database**: Firebase Realtime Database (for active alarm subscriptions and live sensor feeds)


---

## 📂 Project Architecture

```
o2-sentinel-frontend/
├── public/                 # Static assets (Favicons, SVG vectors)
├── src/
│   ├── dashboard/
│   │   └── components/
│   │       ├── Loader.tsx          # Systems-check initialization overlay
│   │       ├── StatusCard.jsx      # Metrics panels showing O2, Temp, Hum
│   │       ├── TrendChart.jsx      # Lightweight native SVG line charts
│   │       └── PredictionChart.jsx # Future confidence interval projection charts
│   ├── App.tsx             # Main coordinator, telemetry state and rules engine
│   ├── index.css           # CSS variables, utility tokens, and iOS look & feel
│   └── main.tsx            # Application entrypoint
├── index.html              # HTML shell & SEO configuration
├── vite.config.ts          # Vite bundling directives
├── tsconfig.json           # Compiler rules
└── package.json            # Scripts and dependencies
```

---

## 🚀 Setup & Execution

### 1. Installation
Clone the repository and install the development dependencies:
```bash
npm install
```

### 2. Configure Environment Variables
Create a `.env` file in the root of the `frontend/` directory and populate it with your Firebase configuration variables:
```env
VITE_FIREBASE_API_KEY=your_api_key
VITE_FIREBASE_AUTH_DOMAIN=your_auth_domain
VITE_FIREBASE_DATABASE_URL=your_database_url
VITE_FIREBASE_PROJECT_ID=your_project_id
VITE_FIREBASE_STORAGE_BUCKET=your_storage_bucket
VITE_FIREBASE_MESSAGING_SENDER_ID=your_messaging_sender_id
VITE_FIREBASE_APP_ID=your_app_id
VITE_FIREBASE_MEASUREMENT_ID=your_measurement_id
```

### 3. Start Local Dev Server
Launch Vite's hot-reloading development environment:
```bash
npm run dev
```
Open [http://localhost:5173](http://localhost:5173) in your browser.

### 3. Build & Compile for Production
Bundle and optimize assets for deployment:
```bash
npm run build
```
You can review the build output locally with:
```bash
npm run preview
```

### 4. Lint and Quality Check
Verify code formatting against compiler and style configs:
```bash
npm run lint
```
