import React, { useEffect, useState } from 'react'
import { createRoot } from 'react-dom/client'
import { BookOpen, CheckCircle2, Clock, Download, Flag, History, Plus, RefreshCw, RotateCcw, ShieldCheck, Square, Trophy } from 'lucide-react'
import './index.css'

const API = '/api'
const api = async (path, options = {}) => {
  const res = await fetch(`${API}${path}`, { headers: { 'Content-Type': 'application/json' }, ...options })
  if (!res.ok) throw new Error(await res.text())
  return res.json()
}
const fmtTime = s => `${Math.floor((s || 0) / 60)}m ${Math.floor((s || 0) % 60)}s`
const fmtClock = s => `${Math.floor(Math.max(0, s) / 60)}:${String(Math.max(0, s) % 60).padStart(2, '0')}`

function Shell() {
  const [page, setPage] = useState('dashboard')
  const [exams, setExams] = useState([])
  const [exam, setExam] = useState('MD-102')
  const [sessionConfig, setSessionConfig] = useState(null)
  const [refresh, setRefresh] = useState(0)
  useEffect(() => { api('/exams').then(setExams).catch(console.error) }, [refresh])
  const current = exams.find(e => e.id === exam) || exams[0]
  useEffect(() => { if (!exam && exams[0]) setExam(exams[0].id) }, [exams])
  const openExam = examId => { setExam(examId); setPage('exam-detail') }
  const startSession = cfg => { setSessionConfig({ examId: exam, ...cfg }); setPage('session') }
  const finishSession = () => { setRefresh(x => x + 1); setPage('dashboard') }
  return <div className="min-h-screen">
    <header className="sticky top-0 z-20 border-b border-white/10 bg-ink/80 backdrop-blur-xl">
      <div className="mx-auto flex max-w-7xl items-center justify-between px-6 py-4">
        <div><h1 className="text-2xl font-black tracking-tight">IT Exam Prep</h1><p className="text-sm text-slate-400">Self-hosted certification training engine</p></div>
        <nav className="flex gap-2">
          {[['dashboard', 'Dashboard', BookOpen], ['history', 'History', History], ['admin', 'Admin', ShieldCheck]].map(([id, label, Icon]) => <button key={id} onClick={() => setPage(id)} className={`btn ${page === id ? 'btn-primary' : ''}`}><Icon className="mr-2 inline h-4 w-4" />{label}</button>)}
        </nav>
      </div>
    </header>
    <main className="mx-auto max-w-7xl px-6 py-8">
      {page === 'dashboard' && <Dashboard exams={exams} openExam={openExam} />}
      {page === 'exam-detail' && current && <ExamDetail exam={current} startSession={startSession} back={() => setPage('dashboard')} />}
      {page === 'session' && sessionConfig && <ExamSession config={sessionConfig} examMeta={current} onDone={finishSession} />}
      {page === 'history' && <HistoryPage />}
      {page === 'admin' && <AdminPage exams={exams} />}
    </main>
  </div>
}

