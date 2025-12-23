// --- Theme Logic ---
const html = document.documentElement;
document.getElementById('theme-toggle').addEventListener('click', () => {
html.classList.toggle('dark');
document.getElementById('theme-icon').textContent = html.classList.contains('dark') ? '🌙' : '🌞';
});
// --- Tab Logic ---
function switchTab(tabName) {
const cutterContent = document.getElementById('tab-cutter-content');
const whisperContent = document.getElementById('tab-whisper-content');
const btnCutter = document.getElementById('tab-btn-cutter');
const btnWhisper = document.getElementById('tab-btn-whisper');
if (tabName === 'cutter') {
cutterContent.classList.remove('hidden');
cutterContent.classList.add('block');
whisperContent.classList.remove('block');
whisperContent.classList.add('hidden');
// Style updates
btnCutter.classList.add('border-tech-500', 'text-tech-600', 'dark:text-tech-400');
btnCutter.classList.remove('border-transparent', 'text-gray-400');

btnWhisper.classList.remove('border-tech-500', 'text-tech-600', 'dark:text-tech-400');
btnWhisper.classList.add('border-transparent', 'text-gray-400');
} else {
cutterContent.classList.remove('block');
cutterContent.classList.add('hidden');
whisperContent.classList.remove('hidden');
whisperContent.classList.add('block');
// Style updates
btnWhisper.classList.add('border-purple-500', 'text-purple-600', 'dark:text-purple-400');
btnWhisper.classList.remove('border-transparent', 'text-gray-400');

btnCutter.classList.remove('border-tech-500', 'text-tech-600', 'dark:text-tech-400');
btnCutter.classList.add('border-transparent', 'text-gray-400');
}
}
// --- Console Helper ---
function log(msg, type='info') {
const c = document.getElementById('console-output');
let color = 'text-green-400';
if (type === 'error') color = 'text-red-500';
if (type === 'warn') color = 'text-yellow-400';
if (type === 'cmd') color = 'text-cyan-300';

c.innerHTML += `<br><span class="${color}">> ${msg}</span>`;
c.scrollTop = c.scrollHeight;
}
// --- API: Cutter ---
async function submitCutter() {
const form = document.getElementById('cutter-form');
const formData = new FormData(form);
if (!formData.get('input_file')) { alert('請輸入影片路徑！'); return; }

log("發送剪輯指令...", 'warn');
try {
const res = await fetch('/run', { method: 'POST', body: formData });
const data = await res.json();
if (data.status === 'success') {
log(`指令: ${data.command}`, 'cmd');
log(data.message);
} else {
log(data.message, 'error');
}
} catch (e) { log(e, 'error'); }
}
// --- API: Extract Audio ---
async function submitExtract() {
const form = document.getElementById('extract-form');
const formData = new FormData(form);
const videoPath = formData.get('input_video');
if (!videoPath) { alert('請輸入影片路徑！'); return; }
log("開始轉檔 MP3...", 'warn');
try {
const res = await fetch('/extract-audio', { method: 'POST', body: formData });
const data = await res.json();
if (data.status === 'success') {
log(`指令: ${data.command}`, 'cmd');
log(data.message);
// Auto-fill next step
document.getElementById('whisper_input').value = data.output_path;
log("已自動填入下一步驟的輸入路徑。", 'warn');
} else {
log(data.message, 'error');
}
} catch (e) { log(e, 'error'); }
}
// --- API: Whisper ---
async function submitWhisper() {
const form = document.getElementById('whisper-form');
const formData = new FormData(form);

// Handle checkboxes manually for FormData
const formats = [];
document.querySelectorAll('input[name="output_formats"]:checked').forEach(cb => {
formats.push(cb.value);
});
if (formats.length === 0) {
alert('請至少選擇一種輸出格式 (如 srt)！');
return;
}
if (!formData.get('input_mp3')) {
alert('請輸入音訊檔案路徑！');
return;
}
// Append list as comma string
formData.set('output_formats', formats.join(','));
log("啟動 Whisper AI...", 'warn');
try {
const res = await fetch('/run-whisper', { method: 'POST', body: formData });
const data = await res.json();
if (data.status === 'success') {
log(`指令: ${data.command}`, 'cmd');
log(data.message);
} else {
log(data.message, 'error');
}
} catch (e) { log(e, 'error'); }
}
// --- Presets Logic (Existing) ---
const inputs = {
hp: document.getElementById('highpass'),
nr: document.getElementById('afftdn'),
echo: document.getElementById('aecho'),
ne: document.getElementById('speechnorm_e'),
np: document.getElementById('speechnorm_p'),
};
const presets = {
dry: { hp: 80, nr: 12, echo: '0.8:0.4:50:0.3', ne: 4, np: 0.9 },
tutorial: { hp: 100, nr: 12, echo: '0.8:0.3:40:0.2', ne: 4, np: 0.9 },
bass: { hp: 20, nr: 10, echo: '0.8:0.3:40:0.2', ne: 4, np: 0.9 },
denoise_only: { hp: 0, nr: 15, echo: 'None', ne: 0, np: 0 },
no_echo: { hp: 80, nr: 12, echo: 'None', ne: 4, np: 0.9 },
off: { hp: 0, nr: 0, echo: 'None', ne: 0, np: 0 },
};
function applyPreset(name) {
const p = presets[name];
if (!p) return;
inputs.hp.value = p.hp; inputs.nr.value = p.nr; inputs.echo.value = p.echo; inputs.ne.value = p.ne; inputs.np.value = p.np;
const form = document.getElementById('cutter-form');
form.classList.add('ring-2', 'ring-tech-400');
setTimeout(() => form.classList.remove('ring-2', 'ring-tech-400'), 200);
}