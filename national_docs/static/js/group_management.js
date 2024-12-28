// static/js/group_management.js

function initializeGroupManagement() {
    // Add Member Modal Handling
    const addMemberForm = document.getElementById('addMemberForm');
    const addButton = document.querySelector('#addMemberModal .btn-primary');
    const addModal = document.getElementById('addMemberModal');
    const bootstrapAddModal = new bootstrap.Modal(addModal);

    addButton.addEventListener('click', function() {
        const selectedUser = document.getElementById('newMember').value;
        if (!selectedUser) {
            alert('Please select a user');
            return;
        }

        // Get CSRF token
        const csrfToken = document.querySelector('[name=csrfmiddlewaretoken]').value;

        // Send AJAX request for adding member
        fetch('', {
            method: 'POST',
            headers: {
                'X-Requested-With': 'XMLHttpRequest',
                'X-CSRFToken': csrfToken,
                'Content-Type': 'application/x-www-form-urlencoded',
            },
            body: `action=add&user_id=${selectedUser}`
        })
        .then(response => response.json())
        .then(data => {
            if (data.status === 'success') {
                showAlert(data.message, 'success');

                // Remove the user from the select options
                const option = document.querySelector(`#newMember option[value="${selectedUser}"]`);
                if (option) option.remove();

                // Reset and close modal
                addMemberForm.reset();
                bootstrapAddModal.hide();

                // Reload page after short delay
                setTimeout(() => {
                    window.location.reload();
                }, 1500);
            } else {
                showAlert(data.message || 'An error occurred while adding the member.', 'danger');
            }
        })
        .catch(error => {
            console.error('Error:', error);
            showAlert('An error occurred while adding the member.', 'danger');
        });
    });

    // Remove Member Modal Handling
    document.querySelectorAll('.remove-member-btn').forEach(button => {
        button.addEventListener('click', function() {
            const userId = this.dataset.userId;
            const modalElement = this.closest('.modal');
            const bootstrapModal = bootstrap.Modal.getInstance(modalElement);
            const csrfToken = document.querySelector('[name=csrfmiddlewaretoken]').value;

            // Send AJAX request for removing member
            fetch('', {
                method: 'POST',
                headers: {
                    'X-Requested-With': 'XMLHttpRequest',
                    'X-CSRFToken': csrfToken,
                    'Content-Type': 'application/x-www-form-urlencoded',
                },
                body: `action=remove&user_id=${userId}`
            })
            .then(response => response.json())
            .then(data => {
                if (data.status === 'success') {
                    showAlert(data.message, 'success');

                    // Close modal
                    bootstrapModal.hide();

                    // Reload page after short delay
                    setTimeout(() => {
                        window.location.reload();
                    }, 1500);
                } else {
                    showAlert(data.message || 'An error occurred while removing the member.', 'danger');
                }
            })
            .catch(error => {
                console.error('Error:', error);
                showAlert('An error occurred while removing the member.', 'danger');
            });
        });
    });
}

// Helper function to show alerts
function showAlert(message, type = 'success') {
    const alertDiv = document.createElement('div');
    alertDiv.className = `alert alert-${type} alert-dismissible fade show`;
    alertDiv.innerHTML = `
        ${message}
        <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
    `;
    document.querySelector('.container').insertBefore(alertDiv, document.querySelector('h2'));
}

// Global error handling
window.addEventListener('error', function(event) {
    console.error('Global error:', event.error);
    showAlert('An unexpected error occurred.', 'danger');
});

// Initialize when DOM is loaded
document.addEventListener('DOMContentLoaded', initializeGroupManagement);