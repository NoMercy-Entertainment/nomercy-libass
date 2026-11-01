// Plays the frame-counter clip with the web libass kit in headless Chrome and keeps a CDP screencast.
// node web-screencast.mjs --kit <kit dist dir> --clip <mp4> --ass <ass> --font <ttf> --out <dir> [--from 5] [--seconds 6]
import { spawn } from 'node:child_process';
import fs from 'node:fs';
import http from 'node:http';
import path from 'node:path';

const args = Object.fromEntries(process.argv.slice(2).reduce((a, v, i, all) => (v.startsWith('--') ? [...a, [v.slice(2), all[i + 1]]] : a), []));
const from = Number(args.from ?? 5);
const seconds = Number(args.seconds ?? 6);
const types = { '.html': 'text/html', '.js': 'text/javascript', '.mp4': 'video/mp4', '.wasm': 'application/wasm' };
const page = `<!doctype html><style>body{margin:0;background:#000;overflow:hidden}#stage{position:relative;width:1280px;height:720px}video{width:1280px;height:720px}.nomercy-libass{position:absolute!important;top:0!important;left:0!important}</style>
<div id="stage"><video id="v" src="/clip.mp4" muted playsinline></video></div>
<script type="module">
import { NMSubtitleOctopus } from '/kit/nomercy-subtitle-octopus.js';
const video = document.getElementById('v');
window.start = async () => {
	const o = new NMSubtitleOctopus({ video, trackUrl: '/counter.ass', workerUrl: '/kit/nomercy-libass-worker.js', fonts: ['/font.ttf'], geometrySource: document.getElementById('stage') });
	await new Promise((res, rej) => { o.on('rendererReady', () => res()); o.on('error', rej); });
	await new Promise(r => setTimeout(r, 800));
	video.currentTime = ${from};
	await new Promise(r => video.addEventListener('seeked', r, { once: true }));
	await video.play();
	return 'playing';
};
window.ready = true;
</script>`;

function serve(req, res, file) {
	if (!file || !fs.existsSync(file)) { res.statusCode = 404; res.end(); return; }
	const size = fs.statSync(file).size;
	const type = types[path.extname(file)] ?? 'application/octet-stream';
	const m = /bytes=(\d*)-(\d*)/.exec(req.headers.range ?? '');
	if (m) {
		const s = m[1] ? Number(m[1]) : 0;
		const e = m[2] ? Number(m[2]) : size - 1;
		res.writeHead(206, { 'Content-Type': type, 'Accept-Ranges': 'bytes', 'Content-Range': `bytes ${s}-${e}/${size}`, 'Content-Length': e - s + 1 });
		fs.createReadStream(file, { start: s, end: e }).pipe(res);
		return;
	}
	res.writeHead(200, { 'Content-Type': type, 'Accept-Ranges': 'bytes', 'Content-Length': size });
	fs.createReadStream(file).pipe(res);
}
const server = http.createServer((req, res) => {
	const u = new URL(req.url, 'http://x').pathname;
	if (u === '/page.html') { res.writeHead(200, { 'Content-Type': 'text/html' }); res.end(page); }
	else if (u === '/clip.mp4') serve(req, res, args.clip);
	else if (u === '/counter.ass') serve(req, res, args.ass);
	else if (u === '/font.ttf') serve(req, res, args.font);
	else if (u.startsWith('/kit/')) serve(req, res, path.join(args.kit, path.basename(u)));
	else { res.statusCode = 404; res.end(); }
});
await new Promise(r => server.listen(9471, '127.0.0.1', r));
const shots = path.join(args.out, 'shots');
fs.mkdirSync(shots, { recursive: true });
const chrome = spawn(args.chrome ?? 'C:/Program Files/Google/Chrome/Application/chrome.exe', [
	'--headless=new', '--remote-debugging-port=9372', `--user-data-dir=${path.join(args.out, 'profile')}`, '--mute-audio',
	'--autoplay-policy=no-user-gesture-required', '--window-size=1280,720', '--no-first-run', 'about:blank'], { stdio: 'ignore' });
let tab;
for (let i = 0; i < 40 && !tab; i++) {
	await new Promise(r => setTimeout(r, 500));
	try { tab = await (await fetch('http://127.0.0.1:9372/json/new?about:blank', { method: 'PUT' })).json(); } catch { /* starting */ }
}
if (!tab) throw new Error('chrome did not start');
const ws = new WebSocket(tab.webSocketDebuggerUrl);
await new Promise(r => ws.addEventListener('open', r));
let id = 0;
const pending = new Map();
let n = 0;
ws.addEventListener('message', (ev) => {
	const m = JSON.parse(ev.data);
	if (m.method === 'Page.screencastFrame') {
		fs.writeFileSync(path.join(shots, `s${String(n++).padStart(5, '0')}.png`), Buffer.from(m.params.data, 'base64'));
		ws.send(JSON.stringify({ id: ++id, method: 'Page.screencastFrameAck', params: { sessionId: m.params.sessionId } }));
	}
	else if (m.id && pending.has(m.id)) { const p = pending.get(m.id); pending.delete(m.id); m.error ? p.reject(new Error(JSON.stringify(m.error))) : p.resolve(m.result); }
});
const send = (method, params = {}) => new Promise((resolve, reject) => { const i = ++id; pending.set(i, { resolve, reject }); ws.send(JSON.stringify({ id: i, method, params })); });
const evaluate = async (expression) => {
	const r = await send('Runtime.evaluate', { expression, awaitPromise: true, returnByValue: true, userGesture: true });
	if (r.exceptionDetails) throw new Error(r.exceptionDetails.exception?.description ?? r.exceptionDetails.text);
	return r.result.value;
};
try {
	await send('Page.enable');
	await send('Emulation.setDeviceMetricsOverride', { width: 1280, height: 720, deviceScaleFactor: 1, mobile: false });
	await send('Page.navigate', { url: 'http://127.0.0.1:9471/page.html' });
	for (let i = 0; i < 60 && (await evaluate('window.ready === true')) !== true; i++) await new Promise(r => setTimeout(r, 500));
	await send('Page.startScreencast', { format: 'png', everyNthFrame: 1 });
	console.log(await evaluate('window.start()'));
	await new Promise(r => setTimeout(r, seconds * 1000));
	await send('Page.stopScreencast');
	await evaluate('document.getElementById("v").pause()');
	console.log('screencast frames', n);
}
finally {
	try { await send('Browser.close'); } catch { /* closed */ }
	chrome.kill();
	server.close();
}
