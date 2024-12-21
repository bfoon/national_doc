// Utility functions
const handleApiError = (error, customMessage) => {
    console.error('Error:', error);
    alert(customMessage || 'An error occurred. Please try again.');
};

// Animation function for counters
function animateCountUp(targetElement, start, end, duration) {
    if (!targetElement) return;

    const increment = Math.ceil((end - start) / (duration / 10));
    let current = start;

    const counter = setInterval(() => {
        current += increment;
        if (current >= end) {
            current = end;
            clearInterval(counter);
        }
        targetElement.textContent = current;
    }, 10);
}

// Initialize the dashboard functionality
document.addEventListener('DOMContentLoaded', function() {
    // Initialize counters
    const initializeCounters = () => {
        const counters = document.querySelectorAll('[data-count]');
        counters.forEach(counter => {
            const value = parseInt(counter.dataset.count, 10);
            if (!isNaN(value)) {
                animateCountUp(counter, 0, value, 1000);
            }
        });
    };

    // Handle Respond button clicks
    const respondButtons = document.querySelectorAll('.respond-btn');
    const chatIdInput = document.getElementById('chatId');
    const senderNameSpan = document.getElementById('senderName');

    respondButtons.forEach(button => {
        button.addEventListener('click', function() {
            chatIdInput.value = this.dataset.chatId;
            senderNameSpan.textContent = this.dataset.senderName;
        });
    });

    // Handle Close chat functionality
    const closeButtons = document.querySelectorAll('.close-btn');
    closeButtons.forEach(button => {
        button.addEventListener('click', function() {
            const chatId = this.dataset.chatId;
            fetch("/close_chat/", {
                method: 'POST',
                headers: {
                    'X-CSRFToken': document.querySelector('[name=csrfmiddlewaretoken]').value,
                    'Content-Type': 'application/x-www-form-urlencoded'
                },
                body: `chat_id=${chatId}`
            })
            .then(response => response.json())
            .then(data => {
                if (data.success) {
                    document.getElementById(`chat-${chatId}`)?.remove();
                } else {
                    handleApiError(data.error, `Failed to close chat: ${data.error}`);
                }
            })
            .catch(error => handleApiError(error));
        });
    });

    // FAQ Search functionality
    const setupFAQSearch = () => {
        const searchFAQ = document.getElementById('searchFAQ');
        if (!searchFAQ) return;

        let searchTimeout;
        const debounceDelay = 300;

        searchFAQ.addEventListener('keyup', function() {
            clearTimeout(searchTimeout);
            const query = this.value.trim();
            const faqContainer = document.querySelector('.card-body .list-group');

            if (!faqContainer) return;

            // Show loading state
            faqContainer.innerHTML = '<li class="list-group-item text-center"><i class="fas fa-spinner fa-spin"></i> Searching...</li>';

            searchTimeout = setTimeout(() => {
                performFAQSearch(query, faqContainer);
            }, debounceDelay);
        });
    };

    // FAQ Search helper function
    const performFAQSearch = async (query, container) => {
        try {
            const response = await fetch(`/immigration/search_faqs/?q=${encodeURIComponent(query)}`, {
                headers: {
                    'X-Requested-With': 'XMLHttpRequest',
                    'Accept': 'application/json',
                    'X-CSRFToken': document.querySelector('[name=csrfmiddlewaretoken]').value
                }
            });

            if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`);
            }

            const data = await response.json();

            if (data.success === false) {
                throw new Error(data.error || 'Server returned an error');
            }

            updateFAQResults(data.faqs, container);
        } catch (error) {
            console.error('Search error:', error);
            container.innerHTML = `
                <li class="list-group-item text-danger text-center">
                    An error occurred while searching. Please try again.
                    <br>
                    <small>${error.message}</small>
                </li>`;
        }
    };

    // Update FAQ results in container
    const updateFAQResults = (faqs, container) => {
        if (!Array.isArray(faqs)) {
            container.innerHTML = '<li class="list-group-item text-muted text-center">Invalid response format</li>';
            return;
        }

        if (faqs.length === 0) {
            container.innerHTML = '<li class="list-group-item text-muted text-center">No FAQs found matching your search.</li>';
            return;
        }

        const faqsHtml = faqs.map(faq => createFAQElement(faq)).join('');
        container.innerHTML = faqsHtml;
        attachEditFAQListeners();
    };

    // Create FAQ HTML element
    const createFAQElement = (faq) => {
        return `
            <li class="list-group-item d-flex justify-content-between align-items-center">
                <div>
                    <strong>${escapeHtml(faq.question)}</strong><br>
                    <p class="mb-0">${escapeHtml(faq.answer)}</p>
                </div>
                <div class="btn-group">
                    <button class="btn btn-warning btn-sm edit-faq-btn"
                            data-toggle="modal"
                            data-target="#updateFAQModal"
                            data-faq-id="${faq.id}"
                            data-question="${escapeHtml(faq.question)}"
                            data-answer="${escapeHtml(faq.answer)}">
                        <i class="fas fa-edit"></i> Edit
                    </button>
                    <a href="/immigration/delete_faq/${faq.id}/"
                       class="btn btn-danger btn-sm"
                       onclick="return confirm('Are you sure you want to delete this FAQ?');">
                        <i class="fas fa-trash-alt"></i> Delete
                    </a>
                </div>
            </li>
        `;
    };

    // Attach event listeners to FAQ edit buttons
    function attachEditFAQListeners() {
        document.querySelectorAll('.edit-faq-btn').forEach(button => {
            button.addEventListener('click', function() {
                const faqId = this.dataset.faqId;
                const question = this.dataset.question;
                const answer = this.dataset.answer;

                const idInput = document.getElementById('faqId');
                const questionInput = document.getElementById('editQuestion');
                const answerInput = document.getElementById('editAnswer');

                if (idInput && questionInput && answerInput) {
                    idInput.value = faqId;
                    questionInput.value = question;
                    answerInput.value = answer;
                }
            });
        });
    }

    // Handle FAQ update form submission
    const setupFAQUpdate = () => {
        const updateFAQForm = document.getElementById('updateFAQForm');
        if (!updateFAQForm) return;

        updateFAQForm.addEventListener('submit', async function(e) {
            e.preventDefault();
            const formData = new FormData(this);
            const faqId = formData.get('faq_id');

            try {
                const response = await fetch(`/immigration/update_faq/${faqId}/`, {
                    method: 'POST',
                    body: formData,
                    headers: {
                        'X-CSRFToken': document.querySelector('[name=csrfmiddlewaretoken]').value
                    }
                });
                const data = await response.json();

                if (data.success) {
                    alert('FAQ updated successfully!');
                    location.reload();
                } else {
                    handleApiError(null, `Failed to update FAQ: ${data.error}`);
                }
            } catch (error) {
                handleApiError(error);
            }
        });
    };

    // Handle Add FAQ form submission
    const setupAddFAQ = () => {
        const addFAQForm = document.getElementById('addFAQForm');
        if (!addFAQForm) return;

        addFAQForm.addEventListener('submit', async function(e) {
            e.preventDefault();
            if (!validateFAQForm(this)) return;

            const submitBtn = document.getElementById('addFAQSubmit');
            const loadingIndicator = this.querySelector('.loading-indicator');

            try {
                await submitFAQForm(this, submitBtn, loadingIndicator);
            } catch (error) {
                const errorDiv = document.getElementById('addFAQError');
                errorDiv.textContent = error.message;
                errorDiv.classList.remove('d-none');
            }
        });
    };

    // Validate FAQ form
    const validateFAQForm = (form) => {
        form.classList.remove('was-validated');
        const errorDiv = document.getElementById('addFAQError');
        errorDiv.classList.add('d-none');

        const question = document.getElementById('newQuestion');
        const answer = document.getElementById('newAnswer');
        let isValid = true;

        if (question.value.trim().length < 10) {
            question.classList.add('is-invalid');
            isValid = false;
        }

        if (answer.value.trim().length < 20) {
            answer.classList.add('is-invalid');
            isValid = false;
        }

        if (!isValid) {
            errorDiv.textContent = 'Please correct the errors before submitting.';
            errorDiv.classList.remove('d-none');
        }

        return isValid;
    };

    // Submit FAQ form
    const submitFAQForm = async (form, submitBtn, loadingIndicator) => {
        submitBtn.disabled = true;
        loadingIndicator.classList.remove('d-none');

        try {
            const formData = new FormData(form);
            const response = await fetch("/add_faq/", {
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
                window.location.reload();
            } else {
                throw new Error(data.error || 'Failed to add FAQ');
            }
        } finally {
            submitBtn.disabled = false;
            loadingIndicator.classList.add('d-none');
        }
    };

    // Helper function to escape HTML
    const escapeHtml = (unsafe) => {
        return unsafe
            .replace(/&/g, "&amp;")
            .replace(/</g, "&lt;")
            .replace(/>/g, "&gt;")
            .replace(/"/g, "&quot;")
            .replace(/'/g, "&#039;");
    };

    // Clear FAQ form validation states when modal is hidden
    const setupModalReset = () => {
        const addFAQModal = document.getElementById('addFAQModal');
        if (!addFAQModal) return;

        addFAQModal.addEventListener('hidden.bs.modal', function () {
            const form = document.getElementById('addFAQForm');
            if (!form) return;

            form.classList.remove('was-validated');
            form.reset();
            const errorDiv = document.getElementById('addFAQError');
            if (errorDiv) errorDiv.classList.add('d-none');
            form.querySelectorAll('.is-invalid').forEach(el => el.classList.remove('is-invalid'));
        });
    };

    // Initialize all functionality
    initializeCounters();
    setupFAQSearch();
    setupFAQUpdate();
    setupAddFAQ();
    setupModalReset();
});