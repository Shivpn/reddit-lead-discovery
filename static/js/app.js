// ===== STATE MANAGEMENT =====
let currentStep = 1;
let userPrompt = '';
let userProfile = { company_name: '', business_niche: '' };
let discoveredSubreddits = [];
let selectedSubreddits = [];
let allLeads = [];
let currentAIResponse = null;
let manualSubreddits = [];

// ===== DOM ELEMENTS =====
const elements = {
    // Step 1
    userPromptInput: document.getElementById('userPrompt'),
    companyNameInput: document.getElementById('companyName'),
    businessNicheInput: document.getElementById('businessNiche'),
    discoverBtn: document.getElementById('discoverBtn'),
    step1Section: document.getElementById('step1Section'),
    
    // Step 2
    step2Section: document.getElementById('step2Section'),
    subredditGrid: document.getElementById('subredditGrid'),
    manualSubredditInput: document.getElementById('manualSubredditInput'),
    addManualBtn: document.getElementById('addManualBtn'), 
    manualSubreddits: document.getElementById('manualSubreddits'), 
    viewSavedBtn: document.getElementById('viewSavedBtn'), 
    savedCount: document.getElementById('savedCount'), 
    selectedCount: document.getElementById('selectedCount'),
    backToStep1: document.getElementById('backToStep1'),
    fetchLeadsBtn: document.getElementById('fetchLeadsBtn'),
    
    // Step 3
    step3Section: document.getElementById('step3Section'),
    savedLeadsSection: document.getElementById('savedLeadsSection'),
    savedLeadsList: document.getElementById('savedLeadsList'),
    totalSaved: document.getElementById('totalSaved'),
    highQualitySaved: document.getElementById('highQualitySaved'),
    notContactedCount: document.getElementById('notContactedCount'),
    backToLeadsBtn: document.getElementById('backToLeadsBtn'),
    totalLeads: document.getElementById('totalLeads'),
    excellentLeads: document.getElementById('excellentLeads'),
    goodLeads: document.getElementById('goodLeads'),
    avgScore: document.getElementById('avgScore'),
    minScoreFilter: document.getElementById('minScoreFilter'),
    newSearchBtn: document.getElementById('newSearchBtn'),
    leadsList: document.getElementById('leadsList'),
    
    // Global
    logoutBtn: document.getElementById('logoutBtn'),
    testConnectionBtn: document.getElementById('testConnectionBtn'),
    loadingOverlay: document.getElementById('loadingOverlay'),
    loadingText: document.getElementById('loadingText'),
    toast: document.getElementById('toast'),
    
    // Modal
    aiResponseModal: document.getElementById('aiResponseModal'),
    aiResponseText: document.getElementById('aiResponseText'),
    closeModal: document.getElementById('closeModal'),
    closeModalBtn: document.getElementById('closeModalBtn'),
    copyResponseBtn: document.getElementById('copyResponseBtn')
};

// ===== UTILITY FUNCTIONS =====
function showLoading(text = 'Processing...') {
    elements.loadingText.textContent = text;
    elements.loadingOverlay.classList.remove('hidden');
}

function hideLoading() {
    elements.loadingOverlay.classList.add('hidden');
}

function showToast(message, type = 'info') {
    elements.toast.textContent = message;
    elements.toast.className = `toast ${type} show`;
    setTimeout(() => elements.toast.classList.remove('show'), 3500);
}

function formatTimestamp(isoString) {
    const date = new Date(isoString);
    const now = new Date();
    const diff = now - date;
    const minutes = Math.floor(diff / 60000);
    const hours = Math.floor(diff / 3600000);
    const days = Math.floor(diff / 86400000);
    
    if (minutes < 1) return 'Just now';
    if (minutes < 60) return `${minutes}m ago`;
    if (hours < 24) return `${hours}h ago`;
    return `${days}d ago`;
}

function getScoreClass(score) {
    if (score >= 80) return 'score-excellent';
    if (score >= 60) return 'score-high';
    return 'score-medium';
}

function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

// ===== SESSION GUARD =====
(function checkAuth() {
    const token = localStorage.getItem('session_token');
    if (!token) { window.location.href = '/login'; return; }
    fetch('/api/auth/check-session', {
        headers: { 'Authorization': `Bearer ${token}` }
    })
    .then(r => r.json())
    .then(data => {
    if (!data.valid) {
        localStorage.removeItem('session_token');
        window.location.href = '/login';
    } else {
        const nameEl = document.getElementById('userName');
        if (nameEl) nameEl.textContent = data.user?.full_name || 'User';
        updateSavedCount();
        loadUserProfile();  // ← NEW: Load profile
    }
})
    .catch(() => console.warn('Session check failed — server may be down.'));
})();

