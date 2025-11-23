const API = localStorage.getItem('emailJobApi') || 'http://localhost:5000/api';
const form = document.querySelector('#campaignForm');
const rich = document.querySelector('#richEditor');
const htmlEditor = document.querySelector('#htmlEditor');
const frame = document.querySelector('#previewFrame');
let previewTimer;

function toast(message, error = false) {
  const el = document.querySelector('#toast');
  el.textContent = message; el.className = `toast show${error ? ' error' : ''}`;
  clearTimeout(el.timer); el.timer = setTimeout(() => el.className = 'toast', 4200);
}

function payload(includeFiles = false) {
  const data = new FormData(form);
  data.set('message_html', rich.innerHTML);
  data.set('preview_name', document.querySelector('#previewRecipient').value);
  if (!includeFiles) { data.delete('csv'); data.delete('logo'); }
  return data;
}

async function api(path, options = {}) {
  const response = await fetch(`${API}${path}`, options);
  const body = await response.json().catch(() => ({}));
  if (!response.ok) throw new Error(body.error || 'The service could not complete that request.');
  return body;
}

async function updatePreview() {
  try {
    const result = await api('/preview', {method: 'POST', body: payload()});
    frame.srcdoc = result.html; document.querySelector('#previewSubject').textContent = result.subject;
    localStorage.setItem('emailDraft', JSON.stringify(Object.fromEntries(payload())));
    document.querySelector('#saveState').textContent = 'Saved locally';
  } catch { frame.srcdoc = '<p style="font-family:sans-serif;padding:30px">Start the Flask backend to see your preview.</p>'; }
}

function queuePreview() {
  document.querySelector('#saveState').textContent = 'Saving…';
  clearTimeout(previewTimer); previewTimer = setTimeout(updatePreview, 350);
}

async function checkHealth() {
  const holder = document.querySelector('.api-state');
  try { const health = await api('/health'); holder.className = 'api-state online'; document.querySelector('#healthText').textContent = health.smtp_configured ? 'Service ready' : 'SMTP not configured'; }
  catch { holder.className = 'api-state offline'; document.querySelector('#healthText').textContent = 'Backend offline'; }
}

document.querySelectorAll('.tab').forEach(tab => tab.addEventListener('click', () => {
  document.querySelectorAll('.tab').forEach(item => item.classList.remove('active')); tab.classList.add('active');
  const htmlMode = tab.dataset.tab === 'html';
  if (htmlMode) htmlEditor.value = rich.innerHTML; else rich.innerHTML = htmlEditor.value;
  htmlEditor.hidden = !htmlMode; document.querySelector('#visualPanel').hidden = htmlMode; queuePreview();
}));
htmlEditor.addEventListener('input', () => { rich.innerHTML = htmlEditor.value; queuePreview(); });
document.querySelectorAll('[data-cmd]').forEach(button => button.addEventListener('click', () => {
  const value = button.dataset.cmd === 'createLink' ? prompt('Link URL') : null;
  if (button.dataset.cmd !== 'createLink' || value) document.execCommand(button.dataset.cmd, false, value); rich.focus(); queuePreview();
}));
document.querySelectorAll('.token').forEach(button => button.addEventListener('click', () => {
  rich.focus(); document.execCommand('insertText', false, button.dataset.token); queuePreview();
}));
form.addEventListener('input', event => {
  if (event.target.name === 'accent') event.target.nextElementSibling.value = event.target.value;
  if (!['csv', 'logo'].includes(event.target.name)) queuePreview();
});

document.querySelector('#logo').addEventListener('change', event => {
  document.querySelector('#logoName').textContent = event.target.files[0]?.name || 'PNG, JPG or GIF';
});

