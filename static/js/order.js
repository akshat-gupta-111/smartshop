let CURRENT_ORDER_ID = null;

function initOrderPage(mode){
  const form = document.getElementById('orderForm');
  const status = document.getElementById('orderStatus');
  const paymentSection = document.getElementById('paymentSection');
  const qrBtn = document.getElementById('generateQrBtn');
  const verifyBtn = document.getElementById('verifyPaymentBtn');
  const qrContainer = document.getElementById('qrContainer');
  const verifyStatus = document.getElementById('verifyStatus');

  form.addEventListener('submit', async (e)=>{
    e.preventDefault();
    status.textContent = 'Creating order...';
    const fd = new FormData(form);
    const payload = {
      name: fd.get('name'),
      phone: fd.get('phone'),
      email: fd.get('email'),
      address: fd.get('address'),
      mode: fd.get('mode')
    };
    if(payload.mode === 'single'){
      payload.item_id = fd.get('item_id');
      payload.retailer = fd.get('retailer');
    }
    const res = await postJSON('/order/create', payload);
    if(res.ok){
      status.textContent = 'Order created. Order ID: ' + res.order_id;
      CURRENT_ORDER_ID = res.order_id;
      paymentSection.classList.remove('hidden');
      qrBtn.disabled = false;
      verifyBtn.disabled = true;
    } else {
      status.textContent = 'Error: ' + (res.error||'');
    }
  });

  qrBtn.addEventListener('click', async ()=>{
    if(!CURRENT_ORDER_ID){
      alert('Create the order first.');
      return;
    }
    qrContainer.innerHTML = 'Generating QR...';
    const res = await fetch(`/order/${CURRENT_ORDER_ID}/qr`);
    const data = await res.json();
    if(data.ok){
      const img = document.createElement('img');
      img.src = 'data:image/png;base64,' + data.image;
      img.alt = 'Payment QR';
      img.style.maxWidth = '200px';
      qrContainer.innerHTML = '';
      qrContainer.appendChild(img);
      verifyBtn.disabled = false;
    } else {
      qrContainer.textContent = 'Error: ' + (data.error||'');
    }
  });

  verifyBtn.addEventListener('click', async ()=>{
    verifyStatus.textContent = 'Verifying...';
    const res = await postJSON(`/order/${CURRENT_ORDER_ID}/verify`, {});
    if(res.ok){
      verifyStatus.textContent = res.message;
    } else {
      verifyStatus.textContent = 'Error: ' + (res.error||'');
    }
  });
}