// ===== LOGOUT =====
async function logout() {
    try {
        const token = localStorage.getItem('session_token') || '';
        await fetch('/api/auth/logout', {
            method: 'POST',
            headers: { 'Authorization': `Bearer ${token}` }
        });
    } catch (_) {}
    localStorage.removeItem('session_token');
    localStorage.removeItem('user_name');
    window.location.href = '/login';
}

// ===== API FUNCTIONS =====
async function apiCall(endpoint, options = {}) {
    try {
        const token = localStorage.getItem('session_token') || '';
        const response = await fetch(endpoint, {
            headers: {
                'Content-Type': 'application/json',
                'Authorization': `Bearer ${token}`,
                ...options.headers
            },
            ...options
        });

        if (response.status === 401) {
            localStorage.removeItem('session_token');
            window.location.href = '/login';
            return;
        }

        if (!response.ok) throw new Error(`HTTP ${response.status}`);
        return await response.json();
    } catch (error) {
        console.error('API Error:', error);
        throw error;
    }
}

// ===== STEP 1: DISCOVER SUBREDDITS =====
async function discoverSubreddits() {
    const prompt  = elements.userPromptInput.value.trim();
    const company = elements.companyNameInput?.value.trim() || '';
    const niche   = elements.businessNicheInput?.value.trim() || '';
    
    if (!prompt || prompt.length < 20) {
        showToast('Please provide a detailed description (at least 20 characters)', 'error');
        return;
    }
    
        // Save profile if company/niche provided and not already saved
    if ((company || niche) && (!userProfile.company_name || !userProfile.business_niche)) {
        await apiCall('/api/profile/update', {
            method: 'POST',
            body: JSON.stringify({ company_name: company, business_niche: niche })
        });
        userProfile = { company_name: company, business_niche: niche };
    } 

    userPrompt = prompt;
    
    showLoading('AI is discovering relevant subreddits...');
    
    try {
        const result = await apiCall('/api/discover-subreddits', {
            method: 'POST',
            body: JSON.stringify({ prompt, company, niche })
        });
        
        if (result && result.success) {
            discoveredSubreddits = result.subreddits;
            renderSubreddits();
            goToStep(2);
            showToast(`Found ${discoveredSubreddits.length} relevant subreddits!`, 'success');
        } else {
            showToast(result?.message || 'Discovery failed', 'error');
        }
    } catch (error) {
        showToast('Failed to discover subreddits: ' + error.message, 'error');
    } finally {
        hideLoading();
    }
}

function renderSubreddits() {
    elements.subredditGrid.innerHTML = discoveredSubreddits.map(sub => `
        <div class="subreddit-card" data-name="${escapeHtml(sub.name)}">
            <div class="subreddit-name">r/${escapeHtml(sub.name)}</div>
            <div class="subreddit-meta">
                <span class="relevance-badge">${sub.relevance_score}% Match</span>
                <span>📊 ${escapeHtml(sub.estimated_size)}</span>
            </div>
            <div class="subreddit-reason">${escapeHtml(sub.reason)}</div>
        </div>
    `).join('');
    
    // Add click handlers
    document.querySelectorAll('.subreddit-card').forEach(card => {
        card.addEventListener('click', () => toggleSubreddit(card));
    });
}

function toggleSubreddit(card) {
    const name = card.dataset.name;
    const isSelected = selectedSubreddits.includes(name);
    
    if (isSelected) {
        selectedSubreddits = selectedSubreddits.filter(s => s !== name);
        card.classList.remove('selected');
    } else {
        selectedSubreddits.push(name);
        card.classList.add('selected');
    }
    
    updateSelectionCount();
}

function updateSelectionCount() {
    elements.selectedCount.textContent = selectedSubreddits.length;
    elements.fetchLeadsBtn.disabled = selectedSubreddits.length === 0;
}
// ===== MANUAL SUBREDDIT ENTRY =====
function renderManualSubreddits() {
    elements.manualSubreddits.innerHTML = manualSubreddits.map(sub => `
        <span class="manual-sub-tag">
            r/${sub}
            <button onclick="removeManualSub('${sub}')" class="remove-btn">×</button>
        </span>
    `).join('');
    updateSelectionCount();
}