function Dashboard({ exams, openExam }) {
  const [weakAreas, setWeakAreas] = useState([])
  useEffect(() => {
    Promise.all(exams.map(e => api(`/exams/${e.id}/progress`).then(rows => rows.map(r => ({ ...r, exam_id: e.id, exam_name: e.name }))).catch(() => [])))
      .then(groups => setWeakAreas(groups.flat().sort((a, b) => (a.avg_mastery || 0) - (b.avg_mastery || 0)).slice(0, 8)))
  }, [exams])
  return <div className="grid gap-6 lg:grid-cols-[1fr_360px]">
    <section>
      <div className="mb-4"><h2 className="text-2xl font-black">Exam library</h2><p className="mt-1 text-sm text-slate-400">Pick an exam. The details live on their own page, like a civilized application.</p></div>
      <div className="grid gap-4 md:grid-cols-3 xl:grid-cols-4">{exams.map(e => <button key={e.id} onClick={() => openExam(e.id)} className="card p-5 text-left hover:border-emerald-400/70">
        <div className="text-sm font-bold text-cyan-300">{e.id} — {e.question_count} questions</div>
        <div className="mt-2 text-lg font-black">{e.name}</div>
        <div className="mt-3 text-sm text-slate-400">Passing score: {e.passing_score}% · {e.duration_minutes || 90} min</div>
        <div className="mt-4 h-2 rounded-full bg-slate-800"><div className="h-2 rounded-full bg-emerald-400" style={{ width: `${e.percent_mastered}%` }} /></div>
        <div className="mt-2 text-xs text-slate-400">{e.percent_mastered}% mastered</div>
      </button>)}</div>
    </section>
    <aside className="card h-fit p-6"><h3 className="text-xl font-black">Weak areas</h3><p className="mt-2 text-sm text-slate-400">Lowest mastery across all exams. Pain, sorted ascending.</p><div className="mt-4 space-y-3">{weakAreas.map(p => <div className="rounded-xl bg-slate-950/60 p-3" key={`${p.exam_id}-${p.code}`}><div className="flex justify-between gap-3 font-semibold"><span>{p.exam_id} · {p.code}</span><span>{Math.round((p.avg_mastery || 0) * 100)}%</span></div><div className="text-sm text-slate-400">{p.title}</div></div>)}</div></aside>
  </div>
}

function ExamDetail({ exam, startSession, back }) {
  const [progress, setProgress] = useState([])
  const [mode, setMode] = useState('practice')
  const [objective, setObjective] = useState('')
  const [minutes, setMinutes] = useState(exam.duration_minutes || 90)
  const [retryWrong, setRetryWrong] = useState(false)
  useEffect(() => { api(`/exams/${exam.id}/progress`).then(setProgress).catch(console.error); setMinutes(exam.duration_minutes || 90); setObjective(''); setRetryWrong(false) }, [exam.id])
  const printUrl = `${API}/exams/${encodeURIComponent(exam.id)}/printable.pdf`
  const begin = () => startSession({ mode, timed: mode === 'certification', minutes: mode === 'certification' ? minutes : 0, objective: mode === 'practice' ? objective : '', retryWrong: mode === 'practice' && retryWrong })
  return <div className="space-y-6">
    <button className="btn" onClick={back}>← Back to dashboard</button>
    <section className="card p-6"><div className="flex flex-wrap items-start justify-between gap-6"><div><div className="text-sm font-bold text-cyan-300">{exam.id}</div><h2 className="mt-1 text-3xl font-black">{exam.name}</h2><p className="mt-2 max-w-3xl text-slate-400">{exam.description}</p></div><a className="btn btn-primary" href={printUrl} target="_blank" rel="noreferrer"><Download className="mr-2 inline h-4 w-4" />Download/Print PDF</a></div>
      <div className="mt-6 grid gap-4 md:grid-cols-4"><Metric icon={BookOpen} label="Questions" value={exam.question_count} /><Metric icon={Trophy} label="Mastered" value={`${exam.percent_mastered || 0}%`} /><Metric icon={Clock} label="Time spent" value={fmtTime(exam.time_spent_seconds)} /><Metric icon={CheckCircle2} label="Passing score" value={`${exam.passing_score || 70}%`} /></div>
    </section>
    <section className="grid gap-6 lg:grid-cols-[1fr_420px]">
      <div className="card p-6"><h3 className="text-xl font-black">Objective breakdown</h3><div className="mt-4 space-y-3">{progress.map(p => <div key={p.code}><div className="mb-1 flex justify-between text-sm"><span>{p.code} · {p.title}</span><span>{Math.round((p.avg_mastery || 0) * 100)}%</span></div><div className="h-2 rounded-full bg-slate-800"><div className="h-2 rounded-full bg-cyan-400" style={{ width: `${Math.round((p.avg_mastery || 0) * 100)}%` }} /></div></div>)}</div></div>
      <aside className="card p-6"><h3 className="text-xl font-black">Choose mode</h3><div className="mt-4 grid gap-3">
        <button onClick={() => setMode('practice')} className={`rounded-2xl border p-4 text-left ${mode === 'practice' ? 'border-emerald-400 bg-emerald-950/30' : 'border-white/10 bg-slate-950/70'}`}><div className="font-black">Practice Mode</div><p className="mt-1 text-sm text-slate-400">Untimed. Shows correct answer and full explanation after each question. Filter objectives. Retry wrong answers.</p></button>
        <button onClick={() => setMode('certification')} className={`rounded-2xl border p-4 text-left ${mode === 'certification' ? 'border-emerald-400 bg-emerald-950/30' : 'border-white/10 bg-slate-950/70'}`}><div className="font-black">Certification Mode</div><p className="mt-1 text-sm text-slate-400">Timed at real exam duration. No feedback until the end. Simulates pressure without lying about it.</p></button>
      </div>
      {mode === 'practice' && <div className="mt-5 space-y-3 rounded-2xl bg-slate-950/60 p-4"><label className="block text-sm text-slate-300">Objective filter<select className="input mt-1" value={objective} onChange={e => setObjective(e.target.value)}><option value="">All objectives</option>{progress.map(p => <option key={p.code} value={p.code}>{p.code} · {p.title}</option>)}</select></label><label className="flex items-center gap-2 text-sm"><input type="checkbox" checked={retryWrong} onChange={e => setRetryWrong(e.target.checked)} /> Retry wrong answers first</label></div>}
      {mode === 'certification' && <div className="mt-5 rounded-2xl bg-slate-950/60 p-4"><label className="text-sm text-slate-300">Timer minutes <input className="input ml-2 inline w-24" type="number" min="1" max="300" value={minutes} onChange={e => setMinutes(Number(e.target.value || exam.duration_minutes || 90))} /></label><p className="mt-2 text-xs text-slate-500">Default comes from the exam metadata.</p></div>}
      <button onClick={begin} className="btn btn-primary mt-5 w-full">Start Exam</button></aside>
    </section>
  </div>
}
function Metric({ icon: Icon, label, value }) { return <div className="rounded-2xl bg-slate-950/70 p-4"><Icon className="h-5 w-5 text-emerald-300" /><div className="mt-2 text-2xl font-black">{value}</div><div className="text-sm text-slate-400">{label}</div></div> }

