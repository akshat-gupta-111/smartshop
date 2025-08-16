let CHAT_SESSION_ID = null;
let ratingTimer = null;

function escapeHTML(str){
  return (str || '').replace(/[&<>"']/g, s => ({
    '&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'
  }[s]));
}

function nl2br(str){
  return escapeHTML(str).replace(/\n/g,'<br>');
}

function appendChat(role, text){
  const box = document.getElementById('chatMessages');
  const row = document.createElement('div');
  row.className = 'chat-message ' + role;
  row.innerHTML = `<strong>${role}:</strong> ${nl2br(text)}`;
  box.appendChild(row);
  box.scrollTop = box.scrollHeight;
}

function ensureRecContainer(){
  let c = document.getElementById('recommendationCards');
  if(!c){
    c = document.createElement('div');
    c.id = 'recommendationCards';
    document.getElementById('chatMessages').appendChild(c);
  }
  return c;
}

function showRecommendations(recs){
  const container = ensureRecContainer();
  container.innerHTML = '';
  if(!recs || !recs.length){
    container.innerHTML = '<p class="no-recs">No recommendations yet.</p>';
    return;
  }
  const grid = document.createElement('div');
  grid.className = 'rec-grid';
  recs.forEach(r=>{
    const card = document.createElement('div');
    card.className = 'rec-card';
    const title = escapeHTML(r.name || ('Item ' + r.item_id));
    const reason = escapeHTML(r.reason || '');
    const retailer = escapeHTML(r.retailer || '');
    const score = escapeHTML(String(r.match_score));
    const linkHTML = r.product_url
      ? `<a href="${escapeHTML(r.product_url)}" class="rec-link" target="_blank" rel="noopener">View Product</a>`
      : `<span class="rec-link disabled">No link</span>`;
    card.innerHTML = `
      <div class="rec-title">${title}</div>
      <div class="rec-meta">Score: ${score}</div>
      ${retailer ? `<div class="rec-retailer">Retailer: ${retailer}</div>` : ''}
      <div class="rec-reason">${reason}</div>
      ${linkHTML}
    `;
    grid.appendChild(card);
  });
  container.appendChild(grid);
}

async function startChat(auto=false){
  const startBtn = document.getElementById('startChatBtn');
  if(startBtn) startBtn.disabled = true;
  const res = await postJSON('/chat/start', {});
  if(res.ok){
    CHAT_SESSION_ID = res.session_id;
    appendChat('assistant', res.message);
    document.getElementById('sendChatBtn').disabled = false;
  } else {
    appendChat('assistant', 'Error starting chat: ' + (res.error||''));
    if(startBtn && !auto) startBtn.disabled = false;
  }
}

async function sendChat(){
  const input = document.getElementById('chatInput');
  const msg = input.value.trim();
  if(!msg) return;

  if(!CHAT_SESSION_ID){
    await startChat(true);
    if(!CHAT_SESSION_ID){
      appendChat('assistant','Could not initialize chat session.');
      return;
    }
  }

  appendChat('user', msg);
  input.value = '';
  document.getElementById('sendChatBtn').disabled = true;

  const res = await postJSON('/chat/recommend', {
    session_id: CHAT_SESSION_ID,
    message: msg
  });

  document.getElementById('sendChatBtn').disabled = false;

  if(res.ok){
    if(res.session_id) CHAT_SESSION_ID = res.session_id;
    const r = res.response;
    // Build concise summary for chat stream
    let summary;
    if(r.recommendations && r.recommendations.length){
      summary = r.recommendations.map((rec,i)=> {
        return `${i+1}. ${(rec.name||rec.item_id)} (Score: ${rec.match_score})`;
      }).join('\n');
    } else {
      summary = 'No suitable items found.';
    }
    if(r.follow_up_question){
      summary += '\n' + r.follow_up_question;
    }
    appendChat('assistant', summary);
    showRecommendations(r.recommendations);
    scheduleRatingPopup();
  } else {
    if(res.error === 'Invalid session'){
      appendChat('assistant', 'Session expired. Starting a new one...');
      CHAT_SESSION_ID = null;
      await startChat(true);
    } else {
      appendChat('assistant', 'Error: ' + (res.error||'Unknown'));
    }
  }
}

function scheduleRatingPopup(){
  clearTimeout(ratingTimer);
  ratingTimer = setTimeout(()=>{
    const popup = document.getElementById('ratingPopup');
    if(popup) popup.classList.remove('hidden');
  }, 5000);
}

window.addEventListener('load', ()=>{
  document.getElementById('startChatBtn')?.addEventListener('click', ()=> startChat(false));
  document.getElementById('sendChatBtn')?.addEventListener('click', sendChat);
});