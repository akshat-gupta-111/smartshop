async function askFAQ(){
  const qEl = document.getElementById('faqQuestion');
  const ansEl = document.getElementById('faqAnswer');
  const question = qEl.value.trim();
  if(!question) return;
  ansEl.textContent = 'Asking...';
  const res = await postJSON('/faq/ask', { question });
  if(res.ok){
    ansEl.textContent = res.answer;
  } else {
    ansEl.textContent = 'Error: '+(res.error||'Unknown');
  }
}
window.addEventListener('load', ()=>{
  const btn = document.getElementById('faqAskBtn');
  if(btn) btn.addEventListener('click', askFAQ);
});