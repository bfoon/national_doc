// Call Notes Management Module
class CallNotesManager {
    constructor() {
        this.currentSenderId = null;
        this.currentChatId = null;
        this.csrfToken = document.querySelector('[name=csrfmiddlewaretoken]')?.value;

        // DOM Elements
        this.elements = {
            senderDetailsLinks: document.querySelectorAll('.sender-details-link'),
            saveNoteBtn: document.getElementById('saveNoteBtn'),
            noteText: document.getElementById('noteText'),
            notesContainer: document.getElementById('notesContainer'),
            closeNoteButtons: document.querySelectorAll('.close-note-btn'),
            modalElements: {
                senderName: document.getElementById('modalSenderName'),
                applicationId: document.getElementById('modalApplicationID'),
                applicationDate: document.getElementById('modalApplicationDate'),
                applicationLocation: document.getElementById('modalApplicationLocation')
            }
        };

        this.initialize();
    }

    initialize() {
        if (!this.csrfToken) {
            console.error('CSRF token not found');
            return;
        }

        this.attachEventListeners();
    }

    attachEventListeners() {
        // Attach sender details click handlers
        this.elements.senderDetailsLinks.forEach(link => {
            link.addEventListener('click', (e) => this.handleSenderDetailsClick(e));
        });

        // Attach save note handler
        if (this.elements.saveNoteBtn) {
            this.elements.saveNoteBtn.addEventListener('click', () => this.handleSaveNote());
        }

        // Attach close note handlers
        this.elements.closeNoteButtons.forEach(button => {
            button.addEventListener('click', (e) => this.handleCloseNote(e));
        });
    }

    async handleSenderDetailsClick(event) {
        const link = event.currentTarget;
        this.currentSenderId = link.dataset.senderId;
        this.currentChatId = link.dataset.chatId;
        const senderName = link.dataset.senderName;

        // Update modal content
        if (this.elements.modalElements.senderName) {
            this.elements.modalElements.senderName.textContent = senderName;
        }

        // Set loading states
        this.setLoadingState(true);

        try {
            await Promise.all([
                this.fetchApplicationDetails(),
                this.fetchUserNotes()
            ]);
        } catch (error) {
            this.handleError(error);
        } finally {
            this.setLoadingState(false);
        }
    }

    async fetchApplicationDetails() {
        try {
            const response = await fetch(`/immigration/get_user_application/${this.currentSenderId}/`);
            if (!response.ok) throw new Error(`HTTP error! status: ${response.status}`);

            const data = await response.json();

            if (data.success) {
                this.updateApplicationDetails(data);
            } else {
                this.clearApplicationDetails();
            }
        } catch (error) {
            this.handleError(error, 'Failed to fetch application details');
            this.clearApplicationDetails();
        }
    }

    async fetchUserNotes() {
        try {
            const response = await fetch(`/immigration/get_user_notes/${this.currentSenderId}/`);
            if (!response.ok) throw new Error(`HTTP error! status: ${response.status}`);

            const data = await response.json();
            this.updateNotesDisplay(data.notes);
        } catch (error) {
            this.handleError(error, 'Failed to fetch user notes');
            this.updateNotesDisplay([]);
        }
    }

    async handleSaveNote() {
        const noteText = this.elements.noteText?.value.trim();

        if (!noteText) {
            this.showNotification('Please enter a note before saving.', 'warning');
            return;
        }

        try {
            const formData = new FormData();
            formData.append('sender_id', this.currentSenderId);
            formData.append('chat_id', this.currentChatId);
            formData.append('note', noteText);
            formData.append('csrfmiddlewaretoken', this.csrfToken);

            const response = await fetch('/immigration/save_note/', {
                method: 'POST',
                body: formData
            });

            if (!response.ok) throw new Error(`HTTP error! status: ${response.status}`);

            const data = await response.json();

            if (data.success) {
                this.addNewNoteToDisplay(noteText);
                this.clearNoteInput();
                this.showNotification('Note saved successfully.', 'success');
            } else {
                throw new Error(data.error || 'Failed to save note');
            }
        } catch (error) {
            this.handleError(error, 'Failed to save note');
        }
    }

