// Configuration for MySQL API endpoint
const API_BASE_URL = 'db_connect.php';

// State management
let currentEntries = [];
let currentFilter = 'all';
let searchQuery = '';

// DOM Elements
const entriesContainer = document.querySelector('.entries-container');
const loadingSpinner = document.getElementById('loadingSpinner');
const noResults = document.getElementById('noResults');
const searchInput = document.getElementById('searchInput');
const languageFilter = document.getElementById('languageFilter');
const refreshBtn = document.getElementById('refreshBtn');
const modal = document.getElementById('imageModal');
const modalImage = document.getElementById('modalImage');
const closeModal = document.querySelector('.close-modal');

// Event Listeners
document.addEventListener('DOMContentLoaded', initializeApp);
searchInput.addEventListener('input', handleSearch);
languageFilter.addEventListener('change', handleFilterChange);
refreshBtn.addEventListener('click', fetchData);
closeModal.addEventListener('click', () => modal.style.display = 'none');
window.addEventListener('click', (e) => {
    if (e.target === modal) modal.style.display = 'none';
});

async function initializeApp() {
    await fetchData();
    updateStats();
}

async function fetchData() {
    showLoading(true);
    try {
        const response = await fetch(API_BASE_URL);
        if (!response.ok) throw new Error('Network response was not ok');
        const result = await response.json();
        
        if (result.success) {
            currentEntries = result.data;
            filterAndRenderEntries();
            updateStats();
        } else {
            throw new Error(result.error || 'Failed to fetch data');
        }
    } catch (error) {
        console.error('Error fetching data:', error);
        showError('Failed to load data. Please try again later.');
    } finally {
        showLoading(false);
    }
}

function filterAndRenderEntries() {
    let filteredEntries = currentEntries;

    // Apply language filter
    if (currentFilter !== 'all') {
        filteredEntries = filteredEntries.filter(entry => {
            const hasText = entry[`${currentFilter}_translation`]?.trim();
            return hasText;
        });
    }

    // Apply search filter
    if (searchQuery) {
        const query = searchQuery.toLowerCase();
        filteredEntries = filteredEntries.filter(entry => {
            return (
                entry.original_text?.toLowerCase().includes(query) ||
                entry.english_translation?.toLowerCase().includes(query) ||
                entry.hindi_translation?.toLowerCase().includes(query) ||
                entry.marathi_translation?.toLowerCase().includes(query)
            );
        });
    }

    renderEntries(filteredEntries);
}

function renderEntries(entries) {
    entriesContainer.innerHTML = '';
    
    if (entries.length === 0) {
        noResults.style.display = 'block';
        return;
    }
    
    noResults.style.display = 'none';
    
    entries.forEach(entry => {
        const card = createEntryCard(entry);
        entriesContainer.appendChild(card);
    });
}

function createEntryCard(entry) {
    const card = document.createElement('div');
    card.className = 'entry-card';
    
    const imageData = entry.image;
    const timestamp = new Date(entry.timestamp).toLocaleString();
    
    card.innerHTML = `
        <img src="data:image/jpeg;base64,${imageData}" alt="Captured Image" class="entry-image">
        <div class="translation-text">
            ${entry.original_text ? `
                <h3>Original Text</h3>
                <p>${entry.original_text}</p>
            ` : ''}
            
            ${entry.english_translation ? `
                <h3>English</h3>
                <p>${entry.english_translation}</p>
            ` : ''}
            
            ${entry.hindi_translation ? `
                <h3>Hindi</h3>
                <p>${entry.hindi_translation}</p>
            ` : ''}
            
            ${entry.marathi_translation ? `
                <h3>Marathi</h3>
                <p>${entry.marathi_translation}</p>
            ` : ''}
            
            <div class="timestamp">${timestamp}</div>
        </div>
    `;

    // Add click event for image modal
    const image = card.querySelector('.entry-image');
    image.addEventListener('click', () => {
        modalImage.src = `data:image/jpeg;base64,${imageData}`;
        modal.style.display = 'block';
    });

    return card;
}

function updateStats() {
    const totalEntries = document.getElementById('totalEntries');
    const todayEntries = document.getElementById('todayEntries');
    
    totalEntries.textContent = currentEntries.length;
    
    const today = new Date().toDateString();
    const todayCount = currentEntries.filter(entry => 
        new Date(entry.timestamp).toDateString() === today
    ).length;
    
    todayEntries.textContent = todayCount;
}

function handleSearch(e) {
    searchQuery = e.target.value;
    filterAndRenderEntries();
}

function handleFilterChange(e) {
    currentFilter = e.target.value;
    filterAndRenderEntries();
}

function showLoading(show) {
    loadingSpinner.style.display = show ? 'block' : 'none';
    entriesContainer.style.display = show ? 'none' : 'grid';
}

function showError(message) {
    const errorDiv = document.createElement('div');
    errorDiv.className = 'error-message';
    errorDiv.textContent = message;
    entriesContainer.appendChild(errorDiv);
}
