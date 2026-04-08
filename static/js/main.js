// State variables
let apiKey = localStorage.getItem('electricity_api_key');
let currentEmail = localStorage.getItem('electricity_email');
let last_update = 0;
let mode = "demo"; // demo | real | learning | monitoring
let learned_current = null;
let learning_readings = [];
let charts = {};
let theftLogs = [];
let theftTimer = null;

// Chart.js Configuration
function createChart(id, label, color) {
    const canvas = document.getElementById(id);
    if (!canvas) return null;
    const ctx = canvas.getContext('2d');
    return new Chart(ctx, {
        type: 'line',
        data: {
            labels: [],
            datasets: [{
                label: label,
                data: [],
                borderColor: color,
                backgroundColor: color + '22',
                borderWidth: 2,
                pointRadius: 0,
                fill: true,
                tension: 0.4
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            scales: {
                x: { display: false },
                y: { 
                    beginAtZero: true,
                    grid: { color: 'rgba(255, 255, 255, 0.05)' },
                    ticks: { color: '#8b949e' }
                }
            },
            plugins: {
                legend: { display: true, labels: { color: '#8b949e' } }
            }
        }
    });
}

// Initializing Charts
function initCharts() {
    charts.current = createChart('currentChart', 'Current (A)', '#00ff41');
    charts.power = createChart('powerChart', 'Power (W)', '#00ff41');
    charts.energy = createChart('energyChart', 'Energy (kWh)', '#00ff41');
}

function updateCharts(data) {
    const timeLabel = new Date().toLocaleTimeString();
    
    ['current', 'power', 'energy'].forEach(key => {
        const chart = charts[key];
        if (!chart) return;
        chart.data.labels.push(timeLabel);
        chart.data.datasets[0].data.push(data[key]);
        
        // Keep only last 20 points
        if (chart.data.labels.length > 20) {
            chart.data.labels.shift();
            chart.data.datasets[0].data.shift();
        }
        
        chart.update('none');
    });
}

// Data Handling
async function fetchLatestData() {
    try {
        const response = await fetch('/api/latest');
        const result = await response.json();

        // Update last_update from backend
        if (result.last_update) {
            last_update = result.last_update;
        }

        processData(result);

    } catch (e) {
        console.error("Polling error:", e);
    }
}

// Connectivity Check Logic
function checkConnectivity() {
    const now = Date.now();
    const isConnected = last_update > 0 && (now - last_update) < 5000;
    
    // Update Mode if not in learning or monitoring
    if (mode === "demo" || mode === "real") {
        mode = isConnected ? "real" : "demo";
    }
    
    updateStatusUI(isConnected);
    updateModeUI();
}

function updateStatusUI(connected) {
    const sensorDot = document.getElementById('sensor-dot');
    const sensorStatus = document.getElementById('sensor-status');
    const aiDot = document.getElementById('ai-dot');
    const aiStatus = document.getElementById('ai-status');

    if (connected) {
        if (sensorDot) sensorDot.classList.add('connected');
        if (sensorStatus) sensorStatus.innerText = "CONNECTED";
        if (aiDot) aiDot.classList.add('connected');
        if (aiStatus) aiStatus.innerText = (mode === "monitoring") ? "MONITORING ACTIVE" : (mode === "learning" ? "LEARNING..." : "AI READY");
    } else {
        if (sensorDot) sensorDot.classList.remove('connected');
        if (sensorStatus) sensorStatus.innerText = "NOT CONNECTED";
        if (aiDot) aiDot.classList.remove('connected');
        if (aiStatus) aiStatus.innerText = "AI: NOT RUNNING";
    }
}

function updateModeUI() {
    const indicator = document.getElementById('indicator-circle');
    const subtext = document.getElementById('indicator-subtext');
    const setupBtn = document.getElementById('setupBtn');
    const learnBtn = document.getElementById('learnBtn');
    const resetBtn = document.getElementById('resetBtn');
    const learningContainer = document.getElementById('learning-container');

    // Default: Hide all buttons and containers
    setupBtn.style.display = "none";
    learnBtn.style.display = "none";
    resetBtn.style.display = "none";
    learningContainer.style.display = "none";
    
    // Default text color and animation
    indicator.classList.remove('theft', 'learning-blink');

    if (mode === "demo") {
        indicator.innerText = "DEMO MODE";
        subtext.innerText = "Setup API Key to enable real monitoring";
        subtext.style.color = "#8b949e";
        setupBtn.style.display = "block";
    } 
    else if (mode === "real") {
        indicator.innerText = "READY";
        subtext.innerText = "Click Learn Pattern to start AI";
        subtext.style.color = "#8b949e";
        learnBtn.style.display = "block";
    } 
    else if (mode === "learning") {
        indicator.innerText = "LEARNING...";
        indicator.classList.add('learning-blink');
        subtext.innerText = "Collecting baseline data...";
        subtext.style.color = "var(--neon-green)";
        learningContainer.style.display = "block";
        // Buttons stay hidden in learning
    } 
    else if (mode === "monitoring") {
        // If theft is detected, processData will handle the UI
        // This is the default monitoring state
        if (!indicator.classList.contains('theft')) {
            indicator.innerText = "MONITORING";
            subtext.innerText = "System Operating Correctly";
            subtext.style.color = "#8b949e";
        }
        resetBtn.style.display = "block";
    }
}

function processData(data) {
    document.getElementById('val-voltage').innerText = Number(data.voltage).toFixed(1);
    document.getElementById('val-current').innerText = Number(data.current).toFixed(2);
    document.getElementById('val-power').innerText = Number(data.power).toFixed(1);
    document.getElementById('val-energy').innerText = Number(data.energy).toFixed(2);

    updateCharts(data);

    if (mode === "learning") {
        learning_readings.push(Number(data.current));
        const progress = (learning_readings.length / 50) * 100;
        document.getElementById('learning-progress').style.width = progress + "%";
        
        if (learning_readings.length >= 50) {
            const sum = learning_readings.reduce((a, b) => a + b, 0);
            learned_current = sum / learning_readings.length;
            mode = "monitoring";
            learning_readings = [];
            showToast("Learning Complete! Baseline established.");
            updateModeUI();
        }
    } 
    else if (mode === "monitoring") {
        const currentNow = Number(data.current);
        if (currentNow > learned_current + 0.02) {
            triggerAlert(learned_current, currentNow);
        } else {
            resetAlert();
        }
    }
}

function triggerAlert(learned, current) {
    const indicator = document.getElementById('indicator-circle');
    const subtext = document.getElementById('indicator-subtext');
    
    indicator.classList.add('theft');
    indicator.innerText = "THEFT DETECTED";
    subtext.innerText = "CRITICAL: ABNORMAL POWER CONSUMPTION";
    subtext.style.color = "#ff3131";

    // Clear auto-email timer if theft resumes
    if (theftTimer) {
        clearTimeout(theftTimer);
        theftTimer = null;
    }
    
    // Add to theft logs if not already showing
    document.getElementById('theft-table-container').style.display = "block";
    const tbody = document.getElementById('theft-logs-body');
    
    // Only add if last log was more than 10 seconds ago to avoid spam
    const lastRow = tbody.firstElementChild;
    const now = new Date();
    if (!lastRow || (now - new Date(lastRow.dataset.time) > 10000)) {
        const row = document.createElement('tr');
        row.dataset.time = now.toISOString();
        row.style.borderBottom = "1px solid #30363d";
        row.innerHTML = `
            <td style="padding: 10px;">${now.toLocaleTimeString()}</td>
            <td style="padding: 10px;">${learned.toFixed(2)}</td>
            <td style="padding: 10px; color: #ff3131;">${current.toFixed(2)}</td>
            <td style="padding: 10px; color: #ff3131;">+${(current - learned).toFixed(2)}</td>
        `;
        tbody.prepend(row);
        
        // Add to array for email
        theftLogs.push({
            time: now.toLocaleTimeString(),
            learned_current: learned.toFixed(2),
            current: current.toFixed(2),
            difference: (current - learned).toFixed(2)
        });

        showToast("⚠️ Electricity Theft Detected!");
        sendNotification();
    }
}

function resetAlert() {
    const indicator = document.getElementById('indicator-circle');
    const subtext = document.getElementById('indicator-subtext');
    
    if (indicator.classList.contains('theft')) {
        indicator.classList.remove('theft');
        indicator.innerText = "MONITORING";
        subtext.innerText = "System Operating Correctly";
        subtext.style.color = "#8b949e";

        // Start 10 second timer for auto-emailing
        if (theftLogs.length > 0 && currentEmail && !theftTimer) {
            theftTimer = setTimeout(autoSendLogs, 10000);
        }
    }
}

function startLearning() {
    if (mode === "real") {
        mode = "learning";
        learning_readings = [];
        document.getElementById('learning-progress').style.width = "0%";
        updateModeUI();
    }
}

function resetPattern() {
    learned_current = null;
    learning_readings = [];
    mode = (last_update > 0 && (Date.now() - last_update) < 5000) ? "real" : "demo";
    document.getElementById('theft-table-container').style.display = "none";
    document.getElementById('theft-logs-body').innerHTML = "";
    resetAlert();
    updateModeUI();
}

function generateApiKey() {
    fetch('/generate-key')
        .then(res => res.json())
        .then(data => {
            if (!data.api_key) {
                alert("Failed to generate API key");
                return;
            }
            apiKey = data.api_key;
            localStorage.setItem('electricity_api_key', apiKey);
            const box = document.getElementById('api-key-box');
            const display = document.getElementById('api-key-display');
            if (box) box.innerText = apiKey;
            if (display) display.innerText = "API KEY: " + apiKey;
            alert("API Key Generated Successfully!");
            closeModal();
        })
        .catch(err => {
            console.error("Key generation failed:", err);
            alert("Server error while generating API key");
        });
}

function openModal() { document.getElementById('setupModal').style.display = 'block'; }
function closeModal() { document.getElementById('setupModal').style.display = 'none'; }

function openEmailModal() { 
    document.getElementById('emailModal').style.display = 'block'; 
    document.getElementById('email-step-1').style.display = 'block';
    document.getElementById('email-step-2').style.display = 'none';
}
function closeEmailModal() { document.getElementById('emailModal').style.display = 'none'; }

function maskEmail(email) {
    if (!email) return "";
    const [user, domain] = email.split("@");
    return user.charAt(0) + "***@" + domain;
}

function updateEmailUI() {
    const setupBtn = document.getElementById('setupEmailBtn');
    const logoutBtn = document.getElementById('logoutEmailBtn');
    
    if (currentEmail) {
        setupBtn.style.display = "none";
        logoutBtn.style.display = "block";
        logoutBtn.innerText = "LOGOUT (" + maskEmail(currentEmail) + ")";
    } else {
        setupBtn.style.display = "block";
        logoutBtn.style.display = "none";
    }
}

async function sendOTP() {
    const email = document.getElementById('setupEmailInput').value;
    if (!email) {
        alert("Please enter a valid email");
        return;
    }
    
    try {
        const res = await fetch('/send-otp', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ email })
        });
        const data = await res.json();
        if (data.success) {
            document.getElementById('email-step-1').style.display = 'none';
            document.getElementById('email-step-2').style.display = 'block';
            showToast("OTP sent to your email!");
        } else {
            alert(data.message);
        }
    } catch (err) {
        console.error("OTP send error:", err);
    }
}