function removeManualSub(sub) {
    manualSubreddits = manualSubreddits.filter(s => s !== sub);
    renderManualSubreddits();
}

window.removeManualSub = removeManualSub;

// ===== STEP 2: FETCH LEADS =====
async function fetchLeads() {
    const allSubreddits = [...selectedSubreddits, ...manualSubreddits]; // COMBINE BOTH
    
    if (allSubreddits.length === 0) { // CHECK COMBINED
        showToast('Please select at least one subreddit', 'error');
        return;
    }
    
    showLoading(`Fetching posts from ${allSubreddits.length} subreddit(s)...`); // USE COMBINED
    
    showLoading(`Fetching posts from ${selectedSubreddits.length} subreddit(s)...`);
    
    try {
        // Add delay to show loading state
        await new Promise(resolve => setTimeout(resolve, 500));
        
        elements.loadingText.textContent = 'AI is analyzing posts for relevance...';
        
        const company = elements.companyNameInput?.value.trim() || '';
        const niche   = elements.businessNicheInput?.value.trim() || '';

        const result = await apiCall('/api/fetch-leads', {
            method: 'POST',
            body: JSON.stringify({
                subreddits: allSubreddits,
                prompt: userPrompt,
                company,
                niche,
                max_age_days: 30
            })
        });
        
        if (result && result.success) {
            allLeads = result.leads;
            renderLeads();
            updateStats();
            goToStep(3);
            showToast(`Found ${result.total_qualified} qualified leads from ${result.total_fetched} posts!`, 'success');
        } else {
            showToast(result?.message || 'Failed to fetch leads', 'error');
        }
    } catch (error) {
        showToast('Error fetching leads: ' + error.message, 'error');
    } finally {
        hideLoading();
    }
}

function updateStats() {
    const excellent = allLeads.filter(l => l.relevancy_score >= 80).length;
    const good = allLeads.filter(l => l.relevancy_score >= 60 && l.relevancy_score < 80).length;
    const avgScore = allLeads.length > 0 
        ? Math.round(allLeads.reduce((sum, l) => sum + l.relevancy_score, 0) / allLeads.length)
        : 0;
    
    elements.totalLeads.textContent = allLeads.length;
    elements.excellentLeads.textContent = excellent;
    elements.goodLeads.textContent = good;
    elements.avgScore.textContent = avgScore;
}

