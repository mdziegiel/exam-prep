import React, { useEffect, useMemo, useState } from 'react'
import { createRoot } from 'react-dom/client'
import { BarChart3, BookOpen, CheckCircle2, ChevronLeft, ChevronRight, Clock, Download, Eye, Flag, History, ListChecks, Pause, Play, Printer, RefreshCw, RotateCcw, Settings, ShieldCheck, Square, Trophy, ZoomIn, ZoomOut } from 'lucide-react'
import './index.css'

const API = '/api'
const api = async (path, options = {}) => {
  const res = await fetch(`${API}${path}`, { headers: { 'Content-Type': 'application/json' }, ...options })
  if (!res.ok) throw new Error(await res.text())
  return res.json()
}
const fmtTime = s => `${Math.floor((s || 0) / 60)}m ${Math.floor((s || 0) % 60)}s`
const fmtClock = s => `${Math.floor(Math.max(0, s) / 60)}:${String(Math.max(0, s) % 60).padStart(2, '0')}`
const pct = (n, d) => d ? Math.round((n / d) * 100) : 0

const modeDefs = [
  ['certification', 'Certification mode', 'Timed, scored at the end. Real exam pressure minus the Pearson VUE trauma.'],
  ['practice', 'Practice mode', 'Untimed practice with configurable answer display and mid-exam options.'],
  ['wrong', 'Study Wrong Answers', 'Only questions you previously missed.'],
  ['objective', 'Objective Drill', 'Pick objectives and drill only that content.'],
  ['quick', 'Quick Quiz', '10 random questions, no timer.']
]

function Shell() {
  const [page, setPage] = useState('dashboard')
  const [exams, setExams] = useState([])
  const [exam, setExam] = useState('MD-102')
  const [sessionConfig, setSessionConfig] = useState(null)
  const [refresh, setRefresh] = useState(0)
  useEffect(() => { api('/exams').then(setExams).catch(console.error) }, [refresh])
  const current = exams.find(e => e.id === exam) || exams[0]
  useEffect(() => { if (!exam && exams[0]) setExam(exams[0].id) }, [exams])
  const startSession = cfg => { setSessionConfig({ examId: exam, ...cfg }); setPage('session') }
  return <div className="min-h-screen">
    <header className="sticky top-0 z-20 border-b border-white/10 bg-ink/80 backdrop-blur-xl">
      <div className="mx-auto flex max-w-7xl items-center justify-between px-6 py-4">
        <div><h1 className="text-2xl font-black tracking-tight">IT Exam Prep</h1><p className="text-sm text-slate-400">Professional certification simulator</p></div>
        <nav className="flex flex-wrap gap-2">
          {[['dashboard', 'Dashboard', BookOpen], ['history', 'History', History], ['admin', 'Admin', ShieldCheck]].map(([id, label, Icon]) => <button key={id} onClick={() => setPage(id)} className={`btn ${page === id ? 'btn-primary' : ''}`}><Icon className="mr-2 inline h-4 w-4" />{label}</button>)}
        </nav>
      </div>
    </header>
    <main className="mx-auto max-w-7xl px-6 py-8">
      {page === 'dashboard' && <Dashboard exams={exams} openExam={id => { setExam(id); setPage('exam-detail') }} />}
      {page === 'exam-detail' && current && <ExamDetail exam={current} startSession={startSession} back={() => setPage('dashboard')} />}
      {page === 'session' && sessionConfig && <ExamSession config={sessionConfig} examMeta={current} onDone={() => { setRefresh(x => x + 1); setPage('dashboard') }} />}
      {page === 'history' && <HistoryPage />}
      {page === 'admin' && <AdminPage exams={exams} />}
    </main>
  </div>
}