document.querySelector('#csv').addEventListener('change', async event => {
  const file = event.target.files[0]; if (!file) return;
  document.querySelector('#csvStatus').textContent = `Checking ${file.name}…`;
  const data = new FormData(); data.append('csv', file);
  try {
    const result = await api('/recipients/validate', {method: 'POST', body: data});
    document.querySelector('#csvStatus').textContent = `${file.name} · ${result.count} valid recipient${result.count === 1 ? '' : 's'}`;
    const preview = document.querySelector('#recipientPreview'); preview.hidden = false;
    preview.textContent = `✓ ${result.count} ready to send${result.errors.length ? ` · ${result.errors.length} row(s) will be skipped` : ''}`;
    const selector = document.querySelector('#previewRecipient');
    selector.innerHTML = result.sample.map(person => `<option value="${escapeHtml(person.name)}">${escapeHtml(person.name)} · ${escapeHtml(person.email)}</option>`).join('');
    selector.disabled = false;
    document.querySelector('#previewNote').textContent = `Previewing the first of ${Math.min(result.count, 5)} available sample recipients.`;
    queuePreview();
  } catch (error) { document.querySelector('#csvStatus').textContent = error.message; toast(error.message, true); }
});

function escapeHtml(value) {
  return String(value).replace(/[&<>'"]/g, character => ({'&':'&amp;','<':'&lt;','>':'&gt;',"'":'&#39;','"':'&quot;'}[character]));
}

document.querySelector('#previewRecipient').addEventListener('change', () => {
  document.querySelector('#previewNote').textContent = `Previewing as ${document.querySelector('#previewRecipient').value}.`;
  queuePreview();
});

document.querySelector('#testButton').addEventListener('click', async event => {
  const email = form.elements.test_email.value; if (!email) return toast('Enter a test recipient email.', true);
  event.currentTarget.disabled = true; event.currentTarget.textContent = 'Sending…';
  try { const result = await api('/send-test', {method: 'POST', body: payload(true)}); toast(result.message); }
  catch (error) { toast(error.message, true); }
  finally { event.currentTarget.disabled = false; event.currentTarget.textContent = 'Send test'; }
});

form.addEventListener('submit', async event => {
  event.preventDefault(); if (!form.elements.csv.files.length) return toast('Upload your attendee CSV first.', true);
  if (!confirm('Send this campaign to every valid recipient in the CSV?')) return;
  const button = document.querySelector('#sendButton'); button.disabled = true; button.textContent = 'Starting…';
  try {
    const job = await api('/jobs', {method: 'POST', body: payload(true)}); trackJob(job.id);
  } catch (error) { toast(error.message, true); button.disabled = false; button.innerHTML = 'Send campaign <span>→</span>'; }
});

async function trackJob(id) {
  const box = document.querySelector('#jobProgress'); box.hidden = false;
  const timer = setInterval(async () => {
    try {
      const job = await api(`/jobs/${id}`); const percent = job.total ? job.processed / job.total * 100 : 0;
      document.querySelector('#progressBar').value = percent;
      document.querySelector('#jobCount').textContent = `${job.processed} / ${job.total}`;
      document.querySelector('#jobText').textContent = job.status === 'completed' ? `${job.sent} sent · ${job.failed} failed` : 'Sending personalized emails…';
      if (job.status === 'completed') { clearInterval(timer); toast(`Campaign complete: ${job.sent} sent, ${job.failed} failed.`, job.failed > 0); const b = document.querySelector('#sendButton'); b.disabled = false; b.innerHTML = 'Send campaign <span>→</span>'; }
    } catch (error) { clearInterval(timer); toast(error.message, true); }
  }, 1200);
}

document.querySelectorAll('.device-tabs button').forEach(button => button.addEventListener('click', () => {
  document.querySelectorAll('.device-tabs button').forEach(item => item.classList.remove('active')); button.classList.add('active');
  document.querySelector('.email-frame').classList.toggle('mobile', button.dataset.width === 'mobile');
}));

['dragenter','dragover'].forEach(name => document.querySelector('#dropzone').addEventListener(name, e => { e.preventDefault(); e.currentTarget.classList.add('drag'); }));
['dragleave','drop'].forEach(name => document.querySelector('#dropzone').addEventListener(name, e => { e.preventDefault(); e.currentTarget.classList.remove('drag'); }));
document.querySelector('#dropzone').addEventListener('drop', e => { document.querySelector('#csv').files = e.dataTransfer.files; document.querySelector('#csv').dispatchEvent(new Event('change')); });
checkHealth(); updatePreview();
