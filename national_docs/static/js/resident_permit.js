    document.addEventListener('DOMContentLoaded', function() {
    // Form Elements
    const form = document.getElementById('resident-permit-form');
    const progressBar = document.getElementById('progress-bar');
    const totalFields = form.querySelectorAll('input, select, textarea').length;

    // Validation Messages
    const validationMessages = {
        fullName: {
            pattern: 'Please enter your full name (at least two names)',
            required: 'Full name is required'
        },
        dateOfBirth: {
            age: 'You must be at least 18 years old',
            required: 'Date of birth is required'
        },
        nationality: {
            pattern: 'Please enter a valid nationality',
            required: 'Nationality is required'
        },
        passportNumber: {
            pattern: 'Please enter a valid passport number (e.g., A1234567)',
            required: 'Passport number is required'
        },
        dateOfEntry: {
            future: 'Entry date cannot be in the future',
            required: 'Date of entry is required'
        },
        phone: {
            pattern: 'Please enter a valid phone number',
            required: 'Phone number is required'
        },
        email: {
            pattern: 'Please enter a valid email address',
            required: 'Email address is required'
        }
    };

    // Validation Rules
    const validators = {
        fullName: (value) => {
            const names = value.trim().split(' ');
            return names.length >= 2 && names.every(name => name.length >= 2);
        },

        dateOfBirth: (value) => {
            const birthDate = new Date(value);
            const today = new Date();
            const age = today.getFullYear() - birthDate.getFullYear();
            const monthDiff = today.getMonth() - birthDate.getMonth();

            if (monthDiff < 0 || (monthDiff === 0 && today.getDate() < birthDate.getDate())) {
                return age - 1 >= 18;
            }
            return age >= 18;
        },

        nationality: (value) => {
            return value.trim().length >= 2 && /^[a-zA-Z\s-]+$/.test(value);
        },

        passportNumber: (value) => {
            return /^[A-Z0-9]{6,9}$/.test(value.trim());
        },

        dateOfEntry: (value) => {
            const entryDate = new Date(value);
            const today = new Date();
            return entryDate <= today;
        },

        phone: (value) => {
            // Gambian phone number format
            return /^(\+220|00220)?[567]\d{7}$/.test(value.replace(/\s/g, ''));
        },

        email: (value) => {
            return /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(value);
        },

        file: (file, maxSize, allowedTypes) => {
            if (!file) return { valid: false, message: 'File is required' };

            const fileSize = file.size / 1024 / 1024; // Convert to MB
            const fileType = file.type.toLowerCase();

            if (fileSize > maxSize) {
                return { valid: false, message: `File size must be less than ${maxSize}MB` };
            }

            if (!allowedTypes.includes(fileType)) {
                return { valid: false, message: `Only ${allowedTypes.join(', ')} files are allowed` };
            }

            return { valid: true };
        }
    };

    // Progress Bar Functions
    function updateProgress() {
        const fields = form.querySelectorAll('input, select, textarea');
        let validFields = 0;

        fields.forEach(field => {
            if (isFieldValid(field)) {
                validFields++;
            }
        });

        const progress = Math.round((validFields / totalFields) * 100);
        setProgress(progress);
    }

    function setProgress(progress) {
        progressBar.style.width = `${progress}%`;
        progressBar.setAttribute('aria-valuenow', progress);

        // Update progress bar color based on completion
        if (progress < 33) {
            progressBar.className = 'progress-bar bg-danger';
        } else if (progress < 66) {
            progressBar.className = 'progress-bar bg-warning';
        } else {
            progressBar.className = 'progress-bar bg-success';
        }
    }

    // File Upload Handler
    function handleFileUpload(input, fileNameElement, maxSize, allowedTypes) {
        const file = input.files[0];
        const fileNameDisplay = document.getElementById(fileNameElement);

        if (file) {
            const validation = validators.file(file, maxSize, allowedTypes);
            showFeedback(input, validation.valid, validation.message);

            if (validation.valid) {
                fileNameDisplay.textContent = `Selected: ${file.name}`;
                fileNameDisplay.className = 'file-name text-success mt-2';
            } else {
                fileNameDisplay.textContent = validation.message;
                fileNameDisplay.className = 'file-name text-danger mt-2';
            }
        } else {
            fileNameDisplay.textContent = '';
        }
        updateProgress();
    }

    // Validation Feedback
    function showFeedback(input, isValid, message) {
        const formGroup = input.closest('.form-floating') || input.closest('.upload-card');
        const feedback = formGroup.querySelector('.invalid-feedback');

        if (feedback) {
            feedback.textContent = message || '';
        }

        input.classList.toggle('is-valid', isValid);
        input.classList.toggle('is-invalid', !isValid);

        // Update progress after validation
        updateProgress();
    }

    // Field Validation
    function isFieldValid(field) {
        if (!field.required) return true;

        switch(field.id) {
            case 'full-name':
                return validators.fullName(field.value);
            case 'date-of-birth':
                return validators.dateOfBirth(field.value);
            case 'nationality':
                return validators.nationality(field.value);
            case 'passport-number':
                return validators.passportNumber(field.value);
            case 'date-of-entry':
                return validators.dateOfEntry(field.value);
            case 'phone':
                return validators.phone(field.value);
            case 'email':
                return validators.email(field.value);
            case 'passport-photo':
            case 'resident-permit-document':
                return field.files.length > 0;
            default:
                return field.value.trim() !== '';
        }
    }

    // Setup File Upload Listeners
    document.getElementById('passport-photo').addEventListener('change', function() {
        handleFileUpload(this, 'passport-photo-file-name', 2, ['image/jpeg', 'image/png']);
    });

    document.getElementById('resident-permit-document').addEventListener('change', function() {
        handleFileUpload(this, 'resident-permit-file-name', 5, ['application/pdf', 'image/jpeg', 'image/png']);
    });

    // Real-time Validation
    form.querySelectorAll('input, select, textarea').forEach(input => {
        input.addEventListener('blur', function() {
            validateField(this);
        });

        input.addEventListener('input', function() {
            if (this.classList.contains('is-invalid')) {
                validateField(this);
            }
            updateProgress();
        });

        // Add change event for select elements
        if (input.tagName === 'SELECT') {
            input.addEventListener('change', function() {
                validateField(this);
            });
        }
    });

    // Field Validation Function
    function validateField(input) {
        let isValid = true;
        let message = '';

        if (input.required && !input.value.trim()) {
            isValid = false;
            message = `${input.labels[0].textContent.replace(' *', '')} is required`;
        } else {
            switch(input.id) {
                case 'full-name':
                    isValid = validators.fullName(input.value);
                    message = isValid ? '' : validationMessages.fullName.pattern;
                    break;

                case 'date-of-birth':
                    isValid = validators.dateOfBirth(input.value);
                    message = isValid ? '' : validationMessages.dateOfBirth.age;
                    break;

                case 'nationality':
                    isValid = validators.nationality(input.value);
                    message = isValid ? '' : validationMessages.nationality.pattern;
                    break;

                case 'passport-number':
                    isValid = validators.passportNumber(input.value);
                    message = isValid ? '' : validationMessages.passportNumber.pattern;
                    break;

                case 'date-of-entry':
                    isValid = validators.dateOfEntry(input.value);
                    message = isValid ? '' : validationMessages.dateOfEntry.future;
                    break;

                case 'phone':
                    isValid = validators.phone(input.value);
                    message = isValid ? '' : validationMessages.phone.pattern;
                    break;

                case 'email':
                    isValid = validators.email(input.value);
                    message = isValid ? '' : validationMessages.email.pattern;
                    break;
            }
        }

        showFeedback(input, isValid, message);
        return isValid;
    }

    // Form Submit Handler
    form.addEventListener('submit', function(e) {
        e.preventDefault();
        let isValid = true;

        // Validate all fields
        form.querySelectorAll('input, select, textarea').forEach(field => {
            if (!validateField(field)) {
                isValid = false;
            }
        });

        if (isValid) {
            // Submit form if all validations pass
            this.submit();
        } else {
            // Scroll to first invalid field
            const firstInvalid = form.querySelector('.is-invalid');
            if (firstInvalid) {
                firstInvalid.scrollIntoView({ behavior: 'smooth', block: 'center' });
            }
        }
    });

    // Initial progress update
    updateProgress();
});