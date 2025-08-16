async function postJSON(url, data){
  const res = await fetch(url, {
    method:'POST',
    headers:{'Content-Type':'application/json'},
    body: JSON.stringify(data || {})
  });
  return res.json();
}

function toggleEditForm(card, show){
  const form = card.querySelector('.edit-form');
  if(!form) return;
  if(show){
    form.classList.remove('hidden');
  } else {
    form.classList.add('hidden');
  }
}

function setupRetailerManagement(){
  const container = document.getElementById('retailerProducts');
  if(!container) return;

  container.addEventListener('click', async (e)=>{
    const editBtn = e.target.closest('.edit-btn');
    const deleteBtn = e.target.closest('.delete-btn');
    const cancelBtn = e.target.closest('.cancel-edit');

    if(editBtn){
      const card = editBtn.closest('.product-card');
      toggleEditForm(card, true);
    }
    if(cancelBtn){
      const id = cancelBtn.getAttribute('data-id');
      const card = container.querySelector(`.product-card[data-item-id="${id}"]`);
      toggleEditForm(card, false);
    }
    if(deleteBtn){
      if(!confirm('Delete this product?')) return;
      const id = deleteBtn.getAttribute('data-id');
      const res = await postJSON(`/store/item/${id}/delete`, {});
      if(res.ok){
        const card = deleteBtn.closest('.product-card');
        card.remove();
      } else {
        alert('Delete failed: ' + (res.error||''));
      }
    }
  });

  container.querySelectorAll('.edit-form').forEach(form=>{
    form.addEventListener('submit', async (e)=>{
      e.preventDefault();
      const id = form.getAttribute('data-id');
      const statusEl = form.querySelector(`.edit-status[data-status-for="${id}"]`);
      statusEl.textContent = 'Saving...';
      const fd = new FormData(form);
      const payload = {
        name: fd.get('name'),
        category: fd.get('category'),
        description: fd.get('description'),
        price: fd.get('price'),
        stock: fd.get('stock'),
        tags: fd.get('tags')
      };
      const res = await postJSON(`/store/item/${id}/edit`, payload);
      if(res.ok){
        statusEl.textContent = 'Saved.';
        // Update visible card fields (name, meta, description)
        const card = form.closest('.product-card');
        card.querySelector('h4').textContent = res.item.name;
        card.querySelector('.meta').textContent =
          `${res.item.category} | $${Number(res.item.price).toFixed(2)} | Stock: ${res.item.stock}`;
        // Update short desc (regenerate)
        const shortDesc = res.item.description_short;
        const descP = card.querySelector('p:not(.meta)');
        if(descP) descP.textContent = shortDesc;
        setTimeout(()=>{
          statusEl.textContent = '';
          toggleEditForm(card, false);
        }, 800);
      } else {
        statusEl.textContent = 'Error: ' + (res.error||'');
      }
    });
  });
}

window.addEventListener('load', setupRetailerManagement);