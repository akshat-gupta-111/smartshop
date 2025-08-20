// async function postJSON(url, data){
//   const res = await fetch(url, {
//     method:'POST',
//     headers:{'Content-Type':'application/json'},
//     body: JSON.stringify(data || {})
//   });
//   return res.json();
// }

// function toggleEditForm(card, show){
//   const form = card.querySelector('.edit-form');
//   if(!form) return;
//   if(show){
//     form.classList.remove('hidden');
//   } else {
//     form.classList.add('hidden');
//   }
// }

// function setupRetailerManagement(){
//   const container = document.getElementById('retailerProducts');
//   if(!container) return;

//   container.addEventListener('click', async (e)=>{
//     const editBtn = e.target.closest('.edit-btn');
//     const deleteBtn = e.target.closest('.delete-btn');
//     const cancelBtn = e.target.closest('.cancel-edit');

//     if(editBtn){
//       const card = editBtn.closest('.product-card');
//       toggleEditForm(card, true);
//     }
//     if(cancelBtn){
//       const id = cancelBtn.getAttribute('data-id');
//       const card = container.querySelector(`.product-card[data-item-id="${id}"]`);
//       toggleEditForm(card, false);
//     }
//     if(deleteBtn){
//       if(!confirm('Delete this product?')) return;
//       const id = deleteBtn.getAttribute('data-id');
//       const res = await postJSON(`/store/item/${id}/delete`, {});
//       if(res.ok){
//         const card = deleteBtn.closest('.product-card');
//         card.remove();
//       } else {
//         alert('Delete failed: ' + (res.error||''));
//       }
//     }
//   });

//   container.querySelectorAll('.edit-form').forEach(form=>{
//     form.addEventListener('submit', async (e)=>{
//       e.preventDefault();
//       const id = form.getAttribute('data-id');
//       const statusEl = form.querySelector(`.edit-status[data-status-for="${id}"]`);
//       statusEl.textContent = 'Saving...';
//       const fd = new FormData(form);
//       const payload = {
//         name: fd.get('name'),
//         category: fd.get('category'),
//         description: fd.get('description'),
//         price: fd.get('price'),
//         stock: fd.get('stock'),
//         tags: fd.get('tags')
//       };
//       const res = await postJSON(`/store/item/${id}/edit`, payload);
//       if(res.ok){
//         statusEl.textContent = 'Saved.';
//         // Update visible card fields (name, meta, description)
//         const card = form.closest('.product-card');
//         card.querySelector('h4').textContent = res.item.name;
//         card.querySelector('.meta').textContent =
//           `${res.item.category} | $${Number(res.item.price).toFixed(2)} | Stock: ${res.item.stock}`;
//         // Update short desc (regenerate)
//         const shortDesc = res.item.description_short;
//         const descP = card.querySelector('p:not(.meta)');
//         if(descP) descP.textContent = shortDesc;
//         setTimeout(()=>{
//           statusEl.textContent = '';
//           toggleEditForm(card, false);
//         }, 800);
//       } else {
//         statusEl.textContent = 'Error: ' + (res.error||'');
//       }
//     });
//   });
// }

// window.addEventListener('load', setupRetailerManagement);




// static/js/retailer_manage.js

document.addEventListener('DOMContentLoaded', () => {

    const retailerProducts = document.getElementById('retailerProducts');
    const editModal = document.getElementById('editModal');
    const editForm = document.getElementById('editForm');
    const cancelEditBtn = document.getElementById('cancelEditBtn');

    if (!retailerProducts) {
        console.error("Product container not found.");
        return;
    }

    // --- Event Listener for Edit and Delete Buttons ---
    retailerProducts.addEventListener('click', (e) => {
        // Use .closest to make sure we get the button even if an icon inside it is clicked
        const deleteButton = e.target.closest('.delete-btn');
        const editButton = e.target.closest('.edit-btn');

        if (deleteButton) {
            const itemId = deleteButton.dataset.id;
            handleDelete(itemId, deleteButton);
        }

        if (editButton) {
            const itemId = editButton.dataset.id;
            handleEdit(itemId);
        }
    });

    // --- Delete Functionality ---
    const handleDelete = async (itemId, button) => {
        if (!confirm('Are you sure you want to delete this product? This action cannot be undone.')) {
            return;
        }

        try {
            const response = await fetch(`/delete_product/${itemId}`, {
                method: 'DELETE',
            });
            const data = await response.json();

            if (data.ok) {
                // Find the parent card and remove it from the view with an animation
                const card = button.closest('[data-item-id]');
                card.style.transition = 'opacity 0.5s ease';
                card.style.opacity = '0';
                setTimeout(() => card.remove(), 500);
            } else {
                alert('Error deleting product: ' + data.error);
            }
        } catch (error) {
            console.error('Failed to delete product:', error);
            alert('An error occurred. Please try again.');
        }
    };

    // --- Edit Functionality ---
    const handleEdit = async (itemId) => {
        try {
            // Fetch current product data from the server
            const response = await fetch(`/get_product_details/${itemId}`);
            const data = await response.json();

            if (data.ok) {
                // Populate the modal form with the product data
                document.getElementById('editItemId').value = data.item.item_id;
                document.getElementById('editName').value = data.item.name;
                document.getElementById('editDescription').value = data.item.description;
                document.getElementById('editPrice').value = data.item.price;
                document.getElementById('editStock').value = data.item.stock;

                // Show the modal
                editModal.classList.remove('hidden');
            } else {
                alert('Could not fetch product details: ' + data.error);
            }
        } catch (error) {
            console.error('Failed to fetch product details:', error);
            alert('An error occurred. Please try again.');
        }
    };
    
    // --- Close the Edit Modal ---
    const closeEditModal = () => {
        editModal.classList.add('hidden');
        editForm.reset(); // Clear the form for the next time it's opened
    };
    
    if(cancelEditBtn) {
      cancelEditBtn.addEventListener('click', closeEditModal);
    }

    // --- Handle Edit Form Submission ---
    if(editForm) {
      editForm.addEventListener('submit', async (e) => {
          e.preventDefault();
          
          const formData = new FormData(editForm);
          const itemId = formData.get('item_id');

          try {
              const response = await fetch(`/update_product/${itemId}`, {
                  method: 'POST',
                  body: formData,
              });
              const data = await response.json();

              if (data.ok) {
                  alert('Product updated successfully!');
                  location.reload(); // Reload the page to show changes
              } else {
                  alert('Error updating product: ' + data.error);
              }
          } catch (error) {
              console.error('Failed to update product:', error);
              alert('An error occurred. Please try again.');
          }
      });
    }

});