async function verifyOTP() {
    const email = document.getElementById('setupEmailInput').value;
    const otp = document.getElementById('otpInput').value;
    
    try {
        const res = await fetch('/verify-otp', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ email, otp })
        });
        const data = await res.json();
        if (data.success) {
            currentEmail = email;
            localStorage.setItem('electricity_email', email);
            updateEmailUI();
            closeEmailModal();
            showToast("Email verified successfully!");
        } else {
            alert("Invalid OTP, please try again.");
        }
    } catch (err) {
        console.error("OTP verify error:", err);
    }
}

function logoutEmail() {
    currentEmail = null;
    localStorage.removeItem('electricity_email');
    updateEmailUI();
    showToast("Email logged out.");
}

async function autoSendLogs() {
    if (theftLogs.length > 0 && currentEmail) {
        await sendLogsToBackend(theftLogs);
        theftLogs = []; // Clear after sending
        theftTimer = null;
    }
}

async function manualSendLogs() {
    if (!currentEmail) {
        alert("Please setup email first!");
        return;
    }
    if (theftLogs.length === 0) {
        alert("No logs to send!");
        return;
    }
    const success = await sendLogsToBackend(theftLogs);
    if (success) {
        theftLogs = [];
        showToast("Email Sent Successfully");
    }
}