function renderLeads() {
    const minScore = parseInt(elements.minScoreFilter.value);
    const filtered = allLeads.filter(l => l.relevancy_score >= minScore);
    
    if (filtered.length === 0) {
        elements.leadsList.innerHTML = `
            <div class="empty-state" style="text-align: center; padding: 60px 20px;">
                <div style="font-size: 64px; opacity: 0.3; margin-bottom: 16px;">📊</div>
                <h3>No Leads Found</h3>
                <p>Try lowering the minimum score filter</p>
            </div>
        `;
        return;
    }
    
    elements.leadsList.innerHTML = filtered.map(lead => `
        <div class="lead-card" data-id="${lead.id}">
            <div class="lead-header">
                <div class="lead-title">
                    <h4>${escapeHtml(lead.title)}</h4>
                    <div class="lead-meta">
                        <span>r/${escapeHtml(lead.subreddit)}</span>
                        <span>u/${escapeHtml(lead.author)}</span>
                        <span>↑ ${lead.score}</span>
                        <span>💬 ${lead.num_comments}</span>
                        <span>🕐 ${formatTimestamp(lead.timestamp)}</span>
                    </div>
                </div>
                <div class="score-badge ${getScoreClass(lead.relevancy_score)}">
                    ${lead.relevancy_score}/100
                </div>
            </div>
            
            <div class="content-preview">
                ${escapeHtml(lead.content.substring(0, 250))}${lead.content.length > 250 ? '...' : ''}
            </div>
            
            <div class="lead-analysis">
                <div class="analysis-section">
                    <div class="analysis-label">AI Analysis</div>
                    <div class="analysis-value">${escapeHtml(lead.reasoning)}</div>
                </div>
                
                <div class="analysis-section">
                    <div class="analysis-label">Intent Strength</div>
                    <div class="analysis-value">
                        <span class="intent-badge intent-${lead.intent_strength}">${lead.intent_strength.toUpperCase()}</span>
                    </div>
                </div>
                
                ${lead.key_pain_points && lead.key_pain_points.length > 0 ? `
                <div class="analysis-section">
                    <div class="analysis-label">Key Pain Points</div>
                    <div class="pain-points">
                        ${lead.key_pain_points.map(p => `<span class="pain-point">${escapeHtml(p)}</span>`).join('')}
                    </div>
                </div>
                ` : ''}
            </div>
            
            ${lead.ai_response_generated ? `
            <div class="ai-response-section">
                <div class="ai-response-header">
                    <span>🤖</span>
                    <span>AI-Generated Response</span>
                </div>
                <div class="ai-response-text-content">${escapeHtml(lead.ai_response)}</div>
            </div>  
            ` : ''}
            
            <div class="lead-actions">
            <a href="${lead.url}" target="_blank" class="btn btn-primary btn-sm">
            <span class="icon">🔗</span> View on Reddit
            </a>
            <button onclick="dismissPost('${lead.id}')" class="btn btn-secondary btn-sm">
            <span class="icon">👁‍🗨</span> Mark as Read
            </button>
           ${!lead.is_saved ? `
           <button onclick="saveLead('${lead.id}')" class="btn btn-success btn-sm">
           <span class="icon">💾</span> Save Lead
           </button>
           ` : `
           <button class="btn btn-secondary btn-sm" disabled>
           <span class="icon">✓</span> Saved
           </button>
            `}
                      ${!lead.ai_response_generated ? `
                <button onclick="generateAIResponse('${lead.id}')" class="btn btn-success btn-sm">
                    <span class="icon">🤖</span> Generate AI Response
                </button>
                ` : `
                <button onclick="showResponseModal('${lead.id}')" class="btn btn-secondary btn-sm">
                    <span class="icon">👁</span> View Full Response
                </button>
                <button onclick="copyResponse('${lead.id}')" class="btn btn-secondary btn-sm">
                    <span class="icon">📋</span> Copy Response
                </button>
                `}
            </div>
        </div>
    `).join('');
}
// ===== SAVE LEAD TO DATABASE =====
async function saveLead(postId) {
    showLoading('Saving lead to database...');
    
    try {
        // Always send full lead data so the server can reconstruct state
        // after a restart — eliminates the 404 "Post not found" glitch
        const lead = allLeads.find(l => l.id === postId);
        const result = await apiCall('/api/save-lead', {
            method: 'POST',
            body: JSON.stringify({ post_id: postId, post_data: lead || null })
        });
        
        if (result.success) {
            const lead = allLeads.find(l => l.id === postId);
            if (lead) lead.is_saved = true;
            renderLeads();
            showToast('Lead saved successfully!', 'success');
            updateSavedCount();
        } else {
            showToast(result.message || 'Failed to save', 'warning');
        }
    } catch (error) {
        showToast('Error saving lead', 'error');
    } finally {
        hideLoading();
    }
}

async function updateSavedCount() {
    try {
        const result = await apiCall('/api/saved-leads?limit=1');
        if (result.success && elements.savedCount) {
            const stats = await apiCall('/api/saved-leads-stats');
            elements.savedCount.textContent = stats.stats?.total_saved || 0;
        }
    } catch (error) {
        console.error('Failed to update count');
    }
}

window.saveLead = saveLead;

// ===== AI RESPONSE GENERATION =====
async function generateAIResponse(postId) {
    showLoading('AI is crafting a personalized response...');
    
    try {
        // Always send full lead data and user context so the server can
        // reconstruct state after a restart — eliminates the 404 glitch
        const lead = allLeads.find(l => l.id === postId);
        const result = await apiCall('/api/generate-response', {
            method: 'POST',
            body: JSON.stringify({
                post_id: postId,
                post_data: lead || null,
                user_context: userPrompt
            })
        });
        
        if (result.success) {
            // Update the lead in our local array
            const lead = allLeads.find(l => l.id === postId);
            if (lead) {
                lead.ai_response_generated = true;
                lead.ai_response = result.ai_response;
            }
            
            // Re-render leads to show the response
            
            renderLeads();
            
            showToast('AI response generated successfully!', 'success');
        } else {
            showToast(result.message || 'Failed to generate response', 'error');
        }
    } catch (error) {
        showToast('Error generating response: ' + error.message, 'error');
    } finally {
        hideLoading();
    }
}

