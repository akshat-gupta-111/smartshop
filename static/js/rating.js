function attachRatingHandlers(){
  const popup = document.getElementById('ratingPopup');
  if(!popup) return;
  popup.addEventListener('click', async (e)=>{
    if(e.target.matches('[data-rate]')){
      const rating = e.target.getAttribute('data-rate');
      const res = await postJSON('/chat/rate', { rating });
      if(res.ok){
        document.getElementById('countExcellent').textContent = res.counts.excellent;
        document.getElementById('countGood').textContent = res.counts.good;
        document.getElementById('countBad').textContent = res.counts.bad;
        popup.classList.add('hidden');
      } else {
        alert('Rating error: '+(res.error||''));
      }
    }
    if(e.target.id === 'closeRatingPopup'){
      popup.classList.add('hidden');
    }
  });
}
window.addEventListener('load', attachRatingHandlers);