function ExamSession({ config, examMeta, onDone }) {
  const [round, setRound] = useState(0)
  const [questions, setQuestions] = useState([])
  const [idx, setIdx] = useState(0)
  const [answered, setAnswered] = useState(null)
  const [selected, setSelected] = useState(null)
  const [answers, setAnswers] = useState([])
  const [startedAt, setStartedAt] = useState(Date.now())
  const [secondsLeft, setSecondsLeft] = useState((config.minutes || examMeta?.duration_minutes || 90) * 60)
  const [result, setResult] = useState(null)
  const isCertification = config.mode === 'certification'
  const activeTimer = isCertification && !result

  useEffect(() => {
    const params = new URLSearchParams({ limit: isCertification ? '100' : '20', mode: config.mode })
    if (config.objective) params.set('objective', config.objective)
    if (config.retryWrong) params.set('wrong', '1')
    const qs = config.questions ? Promise.resolve(config.questions.map(q => ({ ...q, choices: q.choices || [] }))) : api(`/exams/${config.examId}/queue?${params.toString()}`)
    qs.then(data => { setQuestions(data); setIdx(0); setAnswered(null); setSelected(null); setAnswers([]); setStartedAt(Date.now()); setSecondsLeft((config.minutes || examMeta?.duration_minutes || 90) * 60); setResult(null) }).catch(console.error)
  }, [config.examId, config.mode, config.questions, config.minutes, config.objective, config.retryWrong, round])

  useEffect(() => {
    if (!activeTimer) return
    if (secondsLeft <= 0) { finish(); return }
    const t = setInterval(() => setSecondsLeft(s => Math.max(0, s - 1)), 1000)
    return () => clearInterval(t)
  }, [activeTimer, secondsLeft])

  const q = questions[idx]
  const elapsed = () => Math.round((Date.now() - startedAt) / 1000)
  const rememberAnswer = choice => setAnswers(a => a.find(x => x.question_id === q.id) ? a.map(x => x.question_id === q.id ? { question_id: q.id, selected_choice: choice, elapsed_seconds: elapsed() } : x) : [...a, { question_id: q.id, selected_choice: choice, elapsed_seconds: elapsed() }])
  async function choose(choice) {
    if (!q) return
    if (isCertification) { setSelected(choice); rememberAnswer(choice); return }
    if (answered) return
    const res = await api('/answer', { method: 'POST', body: JSON.stringify({ question_id: q.id, selected_choice: choice, elapsed_seconds: elapsed() }) })
    setSelected(choice)
    setAnswered(res)
    rememberAnswer(choice)
  }
  async function finish(finalAnswers = answers) {
    const res = await api('/attempts', { method: 'POST', body: JSON.stringify({ exam_id: config.examId, mode: config.mode, answers: finalAnswers, time_taken_seconds: elapsed() }) })
    setResult(res)
  }
  function restart() { setRound(r => r + 1) }
  function nextCertification() { if (!selected || !q) return; if (idx + 1 >= questions.length) finish(); else { setIdx(i => i + 1); setSelected(null) } }
  function studyWrong() {
    setQuestions([]); setResult(null); setIdx(0); setAnswered(null); setSelected(null); setAnswers([]); setStartedAt(Date.now())
    api(`/exams/${config.examId}/queue?ids=${(result?.wrong_questions || []).map(w => w.id).join(',')}&limit=100`).then(setQuestions)
  }
  if (result) return <Results result={result} onDone={onDone} onRestart={restart} onStudyWrong={studyWrong} />
  if (!q) return <div className="card p-8">Loading exam queue.</div>
  const pct = Math.round(((idx + 1) / questions.length) * 100)
  return <div className="card p-6">
    <div className="mb-6 flex flex-wrap items-center justify-between gap-4"><div><div className="text-sm text-cyan-300">{config.examId} · {isCertification ? 'CERTIFICATION' : 'PRACTICE'}</div><h2 className="text-2xl font-black">Question {idx + 1} / {questions.length}</h2></div><div className="flex flex-wrap items-center gap-3"><button className="btn" onClick={restart}><RotateCcw className="mr-1 inline h-4 w-4" />Restart</button><button className="btn btn-danger" onClick={() => finish()}><Square className="mr-1 inline h-4 w-4" />End Exam</button><button className="btn" onClick={() => api(`/flag/${q.id}`, { method: 'POST' })}><Flag className="inline h-4 w-4" /> Flag</button>{activeTimer && <div className={`rounded-xl px-4 py-2 font-mono ${secondsLeft < 300 ? 'bg-red-500/20 text-red-200' : 'bg-slate-950'}`}>{fmtClock(secondsLeft)}</div>}</div></div>
    <div className="mb-6 h-2 rounded-full bg-slate-800"><div className="h-2 rounded-full bg-emerald-400" style={{ width: `${pct}%` }} /></div>
    <p className="text-xl leading-relaxed">{q.question_text}</p>
    <div className="mt-6 grid gap-3">{q.choices.map(c => { const hit = !isCertification && answered && c.key === answered.correct_choice, miss = !isCertification && answered && c.key === answered.selected_choice && !answered.is_correct, picked = isCertification && selected === c.key; return <button key={c.key} onClick={() => choose(c.key)} className={`rounded-2xl border p-4 text-left transition ${hit ? 'border-emerald-400 bg-emerald-500/20' : miss ? 'border-red-400 bg-red-500/20' : picked ? 'border-cyan-400 bg-cyan-500/20' : 'border-white/10 bg-slate-950/70 hover:border-cyan-400'}`}><b>{c.key}.</b> {c.text}</button> })}</div>
    {isCertification && <div className="mt-6 flex justify-end"><button disabled={!selected} className="btn btn-primary disabled:cursor-not-allowed disabled:opacity-50" onClick={nextCertification}>{idx + 1 >= questions.length ? 'Finish' : 'Next question'}</button></div>}
    {!isCertification && answered && <div className="mt-6 rounded-2xl border border-white/10 bg-slate-950/80 p-5"><div className={`font-black ${answered.is_correct ? 'text-emerald-300' : 'text-red-300'}`}>{answered.is_correct ? 'Correct' : 'Wrong'} · Answer {answered.correct_choice}</div><p className="mt-2 text-slate-300">{answered.explanation}</p><p className="mt-2 text-sm text-cyan-300">Objective: {answered.objective_code} · {answered.objective_title}</p><button className="btn btn-primary mt-4" onClick={() => { if (idx + 1 >= questions.length) finish(); else { setIdx(i => i + 1); setAnswered(null); setSelected(null) } }}>{idx + 1 >= questions.length ? 'Finish' : 'Next question'}</button></div>}
  </div>
}

