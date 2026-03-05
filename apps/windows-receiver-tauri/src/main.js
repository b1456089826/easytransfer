const logEl = document.getElementById('log');
const runBtn = document.getElementById('runBtn');

function log(msg) {
  logEl.textContent += `${msg}\n`;
}

runBtn.addEventListener('click', async () => {
  const receivedPath = document.getElementById('receivedPath').value.trim();
  const manifestPath = document.getElementById('manifestPath').value.trim();
  const outputDir = document.getElementById('outputDir').value.trim();

  if (!receivedPath || !manifestPath || !outputDir) {
    log('Please fill all paths');
    return;
  }

  try {
    const { invoke } = window.__TAURI__.tauri;
    const res = await invoke('reconstruct', { receivedPath, manifestPath, outputDir });
    log(JSON.stringify(res, null, 2));
  } catch (e) {
    log(`Error: ${e}`);
  }
});