function Dashboard({ exams, openExam }) {
  const [dash, setDash] = useState(null)
  const [weakAreas, setWeakAreas] = useState([])
  useEffect(() => { api('/dashboard').then(setDash).catch(console.error) }, [])
  useEffect(() => {
    Promise.all(exams.map(e => api(`/exams/${e.id}/progress`).then(rows => rows.map(r => ({ ...r, exam_id: e.id, exam_name: e.name }))).catch(() => [])))
      .then(groups => setWeakAreas(groups.flat().sort((a, b) => (a.avg_mastery || 0) - (b.avg_mastery || 0)).slice(0, 8)))
  }, [exams])
  return <div className="space-y-6">
    <section className="grid gap-4 md:grid-cols-4">
      <Metric icon={ListChecks} label="Total exams taken" value={dash?.total_exams_taken ?? 0} />
      <Metric icon={Trophy} label="Average score" value={`${dash?.average_score ?? 0}%`} />
      <Metric icon={CheckCircle2} label="Pass rate" value={`${dash?.pass_rate ?? 0}%`} />
      <Metric icon={Clock} label="Study streak" value={`${dash?.study_streak ?? 0} days`} />
    </section>
    <div className="grid gap-6 lg:grid-cols-[1fr_380px]">
      <section>
        <div className="mb-4"><h2 className="text-2xl font-black">Exam library</h2><p className="mt-1 text-sm text-slate-400">Cards now show useful telemetry. Revolutionary, apparently.</p></div>
        <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">{exams.map(e => <button key={e.id} onClick={() => openExam(e.id)} className="card p-5 text-left hover:border-emerald-400/70">
          <div className="flex items-start justify-between gap-3"><div><div className="text-sm font-bold text-cyan-300">{e.id}</div><div className="mt-2 text-lg font-black">{e.name}</div></div><div className="rounded-xl bg-slate-950/70 px-3 py-2 text-right text-xs"><b>{e.question_count}</b><br />questions</div></div>
          <p className="mt-3 line-clamp-2 text-sm text-slate-400">{e.description}</p>
          <div className="mt-4 grid grid-cols-2 gap-2 text-xs text-slate-300"><span>Passing: <b>{e.passing_score}%</b></span><span>Best: <b>{e.best_score || 0}%</b></span><span>Attempts: <b>{e.attempts || 0}</b></span><span>Last: <b>{e.last_attempt ? new Date(e.last_attempt).toLocaleDateString() : 'Never'}</b></span></div>
          <div className="mt-4 h-2 rounded-full bg-slate-800"><div className="h-2 rounded-full bg-emerald-400" style={{ width: `${e.percent_mastered}%` }} /></div>
          <div className="mt-2 text-xs text-slate-400">{e.percent_mastered}% mastered</div>
        </button>)}</div>
      </section>
      <aside className="space-y-4">
        <div className="card p-6"><h3 className="text-xl font-black">Recently missed questions</h3><div className="mt-4 space-y-3">{dash?.recently_missed?.length ? dash.recently_missed.map(q => <div key={`${q.id}-${q.created_at}`} className="rounded-xl bg-slate-950/60 p-3"><div className="text-xs text-cyan-300">{q.exam_id} · {q.objective_code}</div><p className="mt-1 line-clamp-3 text-sm">{q.question_text}</p></div>) : <p className="text-sm text-slate-400">No misses recorded yet.</p>}</div></div>
        <div className="card p-6"><h3 className="text-xl font-black">Weak areas</h3><p className="mt-2 text-sm text-slate-400">Lowest mastery across all exams.</p><div className="mt-4 space-y-3">{weakAreas.map(p => <div className="rounded-xl bg-slate-950/60 p-3" key={`${p.exam_id}-${p.code}`}><div className="flex justify-between gap-3 font-semibold"><span>{p.exam_id} · {p.code}</span><span>{Math.round((p.avg_mastery || 0) * 100)}%</span></div><div className="text-sm text-slate-400">{p.title}</div></div>)}</div></div>
      </aside>
    </div>
  </div>
}

function Metric({ icon: Icon, label, value }) { return <div className="card p-4"><Icon className="h-5 w-5 text-emerald-300" /><div className="mt-2 text-2xl font-black">{value}</div><div className="text-sm text-slate-400">{label}</div></div> }

