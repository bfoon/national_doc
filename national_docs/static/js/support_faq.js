document.getElementById('addFAQForm')?.addEventListener('submit', async function(e) {
    e.preventDefault();

    // Reset previous validation states
    this.classList.remove('was-validated');
    const errorDiv = document.getElementById('addFAQError');
    errorDiv.classList.add('d-none');

    const question = document.getElementById('newQuestion');
    const answer = document.getElementById('newAnswer');
    let isValid = true;

    // Validate question
    if (question.value.trim().length < 10) {
        question.classList.add('is-invalid');
        isValid = false;
    } else {
        question.classList.remove('is-invalid');
    }

    // Validate answer
    if (answer.value.trim().length < 20) {
        answer.classList.add('is-invalid');
        isValid = false;
    } else {
        answer.classList.remove('is-invalid');
    }

    if (!isValid) {
        errorDiv.textContent = 'Please correct the errors before submitting.';
        errorDiv.classList.remove('d-none');
        return;
    }

    // Show loading state
    const submitBtn = document.getElementById('addFAQSubmit');
    const loadingIndicator = this.querySelector('.loading-indicator');
    submitBtn.disabled = true;
    loadingIndicator.classList.remove('d-none');

    try {
        // Submit form using fetch
        const formData = new FormData(this);
        const response = await fetch("{% url 'add_faq' %}", {
            method: 'POST',
            headers: {
                'X-CSRFToken': document.querySelector('[name=csrfmiddlewaretoken]').value
            },
            body: formData
        });

        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }

        const data = await response.json();

        if (data.success) {
            // Success - reload the page
            window.location.reload();
        } else {
            throw new Error(data.error || 'Failed to add FAQ');
        }
    } catch (error) {
        console.error('Error:', error);
        errorDiv.textContent = error.message;
        errorDiv.classList.remove('d-none');
    } finally {
        submitBtn.disabled = false;
        loadingIndicator.classList.add('d-none');
    }
});

// Clear validation states when modal is hidden
$('#addFAQModal').on('hidden.bs.modal', function () {
    const form = document.getElementById('addFAQForm');
    form.classList.remove('was-validated');
    form.reset();
    const errorDiv = document.getElementById('addFAQError');
    errorDiv.classList.add('d-none');
    form.querySelectorAll('.is-invalid').forEach(el => el.classList.remove('is-invalid'));
});