async function sendLogsToBackend(logs) {
    try {
        const res = await fetch('/send-logs', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ logs })
        });
        const data = await res.json();
        return data.success;
    } catch (err) {
        console.error("Send logs error:", err);
        return false;
    }
}

function sendNotification() {
    if (Notification.permission === "granted") {
        new Notification("⚠️ Electricity Theft Detected!", {
            body: "Abnormal power usage detected in your system",
            icon: "https://cdn-icons-png.flaticon.com/512/565/565547.png"
        });
    }
}

function showToast(message) {
    const container = document.getElementById('toast-container');
    if (!container) return;
    const toast = document.createElement('div');
    toast.className = 'toast';
    toast.innerHTML = `<span>🚨</span> <span>${message}</span>`;
    container.appendChild(toast);
    
    setTimeout(() => {
        toast.classList.add('fade-out');
        setTimeout(() => toast.remove(), 500);
    }, 5000);
}

// Initialize
window.onload = () => {
    if (Notification.permission !== "granted" && Notification.permission !== "denied") {
        Notification.requestPermission();
    }

    initCharts();
    updateEmailUI();
    if (apiKey) {
        const display = document.getElementById('api-key-display');
        const box = document.getElementById('api-key-box');
        if (display) display.innerText = "API KEY: " + apiKey;
        if (box) box.innerText = apiKey;
    }
    
    const genBtn = document.getElementById("generateKeyBtn");
    if (genBtn) {
        genBtn.addEventListener("click", generateApiKey);
    }
    
    // Polling data every 2 seconds
    setInterval(fetchLatestData, 2000);
    
    // Connectivity check every 1 second
    setInterval(checkConnectivity, 1000);
};

window.onclick = (event) => {
    const modal = document.getElementById('setupModal');
    const emailModal = document.getElementById('emailModal');
    if (event.target == modal) closeModal();
    if (event.target == emailModal) closeEmailModal();
};