function showResponseModal(postId) {
    const lead = allLeads.find(l => l.id === postId);
    if (!lead || !lead.ai_response) return;
    
    currentAIResponse = lead.ai_response;
    elements.aiResponseText.textContent = lead.ai_response;
    elements.aiResponseModal.classList.remove('hidden');
}

function copyResponse(postId) {
    const lead = allLeads.find(l => l.id === postId);
    if (!lead || !lead.ai_response) return;
    
    navigator.clipboard.writeText(lead.ai_response).then(() => {
        showToast('Response copied to clipboard!', 'success');
    }).catch(() => {
        showToast('Failed to copy response', 'error');
    });
}

// ===== VIEW SAVED LEADS =====
async function viewSavedLeads() {
    showLoading('Loading saved leads...');
    
    try {
        const result = await apiCall('/api/saved-leads?limit=200');
        
        if (result.success) {
            renderSavedLeads(result.leads);
            updateSavedStats(result.leads);
            goToSavedSection();
            showToast('Loaded saved leads', 'success');
        }
    } catch (error) {
        showToast('Failed to load saved leads', 'error');
    } finally {
        hideLoading();
    }
}

function renderSavedLeads(leads) {
    if (leads.length === 0) {
        elements.savedLeadsList.innerHTML = `
            <div class="empty-state" style="text-align: center; padding: 60px 20px;">
                <div style="font-size: 64px; opacity: 0.3; margin-bottom: 16px;">💾</div>
                <h3>No Saved Leads Yet</h3>
                <p>Save leads from your search results to view them here</p>
            </div>
        `;
        return;
    }
    
    elements.savedLeadsList.innerHTML = leads.map(lead => `
        <div class="lead-card">
            <div class="lead-header">
                <div class="lead-title">
                    <h4>${escapeHtml(lead.title)}</h4>
                    <div class="lead-meta">
                        <span>r/${escapeHtml(lead.subreddit)}</span>
                        <span>u/${escapeHtml(lead.author)}</span>
                        <span>↑ ${lead.score}</span>
                        <span>💬 ${lead.num_comments}</span>
                        <span>💾 Saved ${formatTimestamp(lead.saved_at)}</span>
                    </div>
                </div>
                <div class="score-badge ${getScoreClass(lead.relevancy_score)}">
                    ${lead.relevancy_score}/100
                </div>
            </div>
            
            <div class="content-preview">
                ${escapeHtml(lead.content.substring(0, 250))}${lead.content.length > 250 ? '...' : ''}
            </div>
            
            <div class="lead-analysis">
                <div class="analysis-section">
                    <div class="analysis-label">AI Analysis</div>
                    <div class="analysis-value">${escapeHtml(lead.reasoning)}</div>
                </div>
            </div>
            
            ${lead.ai_response ? `
            <div class="ai-response-section">
                <div class="ai-response-header">
                    <span>🤖</span>
                    <span>AI-Generated Response</span>
                </div>
                <div class="ai-response-text-content">${escapeHtml(lead.ai_response)}</div>
            </div>
            ` : ''}
            
            <div class="lead-actions">
                <a href="${lead.url}" target="_blank" class="btn btn-primary btn-sm">
                    <span class="icon">🔗</span> View on Reddit
                </a>
                ${lead.ai_response ? `
                <button onclick="copyText('${escapeHtml(lead.ai_response).replace(/'/g, "\\'")}', 'Response copied!')" class="btn btn-secondary btn-sm">
                    <span class="icon">📋</span> Copy Response
                </button>
                ` : ''}
                <button onclick="deleteSavedLead('${lead.reddit_post_id}')" class="btn btn-danger btn-sm">
                    <span class="icon">🗑</span> Delete
                </button>
            </div>
        </div>
    `).join('');
}

function updateSavedStats(leads) {
    const total = leads.length;
    const highQuality = leads.filter(l => l.relevancy_score >= 70).length;
    const notContacted = leads.filter(l => !l.is_contacted).length;
    
    elements.totalSaved.textContent = total;
    elements.highQualitySaved.textContent = highQuality;
    elements.notContactedCount.textContent = notContacted;
}

function goToSavedSection() {
    elements.step1Section.classList.add('hidden');
    elements.step2Section.classList.add('hidden');
    elements.step3Section.classList.add('hidden');
    elements.savedLeadsSection.classList.remove('hidden');
    window.scrollTo({ top: 0, behavior: 'smooth' });
}

