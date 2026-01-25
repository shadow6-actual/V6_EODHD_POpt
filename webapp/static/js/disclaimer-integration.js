/*
 * FOLIOFORECAST DISCLAIMER INTEGRATION
 * =====================================
 * 
 * This file contains everything you need to add disclaimers to your site:
 * 1. CSS styles (add to your stylesheet or <style> block)
 * 2. HTML snippets for landing page footer
 * 3. HTML snippets for app page
 * 4. JavaScript for first-visit disclaimer modal
 *
 * INTEGRATION INSTRUCTIONS AT BOTTOM OF FILE
 */

/* ==========================================================================
   SECTION 1: CSS STYLES
   Add these to your main stylesheet or in a <style> block
   ========================================================================== */

/* Disclaimer Banner - Full Width */
.disclaimer-banner {
    background: linear-gradient(135deg, rgba(245, 158, 11, 0.1), rgba(239, 68, 68, 0.08));
    border: 1px solid rgba(245, 158, 11, 0.3);
    border-radius: 8px;
    padding: 12px 20px;
    margin: 15px 0;
    display: flex;
    align-items: center;
    gap: 12px;
    font-size: 0.85rem;
}

.disclaimer-banner i {
    color: #f59e0b;
    font-size: 1.1rem;
    flex-shrink: 0;
}

.disclaimer-banner p {
    margin: 0;
    color: #a0a0b0;
    line-height: 1.5;
}

.disclaimer-banner a {
    color: #3b82f6;
    text-decoration: none;
}

.disclaimer-banner a:hover {
    text-decoration: underline;
}

/* Compact version for footer */
.disclaimer-banner.compact {
    padding: 10px 15px;
    font-size: 0.8rem;
    background: rgba(245, 158, 11, 0.05);
    border: none;
    border-top: 1px solid rgba(255,255,255,0.1);
    border-radius: 0;
    margin: 0;
}

/* Footer legal links */
.footer-legal {
    padding: 30px 20px;
    text-align: center;
    border-top: 1px solid rgba(255,255,255,0.1);
    background: #0a0a0f;
}

.footer-legal-links {
    display: flex;
    justify-content: center;
    gap: 20px;
    flex-wrap: wrap;
    margin-bottom: 15px;
}

.footer-legal-links a {
    color: #a0a0b0;
    text-decoration: none;
    font-size: 0.85rem;
    transition: color 0.2s;
}

.footer-legal-links a:hover {
    color: #3b82f6;
}

.footer-disclaimer {
    color: #6b7280;
    font-size: 0.75rem;
    max-width: 800px;
    margin: 0 auto;
    line-height: 1.6;
}

.footer-copyright {
    color: #6b7280;
    font-size: 0.8rem;
    margin-top: 15px;
}

/* App page disclaimer (above results) */
.app-disclaimer {
    background: rgba(245, 158, 11, 0.08);
    border-left: 3px solid #f59e0b;
    padding: 10px 15px;
    margin: 15px 0;
    font-size: 0.8rem;
    color: #9ca3af;
    border-radius: 0 6px 6px 0;
}

.app-disclaimer a {
    color: #3b82f6;
}

/* First-visit modal styling */
.disclaimer-modal .modal-content {
    background: #12121a;
    border: 1px solid #2a2a3a;
}

.disclaimer-modal .modal-header {
    border-bottom: 1px solid #2a2a3a;
}

.disclaimer-modal .modal-footer {
    border-top: 1px solid #2a2a3a;
}

.disclaimer-modal .warning-icon {
    font-size: 3rem;
    color: #f59e0b;
    margin-bottom: 15px;
}

.disclaimer-modal ul {
    text-align: left;
    color: #9ca3af;
}

.disclaimer-modal ul li {
    margin-bottom: 8px;
}


/* ==========================================================================
   SECTION 2: LANDING PAGE FOOTER HTML
   Add this before the closing </body> tag on your landing page
   ========================================================================== */

/*
<!-- LANDING PAGE FOOTER - Add before </body> -->

<footer class="footer-legal">
    <div class="footer-legal-links">
        <a href="/terms">Terms of Service</a>
        <a href="/privacy">Privacy Policy</a>
        <a href="/disclaimer">Investment Disclaimer</a>
        <a href="/pricing">Pricing</a>
    </div>
    <p class="footer-disclaimer">
        <strong>Disclaimer:</strong> FolioForecast is for educational and informational purposes only. 
        It is not investment advice. Past performance does not guarantee future results. 
        All investments involve risk, including loss of principal. Consult a qualified financial advisor before making investment decisions.
    </p>
    <p class="footer-copyright">
        &copy; 2026 FolioForecast. All rights reserved.
    </p>
</footer>
*/


/* ==========================================================================
   SECTION 3: APP PAGE HTML SNIPPETS
   ========================================================================== */

/*
<!-- APP PAGE: Add this disclaimer banner ABOVE the optimization results section -->
<!-- Place it after the "Run Optimization" button area, before results display -->

<div class="app-disclaimer">
    <i class="fas fa-info-circle me-2"></i>
    <strong>Not investment advice.</strong> Results are hypothetical and based on historical data. 
    Past performance ≠ future results. 
    <a href="/disclaimer" target="_blank">Full disclaimer</a>
</div>


<!-- APP PAGE: Add this to the footer area of the app -->

<div class="disclaimer-banner compact mt-4">
    <i class="fas fa-exclamation-triangle"></i>
    <p>
        FolioForecast is for educational purposes only and does not constitute investment advice. 
        <a href="/terms">Terms</a> · <a href="/privacy">Privacy</a> · <a href="/disclaimer">Disclaimer</a>
    </p>
</div>
*/


