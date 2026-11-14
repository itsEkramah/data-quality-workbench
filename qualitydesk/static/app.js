const $ = id => document.getElementById(id);
const example = 'order_id,date,region,amount\nA101,2026-11-01, North ,125.50\nA102,2026-11-02,South,70\nA102,2026-11-02,South,70\nA103,2026-11-03,West,NaN\nA103,2026-11-03,West,49.99\n,2026-11-04,East,20\nA105,04/11/2026,North,45\nA106,2026-11-05,East,90\n';
let jobId;
function loadDemo() { $('source').value = example; }
$('demo').onclick = loadDemo;
$('file').onchange = async event => { const file = event.target.files[0]; if (!file) return; if (file.size > 1000000) { $('status').textContent = 'Please use a file smaller than 1 MB.'; return; } $('source').value = await file.text(); };
const columns = id => $(id).value.split(',').map(x => x.trim()).filter(Boolean);
$('run').onclick = async () => {
  $('run').disabled = true; $('status').textContent = 'Checking your data…';
  try {
    const response = await fetch('/api/jobs', {method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({csv_text:$('source').value,rules:{required:columns('required'),key:columns('key'),numeric:columns('numeric'),dates:columns('dates')}})});
    const data = await response.json(); if (!response.ok) throw new Error(typeof data.detail === 'string' ? data.detail : 'Check the CSV size and rule fields.');
    jobId = data.id; $('empty').hidden = true; $('report').hidden = false;
    $('total').textContent = data.summary.input_rows; $('accepted').textContent = data.summary.accepted_rows; $('rejected').textContent = data.summary.rejected_rows;
    const table = $('preview'); table.replaceChildren(); const head = document.createElement('tr');
    data.columns.forEach(value => {const cell=document.createElement('th');cell.textContent=value;head.append(cell);}); table.append(head);
    data.accepted.slice(0,8).forEach(row => {const tr=document.createElement('tr');data.columns.forEach(col=>{const td=document.createElement('td');td.textContent=row[col];tr.append(td);});table.append(tr);});
    $('issues').replaceChildren(); data.rejected.slice(0,20).forEach(row=>{const li=document.createElement('li');li.textContent=`Row ${row.row}: ${row.errors.join('; ')}`;$('issues').append(li);});
    if (!data.rejected.length) {const li=document.createElement('li');li.textContent='All rows passed the selected rules.';$('issues').append(li);}
    $('downloads').replaceChildren(); ['clean','rejected','source','report'].forEach(kind=>{const a=document.createElement('a');a.href=`/api/jobs/${jobId}/export?kind=${kind}`;a.textContent=`Download ${kind}`;$('downloads').append(a);});
    $('status').textContent = 'Saved locally. Download the source, outputs and full report below.';
  } catch (error) { $('status').textContent=error.message; } finally { $('run').disabled=false; }
};
$('delete').onclick=async()=>{if(!jobId)return;try{const response=await fetch(`/api/jobs/${jobId}`,{method:'DELETE'});if(!response.ok)throw new Error('Could not delete the job.');$('report').hidden=true;$('empty').hidden=false;$('status').textContent='Saved input and result deleted from the application database.';jobId=null;}catch(error){$('status').textContent=error.message;}};
loadDemo();
