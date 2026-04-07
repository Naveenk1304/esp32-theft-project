// ================= STATE =================
let apiKey = localStorage.getItem('electricity_api_key');
let last_update = 0;
let mode = "demo"; // demo | real | learning | monitoring
let learned_current = null;
let learning_readings = [];
let charts = {};

// ================= CHART =================
function createChart(id, label, color) {
    const ctx = document.getElementById(id)?.getContext('2d');
    if (!ctx) return null;

    return new Chart(ctx, {
        type: 'line',
        data: {
            labels: [],
            datasets: [{
                label,
                data: [],
                borderColor: color,
                backgroundColor: color + "22",
                tension: 0.4,
                fill: true,
                pointRadius: 0
            }]
        },
        options: {
            responsive: true,
            plugins: {
                legend: { labels: { color: "#8b949e" } }
            },
            scales: {
                x: { display: false },
                y: {
                    ticks: { color: "#8b949e" },
                    grid: { color: "rgba(255,255,255,0.05)" }
                }
            }
        }
    });
}

function initCharts() {
    charts.current = createChart("currentChart", "Current (A)", "#00ff41");
    charts.power = createChart("powerChart", "Power (W)", "#00ff41");
    charts.energy = createChart("energyChart", "Energy (kWh)", "#00ff41");
}

function updateCharts(data) {
    const time = new Date().toLocaleTimeString();

    ["current", "power", "energy"].forEach(key => {
        const chart = charts[key];
        if (!chart) return;

        chart.data.labels.push(time);
        chart.data.datasets[0].data.push(data[key]);

        if (chart.data.labels.length > 20) {
            chart.data.labels.shift();
            chart.data.datasets[0].data.shift();
        }

        chart.update("none");
    });
}

// ================= DATA =================
async function fetchLatestData() {
    try {
        const res = await fetch('/api/latest');
        let data = await res.json();

        if (data.last_update) last_update = data.last_update;

        // DEMO fallback
        if (!data || data.current === 0) {
            data = {
                voltage: 230 + Math.random()*10,
                current: 0.08 + Math.random()*0.02,
                power: 20 + Math.random()*5,
                energy: 10 + Math.random()*5
            };
        }

        processData(data);

    } catch (err) {
        console.error("Fetch error:", err);
    }
}

// ================= CONNECTIVITY =================
function checkConnectivity() {
    const now = Date.now();
    const connected = (last_update > 0 && (now - last_update) < 5000);

    if (connected) {
        if (mode === "demo") mode = "real";
        updateStatusUI(true);
    } else {
        mode = "demo";
        updateStatusUI(false);
    }

    updateModeUI();
}

// ================= UI =================
function updateStatusUI(connected) {
    const sensor = document.getElementById("sensor-status");
    const ai = document.getElementById("ai-status");

    if (connected) {
        if (sensor) sensor.innerText = "CONNECTED";
        if (ai) ai.innerText = "AI READY";
    } else {
        if (sensor) sensor.innerText = "NOT CONNECTED";
        if (ai) ai.innerText = "AI NOT RUNNING";
    }
}

function updateModeUI() {
    const indicator = document.getElementById("indicator-circle");
    const sub = document.getElementById("indicator-subtext");

    const setup = document.getElementById("setupBtn");
    const learn = document.getElementById("learnBtn");
    const reset = document.getElementById("resetBtn");

    if (!indicator) return;

    // hide all
    setup && (setup.style.display = "none");
    learn && (learn.style.display = "none");
    reset && (reset.style.display = "none");

    indicator.classList.remove("theft");

    if (mode === "demo") {
        indicator.innerText = "DEMO MODE";
        sub.innerText = "Setup API Key to enable real monitoring";
        setup && (setup.style.display = "block");
    }
    else if (mode === "real") {
        indicator.innerText = "READY";
        sub.innerText = "Click Learn Pattern to start AI";
        learn && (learn.style.display = "block");
    }
    else if (mode === "learning") {
        indicator.innerText = "LEARNING...";
        sub.innerText = "Collecting data...";
    }
    else if (mode === "monitoring") {
        indicator.innerText = "MONITORING";
        sub.innerText = "System Normal";
        reset && (reset.style.display = "block");
    }
}

// ================= DATA PROCESS =================
function processData(data) {
    document.getElementById("val-voltage").innerText = data.voltage.toFixed(1);
    document.getElementById("val-current").innerText = data.current.toFixed(2);
    document.getElementById("val-power").innerText = data.power.toFixed(1);
    document.getElementById("val-energy").innerText = data.energy.toFixed(2);

    updateCharts(data);

    if (mode === "learning") {
        learning_readings.push(data.current);

        if (learning_readings.length >= 50) {
            learned_current = learning_readings.reduce((a,b)=>a+b,0)/50;
            mode = "monitoring";
            alert("Learning Completed!");
        }
    }

    if (mode === "monitoring" && learned_current) {
        if (data.current > learned_current + 0.02) {
            triggerTheft();
        } else {
            resetAlert();
        }
    }
}

// ================= ALERT =================
function triggerTheft() {
    const indicator = document.getElementById("indicator-circle");
    indicator.classList.add("theft");
    indicator.innerText = "⚠️ THEFT";
}

function resetAlert() {
    const indicator = document.getElementById("indicator-circle");
    indicator.classList.remove("theft");
}

// ================= ACTIONS =================
function startLearning() {
    mode = "learning";
    learning_readings = [];
}

function resetPattern() {
    mode = "real";
    learned_current = null;
}

// ================= MODAL =================
function openModal() {
    document.getElementById("setupModal").style.display = "block";
}
function closeModal() {
    document.getElementById("setupModal").style.display = "none";
}

// ================= INIT =================
window.onload = () => {
    initCharts();
    updateModeUI();

    const setup = document.getElementById("setupBtn");
    const learn = document.getElementById("learnBtn");
    const reset = document.getElementById("resetBtn");

    setup && setup.addEventListener("click", openModal);
    learn && learn.addEventListener("click", startLearning);
    reset && reset.addEventListener("click", resetPattern);

    setInterval(fetchLatestData, 2000);
    setInterval(checkConnectivity, 1000);
};