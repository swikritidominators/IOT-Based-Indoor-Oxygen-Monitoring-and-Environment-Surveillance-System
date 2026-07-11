let oxygen = 20.8;
let temperature = 25;
let humidity = 48;

function random(min, max) {
  return Math.random() * (max - min) + min;
}

setInterval(() => {
  oxygen += random(-0.15, 0.15);
  temperature += random(-0.5, 0.5);
  humidity += random(-2, 2);

  oxygen = Math.max(18.5, Math.min(21.5, oxygen));
  temperature = Math.max(20, Math.min(40, temperature));
  humidity = Math.max(30, Math.min(90, humidity));
}, 5000);

function getSensorData() {
  return {
    oxygen: Number(oxygen.toFixed(2)),
    temperature: Number(temperature.toFixed(1)),
    humidity: Number(humidity.toFixed(0)),
    timestamp: new Date().toISOString(),
  };
}

module.exports = {
  getSensorData,
};