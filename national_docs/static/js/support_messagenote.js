// Sender Details Handler Module
const SenderDetailsHandler = {
    // State management
    state: {
        senderId: null,
        chatId: null,
        csrfToken: document.querySelector('meta[name="csrf-token"]')?.content
    },

    // DOM Elements
    elements: {
        senderName: document.getElementById('modalSenderName'),
        applicationId: document.getElementById('modalApplicationID'),
        applicationDate: document.getElementById('modalApplicationDate'),
        applicationLocation: document.getElementById('modalApplicationLocation'),
        noteText: document.getElementById('noteText'),
        notesContainer: document.getElementById('notesContainer'),
        saveNoteBtn: document.getElementById('saveNoteBtn')
    },

    // API Endpoints
    endpoints: {
        getUserApplication: (senderId) => `/immigration/get_user_application/${senderId}/`,
        getUserNotes: (senderId) => `/immigration/get_user_notes/${senderId}/`,
        saveNote: '/immigration/save_note/'
    },

    // Initialize the module
    init() {
        this.attachEventListeners();
        this.validateSetup();
    },

    // Validate required elements and setup
    validateSetup() {
        if (!this.state.csrfToken) {
            console.error('CSRF token meta tag is missing');
        }

        // Validate required DOM elements
        Object.entries(this.elements).forEach(([key, element]) => {
            if (!element) {
                console.error(`Required element "${key}" not found in the DOM`);
            }
        });
    },

    // Attach event listeners
    attachEventListeners() {
        document.querySelectorAll('.sender-details-link').forEach(link => {
            link.addEventListener('click', (e) => this.handleSenderClick(e));
        });

        this.elements.saveNoteBtn?.addEventListener('click', () => this.handleNoteSave());
    },

    // Handle sender link click
    async handleSenderClick(event) {
        const link = event.currentTarget;
        this.state.senderId = link.dataset.senderId;
        this.state.chatId = link.dataset.chatId;

        // Update sender name and reset fields
        this.elements.senderName.textContent = link.dataset.senderName;
        this.resetFields();

        // Fetch data
        await Promise.all([
            this.fetchApplicationDetails(),
            this.fetchUserNotes()
        ]);
    },

    // Reset fields to loading state
    resetFields() {
        this.elements.applicationId.textContent = 'Loading...';
        this.elements.applicationDate.textContent = 'Loading...';
        this.elements.applicationLocation.textContent = 'Loading...';
        this.elements.noteText.value = '';
        this.elements.notesContainer.innerHTML = '<p class="text-muted">Loading notes...</p>';
    },

    // Fetch application details
    async fetchApplicationDetails() {
        try {
            const response = await fetch(this.endpoints.getUserApplication(this.state.senderId));
            const data = await response.json();

            if (data.success) {
                this.updateApplicationDetails(data);
            } else {
                this.handleApplicationError();
            }
        } catch (error) {
            console.error('Error fetching application details:', error);
            this.handleApplicationError();
        }
    },

    // Update application details in the DOM
    updateApplicationDetails(data) {
        this.elements.applicationId.textContent = data.application_id;
        this.elements.applicationDate.textContent = data.application_date;
        this.elements.applicationLocation.textContent = data.application_location;
    },

    // Handle application error state
    handleApplicationError() {
        this.elements.applicationId.textContent = 'No application found';
        this.elements.applicationDate.textContent = '-';
        this.elements.applicationLocation.textContent = '-';
    },

    // Fetch user notes
    async fetchUserNotes() {
        try {
            const response = await fetch(this.endpoints.getUserNotes(this.state.senderId));
            const data = await response.json();
            this.updateNotesContainer(data.notes);
        } catch (error) {
            console.error('Error fetching user notes:', error);
            this.elements.notesContainer.innerHTML = '<p class="text-danger">Error fetching notes.</p>';
        }
    },

    // Update notes container with fetched notes
    updateNotesContainer(notes) {
        if (!notes?.length) {
            this.elements.notesContainer.innerHTML = '<p class="text-muted">No notes available.</p>';
            return;
        }

        const notesHtml = notes.map(note => this.createNoteHTML(note)).join('');
        this.elements.notesContainer.innerHTML = notesHtml;
    },

    // Create HTML for a single note
    createNoteHTML(note) {
        return `
            <div class="note">
                <p><strong>${note.created_by}</strong>: ${note.note}</p>
                <small class="text-muted">${note.created_at}</small>
            </div>
        `;
    },

    // Handle note save
    async handleNoteSave() {
        const noteText = this.elements.noteText.value.trim();

        if (!noteText) {
            this.showNotification('Please enter a note before saving.', 'warning');
            return;
        }

        try {
            const response = await this.saveNote(noteText);
            if (response.success) {
                this.handleSuccessfulNoteSave(noteText);
            } else {
                this.showNotification(`Failed to save note: ${response.error}`, 'error');
            }
        } catch (error) {
            console.error('Error saving note:', error);
            this.showNotification('An error occurred while saving the note.', 'error');
        }
    },

    // Save note to the server
    async saveNote(noteText) {
        const formData = new FormData();
        formData.append('sender_id', this.state.senderId);
        formData.append('chat_id', this.state.chatId);
        formData.append('note', noteText);
        formData.append('csrfmiddlewaretoken', this.state.csrfToken);

        const response = await fetch(this.endpoints.saveNote, {
            method: 'POST',
            body: formData
        });

        return response.json();
    },

    // Handle successful note save
    handleSuccessfulNoteSave(noteText) {
        const newNoteHtml = this.createNoteHTML({
            created_by: window.currentUser?.fullName || 'User',
            note: noteText,
            created_at: new Date().toLocaleString()
        });

        this.elements.notesContainer.insertAdjacentHTML('afterbegin', newNoteHtml);
        this.elements.noteText.value = '';
        this.showNotification('Note saved successfully.', 'success');
    },

    // Show notification
    showNotification(message, type = 'info') {
        // If using a notification library, integrate it here
        alert(message); // Fallback to alert if no notification system is available
    }
};

// Initialize the module when DOM is ready
document.addEventListener('DOMContentLoaded', () => SenderDetailsHandler.init());

// Export the module if using modules
export default SenderDetailsHandler;