function ExamDetail({ exam, startSession, back }) {
  const [objectives, setObjectives] = useState([])
  const [cfg, setCfg] = useState({ mode: 'certification', questionCount: exam.question_count || 100, minutes: exam.duration_minutes || 90, randomizeQuestions: true, randomizeAnswers: true, missedLast: 0, unseenLast: 0, objectives: [], answerMode: 'complete', allowChange: true })
  useEffect(() => { api(`/exams/${exam.id}/objectives`).then(setObjectives).catch(console.error); setCfg(c => ({ ...c, questionCount: exam.question_count || 100, minutes: exam.duration_minutes || 90, objectives: [] })) }, [exam.id])
  const toggleObj = code => setCfg(c => ({ ...c, objectives: c.objectives.includes(code) ? c.objectives.filter(x => x !== code) : [...c.objectives, code] }))
  const applyMode = mode => setCfg(c => ({ ...c, mode, questionCount: mode === 'quick' ? 10 : c.questionCount, minutes: mode === 'practice' || mode === 'wrong' || mode === 'objective' || mode === 'quick' ? 0 : (c.minutes || exam.duration_minutes || 90), answerMode: mode === 'certification' ? 'complete' : c.answerMode }))
  const begin = () => startSession({ ...cfg, questionCount: Number(cfg.questionCount || exam.question_count), minutes: Number(cfg.minutes || 0), timed: cfg.mode === 'certification' && Number(cfg.minutes || 0) > 0 })
  return <div className="space-y-6">
    <button className="btn" onClick={back}>← Back to dashboard</button>
    <section className="card p-6"><div className="flex flex-wrap items-start justify-between gap-6"><div><div className="text-sm font-bold text-cyan-300">{exam.id}</div><h2 className="mt-1 text-3xl font-black">{exam.name}</h2><p className="mt-2 max-w-3xl text-slate-400">{exam.description}</p></div><a className="btn btn-primary" href={`${API}/exams/${encodeURIComponent(exam.id)}/printable.pdf`} target="_blank" rel="noreferrer"><Download className="mr-2 inline h-4 w-4" />Download/Print PDF</a></div>
      <div className="mt-6 grid gap-4 md:grid-cols-4"><Metric icon={BookOpen} label="Questions" value={exam.question_count} /><Metric icon={Trophy} label="Best score" value={`${exam.best_score || 0}%`} /><Metric icon={History} label="Attempts" value={exam.attempts || 0} /><Metric icon={CheckCircle2} label="Passing score" value={`${exam.passing_score || 70}%`} /></div>
    </section>
    <section className="grid gap-6 lg:grid-cols-[1fr_440px]">
      <div className="card p-6"><h3 className="text-xl font-black">Advanced options</h3>
        <div className="mt-4 grid gap-4 md:grid-cols-2">
          <label className="text-sm text-slate-300">Number of questions<input className="input mt-1" type="number" min="1" max={exam.question_count || 500} value={cfg.questionCount} onChange={e => setCfg({ ...cfg, questionCount: e.target.value })} /></label>
          <label className="text-sm text-slate-300">Duration timer minutes<input className="input mt-1" type="number" min="0" max="600" value={cfg.minutes} onChange={e => setCfg({ ...cfg, minutes: e.target.value })} /></label>
          <label className="flex items-center gap-2 rounded-xl bg-slate-950/60 p-3 text-sm"><input type="checkbox" checked={cfg.randomizeQuestions} onChange={e => setCfg({ ...cfg, randomizeQuestions: e.target.checked })} /> Randomize question order</label>
          <label className="flex items-center gap-2 rounded-xl bg-slate-950/60 p-3 text-sm"><input type="checkbox" checked={cfg.randomizeAnswers} onChange={e => setCfg({ ...cfg, randomizeAnswers: e.target.checked })} /> Randomize answer order</label>
          <label className="text-sm text-slate-300">Show questions missed from last N tests<input className="input mt-1" type="number" min="0" value={cfg.missedLast} onChange={e => setCfg({ ...cfg, missedLast: Number(e.target.value || 0) })} /></label>
          <label className="text-sm text-slate-300">Show questions not displayed from last N tests<input className="input mt-1" type="number" min="0" value={cfg.unseenLast} onChange={e => setCfg({ ...cfg, unseenLast: Number(e.target.value || 0) })} /></label>
          <label className="text-sm text-slate-300 md:col-span-2">Answer display mode<select className="input mt-1" value={cfg.answerMode} onChange={e => setCfg({ ...cfg, answerMode: e.target.value })}><option value="complete">Do not display until test complete</option><option value="ask">Let me ask for each answer</option><option value="incorrect">Auto-display on incorrect response</option><option value="any">Auto-display on any response</option></select></label>
          <label className="flex items-center gap-2 rounded-xl bg-slate-950/60 p-3 text-sm md:col-span-2"><input type="checkbox" checked={cfg.allowChange} onChange={e => setCfg({ ...cfg, allowChange: e.target.checked })} /> Allow me to change answers before scoring</label>
        </div>
        <h4 className="mt-6 font-black">Filter by exam objective</h4><div className="mt-3 grid gap-2 md:grid-cols-2">{objectives.map(o => <label key={o.code} className="rounded-xl bg-slate-950/60 p-3 text-sm"><input className="mr-2" type="checkbox" checked={cfg.objectives.includes(o.code)} onChange={() => toggleObj(o.code)} />{o.code} · {o.title}</label>)}</div>
      </div>
      <aside className="card p-6"><h3 className="text-xl font-black">Study modes</h3><div className="mt-4 grid gap-3">{modeDefs.map(([id, label, desc]) => <button key={id} onClick={() => applyMode(id)} className={`rounded-2xl border p-4 text-left ${cfg.mode === id ? 'border-emerald-400 bg-emerald-950/30' : 'border-white/10 bg-slate-950/70'}`}><div className="font-black">{label}</div><p className="mt-1 text-sm text-slate-400">{desc}</p></button>)}</div><button onClick={begin} className="btn btn-primary mt-5 w-full">Start Exam</button></aside>
    </section>
  </div>
}

