import { useMemo, useState, useEffect } from 'react';
import { demoData, mockTransactions } from './mockData';

const createRounds = (data) => [
  { id: 1, label: 'ATTACK LAUNCH', title: 'Baseline attack enters the arena', detail: 'Synthetic fraud campaign deployed against the defense model.', rate: data.round_1_detection_rate, caught: data.round_1_caught, total: data.round_1_total, amount: data.round_1_avg_amt, tone: 'cyan' },
  { id: 2, label: 'ADAPTIVE EVASION', title: 'Attacker learns from the signal', detail: 'Campaign mutates its timing, velocity, and spend profile.', rate: data.round_2_detection_rate, caught: data.round_2_caught, total: data.round_2_total, amount: data.round_2_avg_amt, tone: 'alert' },
  { id: 3, label: 'DEFENSE RETRAIN', title: 'Model closes the escape route', detail: 'Retrained classifier restores detection against the evolved campaign.', rate: data.round_3_detection_rate, caught: data.round_3_caught, total: data.round_3_total, amount: data.round_3_avg_amt, tone: 'green' },
];

function Metric({ label, value, sub, tone = '' }) {
  return <div className="metric"><span className="eyebrow">{label}</span><strong className={tone}>{value}</strong><span className="muted mono">{sub}</span></div>;
}

function RoundTimeline({ selected, setSelected, rounds }) {
  return <section className="timeline panel-gridline" aria-label="Adversarial cycle rounds">
    <div className="section-head"><div><span className="eyebrow">OPERATIONAL TIMELINE / LIVE</span><h2>Adversarial cycle</h2></div><span className="live"><i /> STREAMING</span></div>
    <div className="round-track">
      {rounds.map((round, index) => <div className={`round-wrap ${index < rounds.length - 1 ? 'has-link' : ''}`} key={round.id}>
        <button className={`round-node ${round.tone} ${selected === round.id ? 'selected' : ''}`} onClick={() => setSelected(round.id)} aria-pressed={selected === round.id}>
          <span className="round-number">0{round.id}</span><span className="eyebrow">{round.label}</span><strong>{round.title}</strong><span className="muted">{round.detail}</span>
          <span className="round-result"><b>{(round.rate * 100).toFixed(1)}%</b><span>DETECTION</span></span>
          <span className="round-foot mono">{round.caught}/{round.total} intercepted <em>·</em> avg ${round.amount.toFixed(2)}</span>
        </button>
      </div>)}
    </div>
  </section>;
}

function Reasoning({ selected, rounds, data }) {
  return <section className="panel reasoning"><div className="section-head"><div><span className="eyebrow">ADVERSARY INTELLIGENCE</span><h2>Observed reasoning</h2></div><span className="tag alert">LLM TRACE / VERBATIM</span></div><div className="reasoning-text" style={{maxHeight: '120px', overflowY: 'auto', paddingRight: '8px'}}><p className="quote">“{data.llm_reasoning}”</p></div><div className="signal-row"><span className="eyebrow">CURRENT SIGNAL</span><b>ROUND 0{selected} / {rounds[selected - 1].label}</b></div></section>;
}

function ShapPanel({ data }) {
  const max = data.shap_explanation[0][1];
  return <section className="panel"><div className="section-head"><div><span className="eyebrow">DEFENSE MODEL EVIDENCE</span><h2>SHAP pressure map</h2></div><span className="mono muted">XGB / FEATURES</span></div><div className="shap-list">{data.shap_explanation.map(([name, score], index) => <div className="shap" key={name}><div><span className="mono">{name}</span><b className="mono">{score.toFixed(2)}</b></div><div className="bar"><i style={{ width: `${score / max * 100}%`, opacity: 1 - index * 0.12 }} /></div></div>)}</div></section>;
}

function CampaignTrace({ data }) {
  return <section className="panel trace"><div className="section-head"><div><span className="eyebrow">CAMPAIGN TRACE</span><h2>Mutation parameters</h2></div><span className="tag alert">MUTATED</span></div><div className="trace-grid">{Object.entries(data.mutated_params).map(([key, value]) => <div key={key}><span className="eyebrow">{key}</span><b className="mono">{value}</b></div>)}</div></section>;
}

function EventFeed() {
  return <section className="panel feed"><div className="section-head"><div><span className="eyebrow">PACKET MONITOR / 10:14:22</span><h2>Live interception feed</h2></div><span className="live"><i /> LIVE</span></div><div className="events">{mockTransactions.map(tx => <div className="event" key={tx.id}><span className="mono muted">{tx.time}</span><div><b>{tx.attackType}</b><span className="muted">{tx.reason || 'Normal transaction profile'}</span></div><strong className={`event-status ${tx.status}`}>{tx.status}</strong><span className="mono amount">${tx.amount.toFixed(2)}</span></div>)}</div></section>;
}

function App() {
  const [selected, setSelected] = useState(3);
  const [arenaData, setArenaData] = useState(demoData);
  
  useEffect(() => {
    fetch('http://localhost:8000/arena/round/1')
      .then(res => res.json())
      .then(data => {
        if (data && data.shap_explanation) setArenaData(data);
      })
      .catch(err => console.error("API fetch failed, falling back to mockData:", err));
  }, []);

  const rounds = useMemo(() => createRounds(arenaData), [arenaData]);
  const current = useMemo(() => rounds[selected - 1], [selected, rounds]);
  return <div className="console"><aside className="rail"><div className="brand"><span>PG</span><b>ARENA</b></div><div className="rail-status"><i /><span>CONSOLE<br />ONLINE</span></div><nav><button className="active"><span>01</span>Battle View</button><button><span>02</span>Model Metrics</button><button><span>03</span>GenAI Agents</button><button><span>04</span>Settings</button></nav><div className="rail-footer mono">MASTERCARD<br />ADVERSARIAL LAB<br /><small>BUILD 0.9.4 / SECURE</small></div></aside><main className="main"><header className="topbar"><div><span className="eyebrow">MISSION CONTROL / ARENA-07</span><h1>PAYGUARD <em>//</em> BATTLE VIEW</h1></div><div className="top-meta"><span className="tag green">SIMULATION ACTIVE</span><span className="mono muted">AUG 24, 2026 / 10:14:22 UTC</span></div></header><div className="alert-strip"><span className="alert-mark">!</span><b>ADVERSARIAL CYCLE IN PROGRESS</b><span className="muted">Attacker adaptation detected · Defense response deployed</span><span className="strip-round mono">ROUND 0{selected} / 03</span></div><section className="hero-stats"><Metric label="CURRENT DETECTION" value={`${(current.rate * 100).toFixed(1)}%`} sub={`${current.caught} / ${current.total} intercepted`} tone={current.tone} /><Metric label="DELTA VS BASELINE" value={`${((current.rate - arenaData.round_1_detection_rate) * 100).toFixed(1)}%`} sub="detection recovery" tone="green" /><Metric label="CAMPAIGN AVG VALUE" value={`$${current.amount.toFixed(2)}`} sub="fraud transaction amount" /><Metric label="MODEL FPR / ROUND 1" value={`${(arenaData.round_1_model_fpr * 100).toFixed(2)}%`} sub={`${arenaData.round_1_model_fp_count} false positives`} /></section><RoundTimeline selected={selected} setSelected={setSelected} rounds={rounds} /><div className="lower-grid"><div className="stack"><Reasoning selected={selected} rounds={rounds} data={arenaData} /><EventFeed /></div><div className="stack"><ShapPanel data={arenaData} /><CampaignTrace data={arenaData} /></div></div></main></div>;
}

export default App;
