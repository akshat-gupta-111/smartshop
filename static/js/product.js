function initPurchaseRequest(itemId, retailer){
  const btn = document.getElementById('requestPurchaseBtn');
  const status = document.getElementById('purchaseStatus');
  if(!btn) return;
  btn.addEventListener('click', async ()=>{
    status.textContent = 'Sending request...';
    const res = await postJSON('/purchase/request', { item_id: itemId, retailer });
    if(res.ok){
      status.textContent = res.message;
    } else {
      status.textContent = 'Error: ' + (res.error||'');
    }
  });
}