function ExamSession({ config, examMeta, onDone }) {
  const [questions, setQuestions] = useState([]), [idx, setIdx] = useState(0), [answers, setAnswers] = useState({}), [revealed, setRevealed] = useState({}), [result, setResult] = useState(null)
  const [startedAt, setStartedAt] = useState(Date.now()), [secondsLeft, setSecondsLeft] = useState((config.minutes || 0) * 60), [paused, setPaused] = useState(false), [font, setFont] = useState(18), [showNav, setShowNav] = useState(false), [showOptions, setShowOptions] = useState(false), [exhibit, setExhibit] = useState(false)
  const timed = config.timed && !result
  useEffect(() => {
    const params = new URLSearchParams({ limit: String(config.questionCount || 100), mode: config.mode, randomize_questions: String(!!config.randomizeQuestions), randomize_answers: String(!!config.randomizeAnswers) })
    if (config.objectives?.length) params.set('objectives', config.objectives.join(','))
    if (config.mode === 'wrong') params.set('wrong', '1')
    if (config.missedLast) params.set('missed_last', String(config.missedLast))
    if (config.unseenLast) params.set('unseen_last', String(config.unseenLast))
    api(`/exams/${config.examId}/queue?${params}`).then(data => { setQuestions(data); setIdx(0); setAnswers({}); setRevealed({}); setStartedAt(Date.now()); setSecondsLeft((config.minutes || 0) * 60); setResult(null) }).catch(console.error)
  }, [config.examId])
  useEffect(() => { if (!timed || paused) return; if (secondsLeft <= 0) { finish(); return } ; const t = setInterval(() => setSecondsLeft(s => Math.max(0, s - 1)), 1000); return () => clearInterval(t) }, [timed, paused, secondsLeft])
  const q = questions[idx]
  const elapsed = () => Math.round((Date.now() - startedAt) / 1000)
  const current = q ? (answers[q.id]?.selected_choice || '') : ''
  const setAnswer = value => { if (!q) return; setAnswers(a => ({ ...a, [q.id]: { question_id: q.id, selected_choice: value, elapsed_seconds: elapsed(), flagged: a[q.id]?.flagged || false } })) }
  const toggleFlag = async () => { if (!q) return; setAnswers(a => ({ ...a, [q.id]: { question_id: q.id, selected_choice: current, elapsed_seconds: elapsed(), flagged: !a[q.id]?.flagged } })); await api(`/flag/${q.id}`, { method: 'POST' }).catch(() => null) }
  const reveal = async (forced = current) => { if (!q || revealed[q.id]) return; const res = await api('/answer', { method: 'POST', body: JSON.stringify({ question_id: q.id, selected_choice: forced, elapsed_seconds: elapsed(), flagged: !!answers[q.id]?.flagged }) }); setRevealed(r => ({ ...r, [q.id]: res })); return res }
  async function choose(value) { setAnswer(value); if (config.answerMode === 'any') reveal(value); if (config.answerMode === 'incorrect') { const res = await reveal(value); if (res?.is_correct) setRevealed(r => { const n = { ...r }; delete n[q.id]; return n }) } }
  async function finish() { const final = questions.map(qq => answers[qq.id] || { question_id: qq.id, selected_choice: '', elapsed_seconds: elapsed(), flagged: false }); const res = await api('/attempts', { method: 'POST', body: JSON.stringify({ exam_id: config.examId, mode: config.mode, answers: final, time_taken_seconds: elapsed(), config }) }); setResult(res) }
  if (result) return <Results result={result} onDone={onDone} onRestart={() => window.location.reload()} />
  if (!q) return <div className="card p-8">Loading exam queue. If this stays empty, the filter is too narrow. Shocking.</div>
  const r = revealed[q.id]
  const parts = current ? current.split(',').filter(Boolean) : []
  const progress = pct(idx + 1, questions.length)
  if (paused) return <div className="card p-10 text-center"><Pause className="mx-auto h-12 w-12 text-cyan-300" /><h2 className="mt-4 text-3xl font-black">Exam paused</h2><p className="mt-2 text-slate-400">Question hidden. Timer stopped.</p><button className="btn btn-primary mt-6" onClick={() => setPaused(false)}><Play className="mr-2 inline h-4 w-4" />Resume</button></div>
  return <div className="grid gap-6 lg:grid-cols-[1fr_300px]">
    <section className="card p-6">
      <div className="mb-5 flex flex-wrap items-center justify-between gap-3"><div className="flex items-center gap-3"><div className={`rounded-xl px-4 py-2 font-mono ${secondsLeft && secondsLeft < 300 ? 'bg-red-500/20 text-red-200' : 'bg-slate-950'}`}><Clock className="mr-1 inline h-4 w-4" />{config.timed ? fmtClock(secondsLeft) : 'Untimed'}</div><button className="btn" onClick={() => setShowNav(!showNav)}>Question {idx + 1}/{questions.length}</button></div><div className="flex flex-wrap gap-2"><button className="btn" onClick={() => setFont(f => Math.max(14, f - 2))}><ZoomOut className="h-4 w-4" /></button><button className="btn" onClick={() => setFont(f => Math.min(28, f + 2))}><ZoomIn className="h-4 w-4" /></button><button className="btn" onClick={() => setPaused(true)}><Pause className="h-4 w-4" /></button><button className="btn btn-danger" onClick={() => confirm('Exit this exam without scoring?') && onDone()}><Square className="mr-1 inline h-4 w-4" />Exit</button></div></div>
      {showNav && <div className="mb-5 grid grid-cols-10 gap-2 rounded-2xl bg-slate-950/60 p-3">{questions.map((qq, i) => <button key={qq.id} className={`rounded-lg p-2 text-xs ${i === idx ? 'bg-emerald-400 text-slate-950' : answers[qq.id] ? 'bg-cyan-500/30' : 'bg-white/10'} ${answers[qq.id]?.flagged ? 'ring-2 ring-yellow-300' : ''}`} onClick={() => setIdx(i)}>{i + 1}</button>)}</div>}
      <div className="mb-6 h-2 rounded-full bg-slate-800"><div className="h-2 rounded-full bg-emerald-400" style={{ width: `${progress}%` }} /></div>
      <div className="text-sm text-cyan-300">{q.objective_code} · {q.objective_title} · {q.question_type}</div>
      <p className="mt-3 leading-relaxed" style={{ fontSize: `${font}px` }}>{q.question_text}</p>
      {q.question_type === 'multiple' && <p className="mt-2 text-sm text-yellow-200">Select {q.required_answers} answers.</p>}
      {q.exhibit && Object.keys(q.exhibit).length > 0 && <button className="btn mt-4" onClick={() => setExhibit(!exhibit)}><Eye className="mr-2 inline h-4 w-4" />Exhibit</button>}
      {exhibit && <div className="mt-4 rounded-2xl border border-cyan-400/30 bg-cyan-950/20 p-4"><b>{q.exhibit.title || 'Exhibit'}</b><p className="mt-2 text-sm text-slate-300">{q.exhibit.body || q.exhibit.text}</p>{q.exhibit.image && <img className="mt-3 max-h-80 rounded-xl" src={q.exhibit.image} />}</div>}
      <QuestionInput q={q} value={current} parts={parts} choose={choose} revealed={r} />
      <div className="mt-6 flex flex-wrap items-center justify-between gap-3"><button className="btn" disabled={idx === 0} onClick={() => setIdx(i => Math.max(0, i - 1))}><ChevronLeft className="mr-1 inline h-4 w-4" />Previous</button><div className="flex gap-2"><button className={`btn ${answers[q.id]?.flagged ? 'bg-yellow-500/30 text-yellow-100' : ''}`} onClick={toggleFlag}><Flag className="mr-1 inline h-4 w-4" />Flag</button>{config.mode !== 'certification' && <button className="btn" onClick={() => reveal()}>Show Answer</button>}<button className="btn" onClick={() => setShowOptions(!showOptions)}><Settings className="mr-1 inline h-4 w-4" />Options</button></div><button className="btn btn-primary" onClick={() => idx + 1 >= questions.length ? finish() : setIdx(i => i + 1)}>{idx + 1 >= questions.length ? 'Score Exam' : <>Next <ChevronRight className="ml-1 inline h-4 w-4" /></>}</button></div>
      {showOptions && <div className="mt-4 rounded-2xl bg-slate-950/70 p-4 text-sm text-slate-300">Mid-exam options: use font controls, pause, flag, jump list, or show answer. Answer display mode changes require starting a new session because mutating rules mid-score is how bad software gets religion.</div>}
      {r && <AnswerPanel answer={r} />}
    </section>
    <aside className="card h-fit p-5"><h3 className="font-black">Review palette</h3><div className="mt-4 grid grid-cols-5 gap-2">{questions.map((qq, i) => <button key={qq.id} onClick={() => setIdx(i)} className={`rounded-lg p-2 text-xs ${i === idx ? 'bg-emerald-400 text-slate-950' : answers[qq.id] ? 'bg-cyan-500/20' : 'bg-slate-950'} ${answers[qq.id]?.flagged ? 'ring-2 ring-yellow-300' : ''}`}>{i + 1}</button>)}</div><button className="btn btn-primary mt-5 w-full" onClick={finish}>Score now</button></aside>
  </div>
}

