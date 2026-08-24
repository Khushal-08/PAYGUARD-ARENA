import React, { useState, useEffect } from 'react';
import { demoData, mockTransactions } from './mockData';

// --- Components ---

const DefenseModelStats = ({ data }) => {
  return (
    <div className="glass-card flex-col animate-slide-in">
      <h3 className="mb-4 text-gradient-primary font-bold">XGBClassifier (Defense Model)</h3>
      <div className="dashboard-grid">
        <div className="glass-panel">
          <div className="text-muted text-sm mb-2">Baseline FPR</div>
          <div className="font-bold" style={{ fontSize: '1.5rem' }}>{(data.round_0_model_fpr * 100).toFixed(2)}%</div>
          <div className="text-muted text-sm mt-2">{data.round_0_model_fp_count} false positives</div>
        </div>
        <div className="glass-panel">
          <div className="text-muted text-sm mb-2">Round 1 Detection Rate</div>
          <div className="font-bold text-gradient-primary" style={{ fontSize: '1.5rem' }}>{(data.round_1_detection_rate * 100).toFixed(1)}%</div>
          <div className="text-muted text-sm mt-2">{data.round_1_caught} / {data.round_1_total} caught</div>
        </div>
        <div className="glass-panel">
          <div className="text-muted text-sm mb-2">Round 2 Detection Rate</div>
          <div className="font-bold text-gradient-accent" style={{ fontSize: '1.5rem' }}>{(data.round_2_detection_rate * 100).toFixed(1)}%</div>
          <div className="text-muted text-sm mt-2">{data.round_2_caught} / {data.round_2_total} caught</div>
        </div>
      </div>
    </div>
  );
};

const SHAPAnalysisWidget = ({ data }) => {
  const maxScore = data.shap_explanation[0][1];
  return (
    <div className="glass-card animate-slide-in" style={{ animationDelay: '0.1s' }}>
      <h3 className="mb-4 font-bold">Feature Importance (SHAP)</h3>
      <div className="flex-col gap-4">
        {data.shap_explanation.map(([feature, score], idx) => (
          <div key={feature} className="flex-col gap-2">
            <div className="flex justify-between text-sm">
              <span style={{ fontFamily: 'monospace' }}>{feature}</span>
              <span className="text-primary font-bold">{score.toFixed(2)}</span>
            </div>
            <div style={{ width: '100%', height: '6px', background: 'rgba(255,255,255,0.1)', borderRadius: '3px', overflow: 'hidden' }}>
              <div style={{ 
                width: `${(score / maxScore) * 100}%`, 
                height: '100%', 
                background: idx === 0 ? 'var(--primary)' : 'var(--text-muted)' 
              }} />
            </div>
          </div>
        ))}
      </div>
      <div className="mt-4 p-4 glass-panel text-sm text-muted" style={{ borderLeft: '3px solid var(--accent)' }}>
        <strong>LLM Strategy:</strong> {data.llm_reasoning}
      </div>
    </div>
  );
};

const AttackFeed = ({ transactions }) => {
  return (
    <div className="glass-card flex-col animate-slide-in" style={{ animationDelay: '0.2s', height: '100%' }}>
      <div className="flex justify-between items-center mb-4">
        <h3 className="font-bold">Live Simulation Feed</h3>
        <div className="pulse-indicator" style={{ width: 8, height: 8, background: 'var(--accent)', borderRadius: '50%', animation: 'pulseGlow 2s infinite' }}></div>
      </div>
      <div className="flex-col gap-2" style={{ overflowY: 'auto', flex: 1, maxHeight: '500px' }}>
        {transactions.map(tx => (
          <div key={tx.id} className="glass-panel flex justify-between items-center" style={{ padding: '12px 16px' }}>
            <div className="flex-col gap-2">
              <div className="flex items-center gap-4">
                <span className="font-bold text-sm">{tx.time}</span>
                <span className="text-sm" style={{ color: tx.attackType === 'Legitimate' ? 'var(--text-muted)' : 'var(--accent)' }}>{tx.attackType}</span>
              </div>
              <div style={{ fontFamily: 'monospace', fontSize: '1.1rem' }}>${tx.amount.toFixed(2)}</div>
              {tx.reason && <div className="text-muted text-sm mt-1">{tx.reason}</div>}
            </div>
            {tx.status && (
              <div className={`status-badge ${tx.status === 'caught' ? 'status-caught' : 'status-missed'}`}>
                {tx.status}
              </div>
            )}
          </div>
        ))}
      </div>
    </div>
  );
};

// --- Layouts & Pages ---

const ArenaView = () => {
  return (
    <div className="flex-col gap-4">
      <header>
        <div>
          <h1 className="text-gradient-primary">PAYGUARD-ARENA</h1>
          <p className="text-muted mt-2">Active Simulation: Round 3 (Adaptive Evasion)</p>
        </div>
      </header>
      
      <DefenseModelStats data={demoData} />
      
      <div className="arena-grid mt-4">
        <AttackFeed transactions={mockTransactions} />
        <SHAPAnalysisWidget data={demoData} />
      </div>
    </div>
  );
};

const App = () => {
  return (
    <div className="app-container">
      <nav className="sidebar">
        <h2 className="font-bold" style={{ fontSize: '1.2rem', letterSpacing: '2px' }}>PG::ARENA</h2>
        <div className="flex-col gap-4 mt-4 text-sm">
          <div className="text-primary font-bold cursor-pointer hover:opacity-80">⚔️ Battle View</div>
          <div className="text-muted cursor-pointer hover:text-main transition-colors">📊 Model Metrics</div>
          <div className="text-muted cursor-pointer hover:text-main transition-colors">🤖 GenAI Agents</div>
          <div className="text-muted cursor-pointer hover:text-main transition-colors">⚙️ Settings</div>
        </div>
      </nav>
      <main className="main-content">
        <ArenaView />
      </main>
    </div>
  );
};

export default App;
