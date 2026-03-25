function App() {
  return (
    <div style={{
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'center',
      height: '100vh',
      background: 'linear-gradient(135deg, #0f0c29 0%, #1a1a2e 50%, #16213e 100%)',
      color: '#e0e0e0',
      fontFamily: "'Inter', sans-serif",
    }}>
      <div style={{
        textAlign: 'center',
        padding: '3rem',
        background: 'rgba(255,255,255,0.05)',
        borderRadius: '1.5rem',
        border: '1px solid rgba(255,255,255,0.1)',
        backdropFilter: 'blur(20px)',
      }}>
        <h1 style={{ fontSize: '2.5rem', fontWeight: 700, marginBottom: '0.5rem' }}>
          ⚡ Dodge AI
        </h1>
        <p style={{ fontSize: '1.1rem', opacity: 0.7 }}>
          Order-to-Cash Intelligence · Graph + GenAI
        </p>
        <p style={{ fontSize: '0.9rem', opacity: 0.5, marginTop: '1rem' }}>
          Backend API: <a href="/health" style={{ color: '#60a5fa' }}>/health</a>
        </p>
      </div>
    </div>
  )
}

export default App