function Results({ result, onDone, onRestart, onStudyWrong }) {
  const rows = Object.entries(result.breakdown || {})
  const [open, setOpen] = useState(null)
  return <div className="card p-8"><div className="flex flex-wrap items-start justify-between gap-6"><div><div className={`text-sm font-black ${result.passed ? 'text-emerald-300' : 'text-red-300'}`}>{result.passed ? 'PASS' : 'FAIL'}</div><h2 className="mt-2 text-5xl font-black">{result.score}%</h2><p className="mt-2 text-slate-400">{result.correct} correct out of {result.total}. Passing score: {result.passing_score}%.</p><p className="mt-1 text-slate-400">Time taken: {fmtTime(result.time_taken_seconds)}</p></div><Trophy className="h-16 w-16 text-emerald-300" /></div>
    <div className="mt-6 flex flex-wrap gap-3"><button className="btn btn-primary" onClick={onDone}>Back to dashboard</button><button className="btn" onClick={onRestart}><RotateCcw className="mr-1 inline h-4 w-4" />Restart</button>{result.wrong_questions?.length > 0 && <button className="btn" onClick={onStudyWrong}>Study Wrong Answers</button>}</div>
    <h3 className="mt-8 text-xl font-black">Objective breakdown</h3><div className="mt-4 space-y-3">{rows.map(([code, b]) => { const pct = Math.round((b.correct / b.total) * 100); return <div key={code}><div className="mb-1 flex justify-between text-sm"><span>{code} · {b.title}</span><span>{b.correct}/{b.total} · {pct}%</span></div><div className="h-2 rounded-full bg-slate-800"><div className={`h-2 rounded-full ${pct >= result.passing_score ? 'bg-emerald-400' : 'bg-red-400'}`} style={{ width: `${pct}%` }} /></div></div> })}</div>
    <h3 className="mt-8 text-xl font-black">Wrong answer drill-down</h3>{!result.wrong_questions?.length && <p className="mt-2 text-slate-400">No missed questions. Disturbingly competent.</p>}<div className="mt-4 space-y-3">{result.wrong_questions?.map((w, i) => <div key={w.id} className="rounded-2xl bg-slate-950/70 p-4"><button className="flex w-full items-center justify-between text-left font-semibold" onClick={() => setOpen(open === i ? null : i)}><span>{w.objective_code} · {w.question_text}</span><span>{open === i ? '−' : '+'}</span></button>{open === i && <div className="mt-3 space-y-2 text-sm text-slate-300"><p><b>Your answer:</b> {w.selected_choice}. {w.selected_text}</p><p><b>Correct answer:</b> {w.correct_choice}. {w.correct_text}</p><p><b>Explanation:</b> {w.explanation}</p></div>}</div>)}</div>
  </div>
}