function QuestionInput({ q, value, parts, choose, revealed }) {
  const classify = key => revealed ? (revealed.correct?.includes(key) || revealed.correct_choice?.split(',').includes(key) ? 'border-emerald-400 bg-emerald-500/20' : parts.includes(key) ? 'border-red-400 bg-red-500/20' : 'border-white/10 bg-slate-950/70') : (parts.includes(key) || value === key ? 'border-cyan-400 bg-cyan-500/20' : 'border-white/10 bg-slate-950/70 hover:border-cyan-400')
  if (q.question_type === 'multiple') return <div className="mt-6 grid gap-3">{q.choices.map(c => <label key={c.key} className={`rounded-2xl border p-4 transition ${classify(c.key)}`}><input className="mr-3" type="checkbox" checked={parts.includes(c.key)} onChange={e => choose(e.target.checked ? [...parts, c.key].join(',') : parts.filter(x => x !== c.key).join(','))} /><b>{c.key}.</b> {c.text}</label>)}</div>
  if (q.question_type === 'order') { const ordered = parts.length ? parts : q.choices.map(c => c.key); const move = (from, to) => { const arr = [...ordered]; const [x] = arr.splice(from, 1); arr.splice(to, 0, x); choose(arr.join(',')) }; return <div className="mt-6 space-y-3"><p className="text-sm text-slate-400">Drag and drop the actions into the correct order. Current: {ordered.join(' → ')}</p>{ordered.map((key, i) => { const c = q.choices.find(x => x.key === key); return <div key={key} draggable onDragStart={e => e.dataTransfer.setData('text/plain', String(i))} onDragOver={e => e.preventDefault()} onDrop={e => move(Number(e.dataTransfer.getData('text/plain')), i)} onClick={() => !parts.includes(key) && choose([...parts, key].join(','))} className={`cursor-move rounded-2xl border p-4 text-left ${classify(key)}`}><b>{i + 1}.</b> {c?.key}. {c?.text}</div> })}<button className="btn" onClick={() => choose('')}>Reset order</button></div> }
  if (q.question_type === 'match') { const ordered = parts.length ? parts : q.choices.map(c => c.key); const move = (from, to) => { const arr = [...ordered]; const [x] = arr.splice(from, 1); arr.splice(to, 0, x); choose(arr.join(',')) }; return <div className="mt-6 space-y-3"><p className="text-sm text-slate-400">Drag choices to form the requested match sequence. Current: {ordered.join(' → ')}</p>{ordered.map((key, i) => { const c = q.choices.find(x => x.key === key); return <div key={key} draggable onDragStart={e => e.dataTransfer.setData('text/plain', String(i))} onDragOver={e => e.preventDefault()} onDrop={e => move(Number(e.dataTransfer.getData('text/plain')), i)} className={`cursor-move rounded-2xl border p-4 text-left ${classify(key)}`}><b>{key}.</b> {c?.text}</div> })}</div> }
  return <div className="mt-6 grid gap-3">{q.choices.map(c => <button key={c.key} onClick={() => choose(c.key)} className={`rounded-2xl border p-4 text-left transition ${classify(c.key)}`}><b>{c.key}.</b> {c.text}</button>)}</div>
}

