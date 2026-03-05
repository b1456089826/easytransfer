const logEl = document.getElementById('log');
const statusInput = document.getElementById('statusText');
const startBtn = document.getElementById('startBtn');
const stopBtn = document.getElementById('stopBtn');
const runBtn = document.getElementById('runBtn');

function log(msg) {
  logEl.textContent += `${msg}\n`;
}

function setStatus(text) {
  statusInput.value = text;
}

startBtn.addEventListener('click', async () => {
  const listenAddr = document.getElementById('listenAddr').value.trim();
  const receivedPath = document.getElementById('receivedPath').value.trim();
  if (!listenAddr || !receivedPath) {
    log('请填写监听地址和接收文件保存路径');
    return;
  }
  try {
    const { invoke } = window.__TAURI__.tauri;
    const res = await invoke('start_receiver_server', { listenAddr, receivedPath });
    setStatus(`运行中：${listenAddr}`);
    log(JSON.stringify(res, null, 2));
  } catch (e) {
    setStatus('启动失败');
    log(`启动失败：${e}`);
  }
});

stopBtn.addEventListener('click', async () => {
  try {
    const { invoke } = window.__TAURI__.tauri;
    const res = await invoke('stop_receiver_server');
    setStatus('已停止');
    log(JSON.stringify(res, null, 2));
  } catch (e) {
    log(`停止失败：${e}`);
  }
});

runBtn.addEventListener('click', async () => {
  const receivedPath = document.getElementById('receivedPath').value.trim();
  const manifestPath = document.getElementById('manifestPath').value.trim();
  const outputDir = document.getElementById('outputDir').value.trim();

  if (!receivedPath || !manifestPath || !outputDir) {
    log('请填写重组所需路径');
    return;
  }

  try {
    const { invoke } = window.__TAURI__.tauri;
    const res = await invoke('reconstruct', { receivedPath, manifestPath, outputDir });
    log(JSON.stringify(res, null, 2));
  } catch (e) {
    log(`重组失败：${e}`);
  }
});