function HistoryPage() { const [rows, setRows] = useState([]); useEffect(() => { api('/attempts').then(setRows) }, []); return <div className="card p-6"><h2 className="text-2xl font-black">Attempt history</h2><div className="mt-4 overflow-auto scrollbar"><table className="w-full text-left"><thead className="text-slate-400"><tr><th>Date</th><th>Exam</th><th>Mode</th><th>Score</th><th>Result</th><th>Time</th></tr></thead><tbody>{rows.map(r => <tr className="border-t border-white/10" key={r.id}><td className="py-3">{new Date(r.created_at).toLocaleString()}</td><td>{r.exam_id}</td><td>{r.mode}</td><td>{r.score}%</td><td className={r.passed ? 'text-emerald-300' : 'text-red-300'}>{r.passed ? 'PASS' : 'FAIL'}</td><td>{fmtTime(r.time_taken_seconds)}</td></tr>)}</tbody></table></div></div> }

function AdminPage({ exams }) { const [exam, setExam] = useState('MD-102'), [queue, setQueue] = useState([]), [runs, setRuns] = useState([]), [msg, setMsg] = useState(''); const load = () => { api('/admin/review').then(setQueue); api('/admin/refresh-runs').then(setRuns) }; useEffect(load, []); async function refresh(source) { setMsg('Running refresh. If Claude key is absent, LLM generation will be skipped.'); const r = await api('/admin/refresh', { method: 'POST', body: JSON.stringify({ exam_id: exam, source }) }); setMsg(`${r.status}: imported ${r.imported}, skipped ${r.skipped}. ${r.messages.join('; ')}`); load() } async function act(id, action) { await api(`/admin/review/${id}`, { method: 'POST', body: JSON.stringify({ action }) }); load() } return <div className="grid gap-6 lg:grid-cols-[360px_1fr]"><aside className="card p-6"><h2 className="text-2xl font-black">Admin</h2><label className="mt-4 block text-sm text-slate-400">Exam</label><select className="input mt-1" value={exam} onChange={e => setExam(e.target.value)}>{exams.map(e => <option key={e.id}>{e.id}</option>)}</select><div className="mt-4 grid gap-2"><button className="btn btn-primary" onClick={() => refresh('all')}><RefreshCw className="mr-2 inline h-4 w-4" />Check for new questions</button><button className="btn" onClick={() => refresh('llm')}>Claude generation only</button><button className="btn" onClick={() => refresh('scraper')}>Scraper only</button></div><p className="mt-4 text-sm text-slate-400">{msg}</p><ManualForm exam={exam} onDone={load} /></aside><section className="card p-6"><h3 className="text-xl font-black">Review queue</h3><div className="mt-4 max-h-[620px] space-y-4 overflow-auto pr-2 scrollbar">{queue.map(q => <div className="rounded-2xl bg-slate-950/70 p-4" key={q.id}><div className="text-xs text-cyan-300">{q.exam_id} · {q.objective_code} · {q.source}</div><p className="mt-2 font-semibold">{q.question_text}</p><p className="mt-2 text-sm text-slate-400">Answer {q.correct_choice}: {q.explanation}</p><div className="mt-3 flex gap-2"><button className="btn btn-primary" onClick={() => act(q.id, 'approve')}>Approve</button><button className="btn btn-danger" onClick={() => act(q.id, 'reject')}>Reject</button></div></div>)}</div><h3 className="mt-8 text-xl font-black">Refresh history</h3><div className="mt-3 space-y-2 text-sm text-slate-400">{runs.slice(0, 6).map(r => <div key={r.id}>{r.created_at} · {r.exam_id} · {r.source} · imported {r.imported} · {r.message}</div>)}</div></section></div> }
function ManualForm({ exam, onDone }) { const [text, setText] = useState(''); async function submit() { let q; try { q = JSON.parse(text) } catch { alert('Paste valid JSON. Satan accepts strict syntax.'); return } await api('/admin/questions', { method: 'POST', body: JSON.stringify({ exam_id: exam, verified: false, ...q }) }); setText(''); onDone() } return <div className="mt-8"><h3 className="font-black"><Plus className="mr-1 inline h-4 w-4" />Manual import</h3><textarea className="input mt-2 h-48 font-mono text-xs" placeholder='{"objective_code":"1.1","question_text":"...","choices":["..."],"correct_choice":"A","explanation":"..."}' value={text} onChange={e => setText(e.target.value)} /><button className="btn mt-2" onClick={submit}>Add to review queue</button></div> }

createRoot(document.getElementById('root')).render(<Shell />)