async function deleteSavedLead(postId) {
    if (!confirm('Delete this saved lead?')) return;
    
    showLoading('Deleting...');
    
    try {
        const result = await apiCall('/api/delete-lead', {
            method: 'POST',
            body: JSON.stringify({ post_id: postId })
        });
        
        if (result.success) {
            showToast('Lead deleted', 'success');
            await viewSavedLeads(); // Refresh
            await updateSavedCount();
        }
    } catch (error) {
        showToast('Failed to delete', 'error');
    } finally {
        hideLoading();
    }
}

function copyText(text, message) {
    navigator.clipboard.writeText(text).then(() => {
        showToast(message, 'success');
    });
}

window.deleteSavedLead = deleteSavedLead;
window.copyText = copyText;


// ===== NAVIGATION =====
function goToStep(step) {
    currentStep = step;
    
    elements.step1Section.classList.toggle('hidden', step !== 1);
    elements.step2Section.classList.toggle('hidden', step !== 2);
    elements.step3Section.classList.toggle('hidden', step !== 3);
    
    window.scrollTo({ top: 0, behavior: 'smooth' });
}

function resetToStart() {
    userPrompt = '';
    discoveredSubreddits = [];
    selectedSubreddits = [];
    allLeads = [];
    elements.userPromptInput.value = '';
    if (elements.companyNameInput)   elements.companyNameInput.value   = '';
    if (elements.businessNicheInput) elements.businessNicheInput.value = '';
    goToStep(1);
}

// ===== API CONNECTION TEST =====
async function testConnection() {
    showLoading('Testing API connections...');
    
    try {
        const result = await apiCall('/api/test-connection');
        
        let message = 'Connection Test:\n\n';
        message += result.reddit ? '✓ Reddit API: Connected\n' : '✗ Reddit API: Failed\n';
        message += result.groq ? '✓ Groq AI: Connected' : '✗ Groq AI: Failed';
        
        if (result.errors && result.errors.length > 0) {
            message += '\n\nErrors:\n' + result.errors.join('\n');
            showToast('Connection issues detected', 'warning');
        } else {
            showToast('All APIs connected!', 'success');
        }
        
        alert(message);
    } catch (error) {
        showToast('Connection test failed', 'error');
    } finally {
        hideLoading();
    }
}

// ===== DISMISS POST =====
async function dismissPost(postId) {
    if (!confirm('Mark this post as read? You won\'t see it again.')) return;
    
    showLoading('Dismissing post...');
    
    try {
        // Dismiss only needs post_id — no post_data required
        const result = await apiCall('/api/dismiss-post', {
            method: 'POST',
            body: JSON.stringify({ post_id: postId })
        });
        
        if (result.success) {
            // Remove from UI
            allLeads = allLeads.filter(l => l.id !== postId);
            renderLeads();
            updateStats();
            showToast('Post dismissed for 30 days', 'success');
        } else {
            showToast(result.message || 'Failed to dismiss', 'error');
        }
    } catch (error) {
        showToast('Error dismissing post', 'error');
    } finally {
        hideLoading();
    }
}

// ===== USER PROFILE =====
async function loadUserProfile() {
    try {
        const result = await apiCall('/api/profile/get');
        if (result.success) {
            userProfile = result.profile;
            
            // Auto-fill company/niche if they exist
            if (userProfile.company_name) {
                elements.companyNameInput.value = userProfile.company_name;
                elements.companyNameInput.disabled = true;
            }
            if (userProfile.business_niche) {
                elements.businessNicheInput.value = userProfile.business_niche;
                elements.businessNicheInput.disabled = true;
            }
        }
    } catch (error) {
        console.error('Failed to load profile');
    }
}

async function saveProfile() {
    const companyName = document.getElementById('profileCompanyName').value.trim();
    const businessNiche = document.getElementById('profileBusinessNiche').value.trim();
    
    showLoading('Saving profile...');
    
    try {
        const result = await apiCall('/api/profile/update', {
            method: 'POST',
            body: JSON.stringify({
                company_name: companyName,
                business_niche: businessNiche
            })
        });
        
        if (result.success) {
            userProfile = { company_name: companyName, business_niche: businessNiche };
            
            // Update main form
            elements.companyNameInput.value = companyName;
            elements.businessNicheInput.value = businessNiche;
            elements.companyNameInput.disabled = !!companyName;
            elements.businessNicheInput.disabled = !!businessNiche;
            
            document.getElementById('profileModal').classList.add('hidden');
            showToast('Profile updated!', 'success');
        } else {
            showToast(result.message, 'error');
        }
    } catch (error) {
        showToast('Failed to save profile', 'error');
    } finally {
        hideLoading();
    }
}