function AnswerPanel({ answer }) { return <div className="mt-6 rounded-2xl border border-white/10 bg-slate-950/80 p-5"><div className={`font-black ${answer.is_correct ? 'text-emerald-300' : 'text-red-300'}`}>{answer.is_correct ? 'Correct' : 'Incorrect'} · Correct answer {answer.correct_choice}</div><p className="mt-2 text-slate-300">{answer.explanation}</p><div className="mt-3 text-sm text-cyan-300">Objective: {answer.objective_code} · {answer.objective_title}</div>{answer.references?.length > 0 && <div className="mt-3 text-sm"><b>References</b><ul className="mt-1 list-disc pl-5">{answer.references.map((r, i) => <li key={i}><a className="text-cyan-300 underline" href={r.url} target="_blank" rel="noreferrer">{r.title || r.url}</a></li>)}</ul></div>}</div> }

function Results({ result, onDone, onRestart }) {
  const [tab, setTab] = useState('objectives'), [open, setOpen] = useState(null)
  const rows = Object.entries(result.breakdown || {})
  const chartPoints = rows.map(([code, b]) => ({ code, score: pct(b.correct, b.total) }))
  return <div className="card p-8"><div className="flex flex-wrap items-start justify-between gap-6"><div><div className={`text-sm font-black ${result.passed ? 'text-emerald-300' : 'text-red-300'}`}>{result.passed ? 'PASS' : 'FAIL'}</div><h2 className="mt-2 text-5xl font-black">{result.score}%</h2><p className="mt-2 text-slate-400">{result.exam_name} · {new Date(result.created_at).toLocaleString()}</p><p className="mt-1 text-slate-400">{result.correct} correct out of {result.total}. Passing score: {result.passing_score}%. Time: {fmtTime(result.time_taken_seconds)}.</p></div><Trophy className="h-16 w-16 text-emerald-300" /></div>
    <div className="mt-6 flex flex-wrap gap-3"><button className="btn btn-primary" onClick={onDone}>Back to dashboard</button><button className="btn" onClick={onRestart}><RotateCcw className="mr-1 inline h-4 w-4" />Retake Test</button><button className="btn" onClick={() => window.print()}><Printer className="mr-1 inline h-4 w-4" />Print Report</button><button className="btn" onClick={() => setTab('review')}>Review Questions</button><button className="btn" onClick={() => setTab('history')}>View Test History</button></div>
    <div className="mt-8 flex gap-2"><button className={`btn ${tab === 'objectives' ? 'btn-primary' : ''}`} onClick={() => setTab('objectives')}>Objectives view</button><button className={`btn ${tab === 'graphics' ? 'btn-primary' : ''}`} onClick={() => setTab('graphics')}><BarChart3 className="mr-1 inline h-4 w-4" />Graphics/chart view</button><button className={`btn ${tab === 'review' ? 'btn-primary' : ''}`} onClick={() => setTab('review')}>Question list review</button></div>
    {tab === 'objectives' && <div><h3 className="mt-8 text-xl font-black">Objective breakdown</h3><div className="mt-4 space-y-3">{rows.map(([code, b]) => { const p = pct(b.correct, b.total); return <div key={code}><div className="mb-1 flex justify-between text-sm"><span>{code} · {b.title}</span><span>{b.correct}/{b.total} · {p}%</span></div><div className="h-3 rounded-full bg-slate-800"><div className={`h-3 rounded-full ${p >= result.passing_score ? 'bg-emerald-400' : 'bg-red-400'}`} style={{ width: `${p}%` }} /></div></div> })}</div></div>}
    {tab === 'graphics' && <div className="mt-8"><h3 className="text-xl font-black">Score graphics</h3><div className="mt-4 flex h-60 items-end gap-3 rounded-2xl bg-slate-950/70 p-4">{chartPoints.map(p => <div key={p.code} className="flex flex-1 flex-col items-center gap-2"><div className="w-full rounded-t bg-cyan-400" style={{ height: `${Math.max(4, p.score * 1.8)}px` }} /><span className="text-xs">{p.code}</span><span className="text-xs text-slate-400">{p.score}%</span></div>)}</div><HistoryChart examId={result.exam_id} /></div>}
    {tab === 'review' && <div className="mt-8 space-y-3">{result.review_questions?.map((w, i) => <div key={w.id} className={`rounded-2xl p-4 ${w.is_correct ? 'bg-emerald-950/20' : 'bg-red-950/20'}`}><button className="flex w-full items-center justify-between text-left font-semibold" onClick={() => setOpen(open === i ? null : i)}><span>{i + 1}. {w.objective_code} · {w.question_text}</span><span>{w.is_correct ? '✓' : '✕'} {open === i ? '−' : '+'}</span></button>{open === i && <div className="mt-3 space-y-2 text-sm text-slate-300"><p><b>Your answer:</b> {w.selected_text || 'No answer'}</p><p><b>Correct answer:</b> {w.correct_text}</p><p><b>Explanation:</b> {w.explanation}</p>{w.references?.map((r, n) => <a key={n} className="block text-cyan-300 underline" href={r.url} target="_blank" rel="noreferrer">{r.title || r.url}</a>)}</div>}</div>)}</div>}
    {tab === 'history' && <HistoryPage examId={result.exam_id} embedded />}
  </div>
}

