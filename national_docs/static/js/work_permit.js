 document.addEventListener('DOMContentLoaded', function() {
    const form = document.getElementById('work-permit-form');
    const progressBar = document.getElementById('progress-bar');
    const totalFields = form.querySelectorAll('input:not([type="file"]), select, textarea').length;
    const requiredFileUploads = form.querySelectorAll('input[type="file"]').length;

    // Validation Messages
    const validationMessages = {
        fullName: 'Please enter your full name (at least two names)',
        dateOfBirth: 'You must be at least 18 years old',
        nationality: 'Please enter a valid nationality',
        passportNumber: 'Please enter a valid passport number',
        phone: 'Please enter a valid phone number (e.g., +220XXXXXXX)',
        jobTitle: 'Please enter your job title',
        employerName: 'Please enter your employer name',
        workStartDate: 'Work start date cannot be in the past',
        contractDuration: 'Contract duration must be between 1 and 60 months',
        skills: 'Please enter at least three relevant skills',
        educationLevel: 'Please select your education level',
        postLocation: 'Please select a post location',
        files: {
            pdf: 'Only PDF files are allowed',
            size: 'File size must be less than 5MB'
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

        nationality: (value) => value.trim().length > 0,

        passportNumber: (value) => /^[A-Z0-9]{6,9}$/i.test(value),

        phone: (value) => /^(\+220|00220)?[567]\d{7}$/.test(value.replace(/\s/g, '')),

        jobTitle: (value) => value.trim().length > 0,

        employerName: (value) => value.trim().length > 0,

        workStartDate: (value) => {
            const workStartDate = new Date(value);
            const today = new Date();
            today.setHours(0, 0, 0, 0); // Set to start of today
            return workStartDate >= today;
        },

        contractDuration: (value) => {
            const duration = parseInt(value, 10);
            return duration >= 1 && duration <= 60;
        },

        skills: (value) => {
            const skills = value.trim().split(',').filter(skill => skill.trim().length > 0);
            return skills.length >= 3;
        },

        educationLevel: (value) => value.trim() !== '',

        postLocation: (value) => value.trim() !== '',

        file: (file, allowedType, maxSize) => {
            if (!file) return { valid: false, message: 'File is required' };

            const fileSize = file.size / 1024 / 1024; // Convert to MB
            const fileType = file.type.toLowerCase();

            if (fileSize > maxSize) {
                return { valid: false, message: validationMessages.files.size };
            }

            if (fileType !== allowedType) {
                return { valid: false, message: validationMessages.files.pdf };
            }

            return { valid: true };
        }
    };

    // Show feedback
    const showFeedback = (input, isValid, message) => {
        const feedback = input.nextElementSibling || document.createElement('div');
        feedback.className = isValid ? 'valid-feedback' : 'invalid-feedback';
        feedback.textContent = message || '';

        if (!input.nextElementSibling) {
            input.parentNode.appendChild(feedback);
        }

        input.classList.toggle('is-valid', isValid);
        input.classList.toggle('is-invalid', !isValid);
    };

    // Handle file uploads
    const handleFileUpload = (input, allowedType, maxSize) => {
        const file = input.files[0];
        const validation = validators.file(file, allowedType, maxSize);
        showFeedback(input, validation.valid, validation.message);
    };

    // Real-time field validation
    const validateField = (input) => {
        const fieldId = input.id;
        let isValid = true;
        let message = '';

        switch (fieldId) {
            case 'full-name':
                isValid = validators.fullName(input.value);
                message = validationMessages.fullName;
                break;

            case 'date-of-birth':
                isValid = validators.dateOfBirth(input.value);
                message = validationMessages.dateOfBirth;
                break;

            case 'nationality':
                isValid = validators.nationality(input.value);
                message = validationMessages.nationality;
                break;

            case 'passport-number':
                isValid = validators.passportNumber(input.value);
                message = validationMessages.passportNumber;
                break;

            case 'phone':
                isValid = validators.phone(input.value);
                message = validationMessages.phone;
                break;

            case 'job-title':
                isValid = validators.jobTitle(input.value);
                message = validationMessages.jobTitle;
                break;

            case 'employer-name':
                isValid = validators.employerName(input.value);
                message = validationMessages.employerName;
                break;

            case 'work-start-date':
                isValid = validators.workStartDate(input.value);
                message = validationMessages.workStartDate;
                break;

            case 'contract-duration':
                isValid = validators.contractDuration(input.value);
                message = validationMessages.contractDuration;
                break;

            case 'skills':
                isValid = validators.skills(input.value);
                message = validationMessages.skills;
                break;

            case 'education-level':
                isValid = validators.educationLevel(input.value);
                message = validationMessages.educationLevel;
                break;

            case 'post-location':
                isValid = validators.postLocation(input.value);
                message = validationMessages.postLocation;
                break;
        }

        showFeedback(input, isValid, message);
        return isValid;
    };

    // Update progress bar
    const updateProgressBar = () => {
        const filledFields = Array.from(form.querySelectorAll('input:not([type="file"]), select, textarea')).filter(input => input.value.trim() !== '').length;
        const fileUploads = Array.from(form.querySelectorAll('input[type="file"]')).filter(input => input.files.length > 0).length;

        const completed = filledFields + fileUploads;
        const percentage = Math.round((completed / (totalFields + requiredFileUploads)) * 100);

        progressBar.style.width = `${percentage}%`;
        progressBar.textContent = `${percentage}% Complete`;
    };

    // Attach validation and progress bar update
    form.querySelectorAll('input, select, textarea').forEach(input => {
        input.addEventListener('input', () => {
            validateField(input);
            updateProgressBar();
        });

        if (input.type === 'file') {
            input.addEventListener('change', () => {
                handleFileUpload(input, 'application/pdf', 5);
                updateProgressBar();
            });
        }
    });

    // Form submission
    form.addEventListener('submit', (e) => {
        e.preventDefault();
        let isValid = true;

        form.querySelectorAll('input, select, textarea').forEach(input => {
            if (!validateField(input)) {
                isValid = false;
            }
        });

        if (isValid) {
            alert('Form submitted successfully!');
            // Add form submission logic here
        } else {
            alert('Please correct the errors in the form.');
        }
    });
});