// Initialize grade chart for student dashboard
function initializeGradeChart(grades) {
    const ctx = document.getElementById('gradeChart');
    if (!ctx) return;

    const subjects = [...new Set(grades.map(g => g.subject))];
    const gradesBySubject = subjects.map(subject => {
        const subjectGrades = grades.filter(g => g.subject === subject);
        return {
            subject,
            average: subjectGrades.reduce((sum, g) => sum + g.grade, 0) / subjectGrades.length
        };
    });

    new Chart(ctx, {
        type: 'bar',
        data: {
            labels: gradesBySubject.map(g => g.subject),
            datasets: [{
                label: 'Average Grade',
                data: gradesBySubject.map(g => g.average),
                backgroundColor: 'rgba(54, 162, 235, 0.5)',
                borderColor: 'rgba(54, 162, 235, 1)',
                borderWidth: 1
            }]
        },
        options: {
            responsive: true,
            scales: {
                y: {
                    beginAtZero: true,
                    max: 100
                }
            }
        }
    });
}

// Form validation for grade entry
document.addEventListener('DOMContentLoaded', function() {
    const gradeForm = document.querySelector('form[action*="add_grade"]');
    if (gradeForm) {
        gradeForm.addEventListener('submit', function(e) {
            const grade = parseFloat(document.getElementById('grade').value);
            if (grade < 0 || grade > 100) {
                e.preventDefault();
                alert('Grade must be between 0 and 100');
            }
        });
    }

    // Initialize tooltips
    const tooltipTriggerList = [].slice.call(document.querySelectorAll('[data-bs-toggle="tooltip"]'));
    tooltipTriggerList.map(function (tooltipTriggerEl) {
        return new bootstrap.Tooltip(tooltipTriggerEl);
    });

    // Handle grade deletion
    document.querySelectorAll('.delete-grade').forEach(button => {
        button.addEventListener('click', function() {
            if (confirm('Are you sure you want to delete this grade?')) {
                const gradeId = this.dataset.gradeId;
                fetch(`/delete_grade/${gradeId}`, {
                    method: 'DELETE',
                    headers: {
                        'Content-Type': 'application/json'
                    }
                }).then(response => {
                    if (response.ok) {
                        window.location.reload();
                    } else {
                        alert('Error deleting grade');
                    }
                });
            }
        });
    });

    // Handle grade editing
    document.querySelectorAll('.edit-grade').forEach(button => {
        button.addEventListener('click', function() {
            const gradeId = this.dataset.gradeId;
            const row = this.closest('tr');
            const subject = row.cells[1].textContent;
            const grade = row.cells[2].textContent;
            
            const newGrade = prompt(`Enter new grade for ${subject}:`, grade);
            if (newGrade !== null) {
                fetch(`/update_grade/${gradeId}`, {
                    method: 'PUT',
                    headers: {
                        'Content-Type': 'application/json'
                    },
                    body: JSON.stringify({
                        grade: parseFloat(newGrade)
                    })
                }).then(response => {
                    if (response.ok) {
                        window.location.reload();
                    } else {
                        alert('Error updating grade');
                    }
                });
            }
        });
    });
});