function HistoryChart({ examId }) { const [rows, setRows] = useState([]); useEffect(() => { api(`/attempts?exam_id=${examId}`).then(r => setRows(r.reverse().slice(-12))).catch(() => []) }, [examId]); return <div className="mt-6"><h4 className="font-black">Score history chart</h4><div className="mt-3 flex h-40 items-end gap-2 rounded-2xl bg-slate-950/70 p-4">{rows.map(r => <div key={r.id} className="flex-1 rounded-t bg-emerald-400" title={`${r.score}%`} style={{ height: `${Math.max(4, r.score * 1.3)}px` }} />)}</div></div> }
function HistoryPage({ examId = '', embedded = false }) { const [rows, setRows] = useState([]); useEffect(() => { api(`/attempts${examId ? `?exam_id=${examId}` : ''}`).then(setRows).catch(console.error) }, [examId]); return <div className={embedded ? '' : 'card p-6'}><h2 className="text-2xl font-black">Attempt history</h2><div className="mt-4 overflow-auto scrollbar"><table className="w-full text-left"><thead className="text-slate-400"><tr><th>Date</th><th>Exam</th><th>Mode</th><th>Score</th><th>Result</th><th>Time</th></tr></thead><tbody>{rows.map(r => <tr className="border-t border-white/10" key={r.id}><td className="py-3">{new Date(r.created_at).toLocaleString()}</td><td>{r.exam_id}</td><td>{r.mode}</td><td>{r.score}%</td><td className={r.passed ? 'text-emerald-300' : 'text-red-300'}>{r.passed ? 'PASS' : 'FAIL'}</td><td>{fmtTime(r.time_taken_seconds)}</td></tr>)}</tbody></table></div></div> }