    async handleCloseNote(event) {
        const button = event.currentTarget;
        const noteId = button.dataset.noteId;
        const noteItem = button.closest('.list-group-item');

        if (!noteId || !noteItem) {
            console.error('Required note data not found');
            return;
        }

        if (!confirm('Are you sure you want to close this note?')) return;

        try {
            const response = await fetch(`/immigration/close_call_note/${noteId}/`, {
                method: 'POST',
                headers: {
                    'X-CSRFToken': this.csrfToken,
                    'Content-Type': 'application/json'
                }
            });

            if (!response.ok) throw new Error(`HTTP error! status: ${response.status}`);

            const data = await response.json();

            if (data.success) {
                this.updateNoteDisplay(noteItem, button);
            } else {
                throw new Error(data.error || 'Failed to close note');
            }
        } catch (error) {
            this.handleError(error, 'Failed to close note');
        }
    }

    // Helper Methods
    setLoadingState(isLoading) {
        const loadingText = 'Loading...';
        const elements = this.elements.modalElements;

        if (isLoading) {
            Object.values(elements).forEach(el => {
                if (el) el.textContent = loadingText;
            });
            if (this.elements.notesContainer) {
                this.elements.notesContainer.innerHTML = '<p class="text-muted">Loading notes...</p>';
            }
        }
    }

    updateApplicationDetails(data) {
        const elements = this.elements.modalElements;
        if (elements.applicationId) elements.applicationId.textContent = data.application_id;
        if (elements.applicationDate) elements.applicationDate.textContent = data.application_date;
        if (elements.applicationLocation) elements.applicationLocation.textContent = data.application_location;
    }

    clearApplicationDetails() {
        const elements = this.elements.modalElements;
        Object.values(elements).forEach(el => {
            if (el) el.textContent = '-';
        });
        if (elements.applicationId) elements.applicationId.textContent = 'No application found';
    }

    updateNotesDisplay(notes) {
        if (!this.elements.notesContainer) return;

        if (!notes?.length) {
            this.elements.notesContainer.innerHTML = '<p class="text-muted">No notes available.</p>';
            return;
        }

        const notesHtml = notes.map(note => this.createNoteHTML(note)).join('');
        this.elements.notesContainer.innerHTML = notesHtml;
    }

    addNewNoteToDisplay(noteText) {
        if (!this.elements.notesContainer) return;

        const newNoteHtml = this.createNoteHTML({
            note: noteText,
            created_by: 'Current User', // This should be replaced with actual user name
            created_at: new Date().toLocaleString()
        });

        this.elements.notesContainer.insertAdjacentHTML('afterbegin', newNoteHtml);
    }

    createNoteHTML(note) {
        return `
            <div class="note">
                <p><strong>${this.escapeHtml(note.created_by)}</strong>: ${this.escapeHtml(note.note)}</p>
                <small class="text-muted">${this.escapeHtml(note.created_at)}</small>
            </div>
        `;
    }

    updateNoteDisplay(noteItem, button) {
        const noteText = noteItem.querySelector('.note-text');
        if (noteText) noteText.classList.add('completed');
        button.classList.replace('btn-danger', 'btn-success');
        const icon = button.querySelector('i');
        if (icon) icon.classList.replace('fa-times-circle', 'fa-check-circle');
        button.disabled = true;
    }

    clearNoteInput() {
        if (this.elements.noteText) {
            this.elements.noteText.value = '';
        }
    }

    showNotification(message, type = 'info') {
        // Implementation depends on your UI framework
        // Example using toastr
        if (window.toastr) {
            toastr[type](message);
        } else {
            alert(message);
        }
    }

    handleError(error, customMessage = '') {
        console.error('Error:', error);
        const errorMessage = customMessage || error.message || 'An error occurred';
        this.showNotification(errorMessage, 'error');
    }

    escapeHtml(unsafe) {
        return unsafe
            .replace(/&/g, "&amp;")
            .replace(/</g, "&lt;")
            .replace(/>/g, "&gt;")
            .replace(/"/g, "&quot;")
            .replace(/'/g, "&#039;");
    }
}

// Initialize the call notes manager when the DOM is ready
document.addEventListener('DOMContentLoaded', () => {
    new CallNotesManager();
});