function openProfileModal() {
    document.getElementById('profileCompanyName').value = userProfile.company_name || '';
    document.getElementById('profileBusinessNiche').value = userProfile.business_niche || '';
    document.getElementById('profileModal').classList.remove('hidden');
}

// Event listeners for profile modal
// Event listeners for profile modal
const userNameBtn = document.getElementById('userNameBtn');
if (userNameBtn) {
    userNameBtn.addEventListener('click', openProfileModal);
}

const closeProfileModal = document.getElementById('closeProfileModal');
if (closeProfileModal) {
    closeProfileModal.addEventListener('click', () => {
        document.getElementById('profileModal').classList.add('hidden');
    });
}

const closeProfileModalBtn = document.getElementById('closeProfileModalBtn');
if (closeProfileModalBtn) {
    closeProfileModalBtn.addEventListener('click', () => {
        document.getElementById('profileModal').classList.add('hidden');
    });
}

const saveProfileBtn = document.getElementById('saveProfileBtn');
if (saveProfileBtn) {
    saveProfileBtn.addEventListener('click', saveProfile);
}

const profileModal = document.getElementById('profileModal');
if (profileModal) {
    profileModal.addEventListener('click', (e) => {
        if (e.target.id === 'profileModal') {
            profileModal.classList.add('hidden');
        }
    });
}


// ===== EVENT LISTENERS =====

// Step 1
elements.discoverBtn.addEventListener('click', discoverSubreddits);
elements.userPromptInput.addEventListener('keydown', (e) => {
    if (e.key === 'Enter' && e.ctrlKey) {
        discoverSubreddits();
    }
});

// Step 2
elements.backToStep1.addEventListener('click', () => goToStep(1));
elements.fetchLeadsBtn.addEventListener('click', fetchLeads);

// Step 3
elements.minScoreFilter.addEventListener('change', renderLeads);
elements.newSearchBtn.addEventListener('click', resetToStart);

// Modal
elements.closeModal.addEventListener('click', () => {
    elements.aiResponseModal.classList.add('hidden');
});
elements.closeModalBtn.addEventListener('click', () => {
    elements.aiResponseModal.classList.add('hidden');
});
elements.copyResponseBtn.addEventListener('click', () => {
    if (currentAIResponse) {
        navigator.clipboard.writeText(currentAIResponse).then(() => {
            showToast('Response copied!', 'success');
        });
    }
});

// Close modal on background click
elements.aiResponseModal.addEventListener('click', (e) => {
    if (e.target === elements.aiResponseModal) {
        elements.aiResponseModal.classList.add('hidden');
    }
});


// Global
elements.testConnectionBtn.addEventListener('click', testConnection);

const logoutBtn = document.getElementById('logoutBtn');
if (logoutBtn) logoutBtn.addEventListener('click', logout);

// Manual subreddit entry
elements.addManualBtn.addEventListener('click', () => {
    const input = elements.manualSubredditInput;
    const sub = input.value.trim().toLowerCase().replace(/^r\//, '');
    
    if (sub && !manualSubreddits.includes(sub) && !selectedSubreddits.includes(sub)) {
        manualSubreddits.push(sub);
        renderManualSubreddits();
        input.value = '';
        showToast(`Added r/${sub}`, 'success');
    } else if (manualSubreddits.includes(sub) || selectedSubreddits.includes(sub)) {
        showToast('Subreddit already added', 'warning');
    }
});

elements.manualSubredditInput.addEventListener('keypress', (e) => {
    if (e.key === 'Enter') {
        elements.addManualBtn.click();
    }
});

// View Saved Leads
elements.viewSavedBtn.addEventListener('click', viewSavedLeads);

// Back to discovered leads
elements.backToLeadsBtn.addEventListener('click', () => goToStep(3));
// Expose functions globally for onclick handlers
window.generateAIResponse = generateAIResponse;
window.showResponseModal = showResponseModal;
window.copyResponse = copyResponse;
window.dismissPost = dismissPost;

// ===== INITIALIZATION =====
console.log('🚀 AI Lead Discovery Platform initialized');

console.log('📝 Enter your product/service description to begin');