function AdminPage({ exams }) { const [exam, setExam] = useState('MD-102'), [queue, setQueue] = useState([]), [runs, setRuns] = useState([]), [msg, setMsg] = useState(''); const load = () => { api('/admin/review').then(setQueue); api('/admin/refresh-runs').then(setRuns) }; useEffect(load, []); async function refresh(source) { setMsg('Running refresh. Claude is used only if ANTHROPIC_API_KEY exists.'); const r = await api('/admin/refresh', { method: 'POST', body: JSON.stringify({ exam_id: exam, source }) }); setMsg(`${r.status}: imported ${r.imported}, skipped ${r.skipped}. ${r.messages.join('; ')}`); load() } async function act(id, action) { await api(`/admin/review/${id}`, { method: 'POST', body: JSON.stringify({ action }) }); load() } return <div className="grid gap-6 lg:grid-cols-[360px_1fr]"><aside className="card p-6"><h2 className="text-2xl font-black">Admin</h2><label className="mt-4 block text-sm text-slate-400">Exam</label><select className="input mt-1" value={exam} onChange={e => setExam(e.target.value)}>{exams.map(e => <option key={e.id}>{e.id}</option>)}</select><div className="mt-4 grid gap-2"><button className="btn btn-primary" onClick={() => refresh('all')}><RefreshCw className="mr-2 inline h-4 w-4" />Check for new questions</button><button className="btn" onClick={() => refresh('llm')}>Claude generation only</button><button className="btn" onClick={() => refresh('scraper')}>Scraper only</button></div><p className="mt-4 text-sm text-slate-400">{msg}</p></aside><section className="card p-6"><h3 className="text-xl font-black">Review queue</h3><div className="mt-4 max-h-[620px] space-y-4 overflow-auto pr-2 scrollbar">{queue.map(q => <div className="rounded-2xl bg-slate-950/70 p-4" key={q.id}><div className="text-xs text-cyan-300">{q.exam_id} · {q.objective_code} · {q.source}</div><p className="mt-2 font-semibold">{q.question_text}</p><p className="mt-2 text-sm text-slate-400">Answer {q.correct_choice}: {q.explanation}</p><div className="mt-3 flex gap-2"><button className="btn btn-primary" onClick={() => act(q.id, 'approve')}>Approve</button><button className="btn btn-danger" onClick={() => act(q.id, 'reject')}>Reject</button></div></div>)}</div><h3 className="mt-8 text-xl font-black">Refresh runs</h3><div className="mt-3 space-y-2 text-sm text-slate-400">{runs.map(r => <div key={r.id}>{r.created_at} · {r.exam_id} · {r.source} · {r.imported}/{r.skipped} · {r.message}</div>)}</div></section></div> }

createRoot(document.getElementById('root')).render(<Shell />)
