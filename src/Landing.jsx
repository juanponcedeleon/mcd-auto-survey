function Landing() {
    const lightningIcon = <svg xmlns="http://www.w3.org/2000/svg" width="32" height="32" viewBox="0 0 24 24"><path fill="none" stroke="var(--bg-primary)" strokeLinejoin="round" strokeWidth="1.5" d="M11 14H6L9.5 2H16l-3 8h5l-8 12z"/></svg>
    const checkIcon = <svg xmlns="http://www.w3.org/2000/svg" width="32" height="32" viewBox="0 0 24 24"><path fill="none" stroke="var(--bg-primary)" strokeLinecap="round" strokeLinejoin="round" strokeWidth="2.5" d="M20 7L10 17l-5-5"/></svg>
    const moneyIcon = <svg xmlns="http://www.w3.org/2000/svg" width="32" height="32" viewBox="0 0 24 24"><path fill="var(--bg-primary)" d="M12 16q-.825 0-1.412-.587T10 14t.588-1.412T12 12t1.413.588T14 14t-.587 1.413T12 16M7.375 7h9.25l2-4H5.375zM8.4 21h7.2q2.25 0 3.825-1.562T21 15.6q0-.95-.325-1.85t-.925-1.625L17.15 9H6.85l-2.6 3.125q-.6.725-.925 1.625T3 15.6q0 2.275 1.563 3.838T8.4 21"/></svg>

    return <>
        <div className="landing-container">
        <header className="landing-header">
            {/* <div className="logo">SurveyFlow</div> */}
        </header>

        <main className="hero-section">
            <h1 className="hero-title">
            Automate McDonald's Customer Surveys
            </h1>
            
            <p className="hero-subtitle">
            Stop wasting time manually entering survey codes and responses
            </p>
            
            <p className="hero-description">
            Our platform eliminates the tedious process of manually filling out customer satisfaction surveys. 
            Simply enter your survey code and let our automation handle the rest – saving your team hours of repetitive work every week.
            </p>

            <div className="cta-section">
            <a href="/login" className="login-button">
                {/* <span>🏪</span> */}
                Login to your Store
            </a>
            </div>

            <div className="benefits-grid">
            <div className="benefit-card">
                <div className="benefit-icon">{lightningIcon}</div>
                <h3 className="benefit-title">Lightning Fast</h3>
                <p className="benefit-description">
                Complete surveys automatically in seconds. No more tedious manual data entry.
                </p>
            </div>

            <div className="benefit-card">
                <div className="benefit-icon">{checkIcon}</div>
                <h3 className="benefit-title">100% Accurate</h3>
                <p className="benefit-description">
                Eliminate human errors with automated form filling that works perfectly every time.
                </p>
            </div>

            <div className="benefit-card">
                <div className="benefit-icon">{moneyIcon}</div>
                <h3 className="benefit-title">Save Time & Money</h3>
                <p className="benefit-description">
                Free up your time for more important tasks, while our survey bots boost your store's reviews.
                </p>
            </div>
            </div>
        </main>

        <footer className="landing-footer">
            {/* &copy; 2025 SurveyFlow.  */}
            <p><a className="underline-link" href="https://github.com/JMasterBoi" target="_blank">Beep boop</a> | Streamlining McDonald's operations one survey at a time.</p>
        </footer>
        </div>
    </>
  
}

export default Landing