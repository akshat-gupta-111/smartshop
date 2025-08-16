async function addToCart(item_id, retailer){
  const res = await postJSON('/cart/add', { item_id, retailer });
  return res;
}
async function removeFromCart(item_id, retailer){
  const res = await postJSON('/cart/remove', { item_id, retailer });
  return res;
}
async function clearCart(){
  return postJSON('/cart/clear', {});
}

function setupProductCartButtons(item_id, retailer, inCart){
  const status = document.getElementById('cartActionStatus');
  const addBtn = document.getElementById('addToCartBtn');
  const removeBtn = document.getElementById('removeFromCartBtn');

  if(addBtn){
    addBtn.addEventListener('click', async ()=>{
      status.textContent = 'Adding to cart...';
      const r = await addToCart(item_id, retailer);
      if(r.ok){
        status.textContent = 'Added to cart.';
        addBtn.disabled = true;
      } else {
        status.textContent = 'Error: ' + (r.error||'');
      }
    });
  }
  if(removeBtn){
    removeBtn.addEventListener('click', async ()=>{
      status.textContent = 'Removing from cart...';
      const r = await removeFromCart(item_id, retailer);
      if(r.ok){
        status.textContent = 'Removed from cart.';
        removeBtn.disabled = true;
      } else {
        status.textContent = 'Error: ' + (r.error||'');
      }
    });
  }
}

function setupCartPage(){
  const clearBtn = document.getElementById('clearCartBtn');
  if(clearBtn){
    clearBtn.addEventListener('click', async ()=>{
      if(!confirm('Clear entire cart?')) return;
      const r = await clearCart();
      if(r.ok){
        location.reload();
      }
    });
  }
  document.querySelectorAll('.remove-btn').forEach(btn=>{
    btn.addEventListener('click', async ()=>{
      const item_id = btn.getAttribute('data-item');
      const retailer = btn.getAttribute('data-retailer');
      const row = btn.closest('tr');
      const r = await removeFromCart(item_id, retailer);
      if(r.ok){
        row.remove();
        if(document.querySelectorAll('.cart-table tbody tr').length === 0){
          location.reload();
        }
      } else {
        alert('Error removing item: '+(r.error||''));
      }
    });
  });
}