/* ==========================================================================
   SECTION 4: FIRST-VISIT DISCLAIMER MODAL HTML
   Add this anywhere in the body of your app page (index.html)
   ========================================================================== */

/*
<!-- FIRST-VISIT DISCLAIMER MODAL -->
<div class="modal fade disclaimer-modal" id="disclaimerModal" tabindex="-1" data-bs-backdrop="static" data-bs-keyboard="false">
    <div class="modal-dialog modal-dialog-centered">
        <div class="modal-content">
            <div class="modal-header">
                <h5 class="modal-title text-warning">
                    <i class="fas fa-exclamation-triangle me-2"></i>
                    Important Disclaimer
                </h5>
            </div>
            <div class="modal-body text-center">
                <div class="warning-icon">
                    <i class="fas fa-chart-line"></i>
                </div>
                <h5 class="mb-3">Welcome to FolioForecast</h5>
                <p class="text-secondary">Before you begin, please understand:</p>
                <ul class="text-start">
                    <li><strong>Educational Tool Only:</strong> This is not investment advice</li>
                    <li><strong>No Guarantees:</strong> Past performance does not predict future results</li>
                    <li><strong>Risk of Loss:</strong> All investments can lose value</li>
                    <li><strong>Do Your Research:</strong> Consult a financial advisor before investing</li>
                    <li><strong>Your Responsibility:</strong> You are solely responsible for your investment decisions</li>
                </ul>
                <p class="small text-muted mt-3">
                    By clicking "I Understand", you agree to our 
                    <a href="/terms" target="_blank">Terms of Service</a> and acknowledge our 
                    <a href="/disclaimer" target="_blank">Investment Disclaimer</a>.
                </p>
            </div>
            <div class="modal-footer justify-content-center">
                <button type="button" class="btn btn-warning btn-lg" id="acceptDisclaimerBtn">
                    <i class="fas fa-check me-2"></i>I Understand
                </button>
            </div>
        </div>
    </div>
</div>
*/


/* ==========================================================================
   SECTION 5: JAVASCRIPT
   Add this to your main.js or in a <script> block before </body>
   ========================================================================== */

/*
// ============================================
// DISCLAIMER MODAL - FIRST VISIT
// ============================================

// Check and show disclaimer on first visit
function initDisclaimerModal() {
    const disclaimerAcknowledged = localStorage.getItem('folioforecast_disclaimer_acknowledged');
    
    if (!disclaimerAcknowledged) {
        // Show modal after a brief delay to let page load
        setTimeout(() => {
            const modal = new bootstrap.Modal(document.getElementById('disclaimerModal'));
            modal.show();
        }, 500);
    }
}

// Handle disclaimer acceptance
document.addEventListener('DOMContentLoaded', function() {
    const acceptBtn = document.getElementById('acceptDisclaimerBtn');
    if (acceptBtn) {
        acceptBtn.addEventListener('click', function() {
            localStorage.setItem('folioforecast_disclaimer_acknowledged', 'true');
            localStorage.setItem('folioforecast_disclaimer_date', new Date().toISOString());
            
            const modal = bootstrap.Modal.getInstance(document.getElementById('disclaimerModal'));
            modal.hide();
        });
    }
    
    // Initialize disclaimer check
    initDisclaimerModal();
});

// Optional: Re-show disclaimer after 30 days
function checkDisclaimerExpiry() {
    const acknowledgedDate = localStorage.getItem('folioforecast_disclaimer_date');
    if (acknowledgedDate) {
        const daysSinceAck = (new Date() - new Date(acknowledgedDate)) / (1000 * 60 * 60 * 24);
        if (daysSinceAck > 30) {
            localStorage.removeItem('folioforecast_disclaimer_acknowledged');
            localStorage.removeItem('folioforecast_disclaimer_date');
        }
    }
}
// Uncomment to enable 30-day re-acknowledgment:
// checkDisclaimerExpiry();
*/


/* ==========================================================================
   INTEGRATION INSTRUCTIONS
   ========================================================================== */

/*
STEP-BY-STEP INTEGRATION:

1. ADD CSS
   - Copy Section 1 (CSS Styles) into your main stylesheet
   - Or add it in a <style> block in your HTML <head>

2. LANDING PAGE (landing.html or home page)
   - Add the footer HTML from Section 2 before </body>
   - This adds Terms/Privacy/Disclaimer links + short disclaimer text

3. APP PAGE (index.html)
   - Add the app-disclaimer div from Section 3 above your results area
   - Add the compact footer disclaimer from Section 3 at bottom of app
   - Add the modal HTML from Section 4 anywhere in <body>

4. JAVASCRIPT
   - Add the JavaScript from Section 5 to your main.js file
   - Or add it in a <script> block before </body>
   - This shows a modal on first visit requiring acknowledgment

5. TEST
   - Clear localStorage or use incognito to test first-visit modal
   - Verify all links work: /terms, /privacy, /disclaimer
   - Check that modal doesn't show again after clicking "I Understand"

CUSTOMIZATION OPTIONS:
- Remove the 30-day re-acknowledgment by leaving checkDisclaimerExpiry() commented out
- Change modal backdrop by removing data-bs-backdrop="static" (allows clicking outside to close)
- Adjust colors by modifying the CSS variables
*/
