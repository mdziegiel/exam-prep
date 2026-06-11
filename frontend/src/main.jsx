import React, { useEffect, useMemo, useState } from 'react'
import { createRoot } from 'react-dom/client'
import { AlertTriangle, BarChart3, BookOpen, CheckCircle2, Clock, Flag, History, Plus, RefreshCw, ShieldCheck, Trophy } from 'lucide-react'
import './index.css'

const API = '/api'
const api = async (path, options={}) => {
  const res = await fetch(`${API}${path}`, { headers: { 'Content-Type': 'application/json' }, ...options })
  if (!res.ok) throw new Error(await res.text())
  return res.json()
}
const fmtTime = s => `${Math.floor((s||0)/60)}m ${Math.floor((s||0)%60)}s`

function Shell() {
  const [page, setPage] = useState('dashboard')
  const [exams, setExams] = useState([])
  const [exam, setExam] = useState('MD-102')
  const [refresh, setRefresh] = useState(0)
  useEffect(() => { api('/exams').then(setExams).catch(console.error) }, [refresh])
  const current = exams.find(e => e.id === exam) || exams[0]
  useEffect(() => { if (!exam && exams[0]) setExam(exams[0].id) }, [exams])
  return <div className="min-h-screen">
    <header className="sticky top-0 z-20 border-b border-white/10 bg-ink/80 backdrop-blur-xl">
      <div className="mx-auto flex max-w-7xl items-center justify-between px-6 py-4">
        <div><h1 className="text-2xl font-black tracking-tight">IT Exam Prep</h1><p className="text-sm text-slate-400">Self-hosted certification training engine</p></div>
        <nav className="flex gap-2">
          {[['dashboard','Dashboard',BookOpen],['history','History',History],['admin','Admin',ShieldCheck]].map(([id,label,Icon]) => <button key={id} onClick={()=>setPage(id)} className={`btn ${page===id?'btn-primary':''}`}><Icon className="mr-2 inline h-4 w-4"/>{label}</button>)}
        </nav>
      </div>
    </header>
    <main className="mx-auto max-w-7xl px-6 py-8">
      {page === 'dashboard' && <Dashboard exams={exams} exam={exam} setExam={setExam} current={current} setPage={setPage}/>} 
      {page === 'practice' && <ExamSession exam={exam} mode="practice" onDone={()=>{setRefresh(x=>x+1);setPage('dashboard')}}/>}
      {page === 'timed' && <ExamSession exam={exam} mode="timed" onDone={()=>{setRefresh(x=>x+1);setPage('history')}}/>}
      {page === 'history' && <HistoryPage exams={exams}/>} 
      {page === 'admin' && <AdminPage exams={exams}/>} 
    </main>
  </div>
}

function Dashboard({exams, exam, setExam, current, setPage}) {
  const [progress, setProgress] = useState([])
  useEffect(()=>{ if(exam) api(`/exams/${exam}/progress`).then(setProgress).catch(console.error)}, [exam])
  return <div className="grid gap-6 lg:grid-cols-[1fr_360px]">
    <section className="space-y-6">
      <div className="grid gap-4 md:grid-cols-3">{exams.map(e => <button key={e.id} onClick={()=>setExam(e.id)} className={`card p-5 text-left hover:border-emerald-400/70 ${exam===e.id?'border-emerald-400 bg-emerald-950/30':''}`}>
        <div className="text-sm font-bold text-cyan">{e.id}</div><div className="mt-2 text-xl font-black">{e.name}</div><div className="mt-3 text-sm text-slate-400">{e.question_count} active questions</div>
        <div className="mt-4 h-2 rounded-full bg-slate-800"><div className="h-2 rounded-full bg-emerald-400" style={{width:`${e.percent_mastered}%`}}/></div><div className="mt-2 text-xs text-slate-400">{e.percent_mastered}% mastered</div>
      </button>)}</div>
      <div className="card p-6"><h2 className="text-2xl font-black">{current?.id} readiness</h2><p className="mt-2 text-slate-400">{current?.description}</p>
        <div className="mt-6 grid gap-4 md:grid-cols-3"><Metric icon={Trophy} label="Mastered" value={`${current?.percent_mastered||0}%`}/><Metric icon={Clock} label="Time spent" value={fmtTime(current?.time_spent_seconds)}/><Metric icon={CheckCircle2} label="Passing score" value={`${current?.passing_score||70}%`}/></div>
        <div className="mt-6 flex gap-3"><button onClick={()=>setPage('practice')} className="btn btn-primary">Start practice</button><button onClick={()=>setPage('timed')} className="btn">Timed exam</button></div>
      </div>
      <div className="card p-6"><h3 className="text-xl font-black">Objective breakdown</h3><div className="mt-4 space-y-3">{progress.map(p => <div key={p.code}><div className="mb-1 flex justify-between text-sm"><span>{p.code} · {p.title}</span><span>{Math.round((p.avg_mastery||0)*100)}%</span></div><div className="h-2 rounded-full bg-slate-800"><div className="h-2 rounded-full bg-cyan" style={{width:`${Math.round((p.avg_mastery||0)*100)}%`}}/></div></div>)}</div></div>
    </section>
    <aside className="card h-fit p-6"><h3 className="text-xl font-black">Weak areas</h3><p className="mt-2 text-sm text-slate-400">Prioritized by lowest mastery. The spaced repetition queue feeds these sooner because pain is educational.</p><div className="mt-4 space-y-3">{[...progress].sort((a,b)=>(a.avg_mastery||0)-(b.avg_mastery||0)).slice(0,5).map(p=><div className="rounded-xl bg-slate-950/60 p-3" key={p.code}><div className="font-semibold">{p.code}</div><div className="text-sm text-slate-400">{p.title}</div></div>)}</div></aside>
  </div>
}
function Metric({icon:Icon,label,value}) { return <div className="rounded-2xl bg-slate-950/70 p-4"><Icon className="h-5 w-5 text-emerald-300"/><div className="mt-2 text-2xl font-black">{value}</div><div className="text-sm text-slate-400">{label}</div></div> }

function ExamSession({exam, mode, onDone}) {
  const [questions, setQuestions] = useState([]), [idx, setIdx] = useState(0), [answered, setAnswered] = useState(null), [answers, setAnswers] = useState([]), [start] = useState(Date.now()), [seconds, setSeconds] = useState(90*60), [result, setResult] = useState(null)
  useEffect(()=>{ api(`/exams/${exam}/queue?limit=${mode==='timed'?60:20}&mode=${mode}`).then(setQuestions).catch(console.error)}, [exam,mode])
  useEffect(()=>{ if(mode!=='timed') return; const t=setInterval(()=>setSeconds(s=>Math.max(0,s-1)),1000); return ()=>clearInterval(t)}, [mode])
  const q = questions[idx]
  async function choose(choice){ if(answered) return; const res = await api('/answer',{method:'POST',body:JSON.stringify({question_id:q.id,selected_choice:choice,elapsed_seconds:Math.round((Date.now()-start)/1000)})}); setAnswered(res); setAnswers(a=>[...a,{question_id:q.id,selected_choice:choice,elapsed_seconds:5}]) }
  async function finish(){ const finalAnswers = answered && !answers.find(a=>a.question_id===answered.id) ? [...answers,{question_id:answered.id,selected_choice:answered.selected_choice,elapsed_seconds:5}] : answers; const res = await api('/attempts',{method:'POST',body:JSON.stringify({exam_id:exam,mode,answers:finalAnswers,time_taken_seconds:Math.round((Date.now()-start)/1000)})}); setResult(res) }
  if(result) return <Results result={result} onDone={onDone}/>
  if(!q) return <div className="card p-8">Loading exam queue.</div>
  const pct = Math.round(((idx+1)/questions.length)*100)
  return <div className="card p-6"><div className="mb-6 flex items-center justify-between"><div><div className="text-sm text-cyan">{exam} · {mode.toUpperCase()}</div><h2 className="text-2xl font-black">Question {idx+1} / {questions.length}</h2></div><div className="flex items-center gap-3"><button className="btn" onClick={()=>api(`/flag/${q.id}`,{method:'POST'})}><Flag className="inline h-4 w-4"/> Flag</button>{mode==='timed'&&<div className="rounded-xl bg-slate-950 px-4 py-2 font-mono">{Math.floor(seconds/60)}:{String(seconds%60).padStart(2,'0')}</div>}</div></div><div className="mb-6 h-2 rounded-full bg-slate-800"><div className="h-2 rounded-full bg-emerald-400" style={{width:`${pct}%`}}/></div><p className="text-xl leading-relaxed">{q.question_text}</p><div className="mt-6 grid gap-3">{q.choices.map(c=>{ const hit=answered && c.key===answered.correct_choice, miss=answered && c.key===answered.selected_choice && !answered.is_correct; return <button key={c.key} onClick={()=>choose(c.key)} className={`rounded-2xl border p-4 text-left transition ${hit?'border-emerald-400 bg-emerald-500/20':miss?'border-red-400 bg-red-500/20':'border-white/10 bg-slate-950/70 hover:border-cyan'}`}><b>{c.key}.</b> {c.text}</button>})}</div>{answered&&<div className="mt-6 rounded-2xl border border-white/10 bg-slate-950/80 p-5"><div className={`font-black ${answered.is_correct?'text-emerald-300':'text-red-300'}`}>{answered.is_correct?'Correct':'Wrong'} · Answer {answered.correct_choice}</div><p className="mt-2 text-slate-300">{answered.explanation}</p><p className="mt-2 text-sm text-cyan">Objective: {answered.objective_code} · {answered.objective_title}</p><button className="btn btn-primary mt-4" onClick={()=>{ if(idx+1>=questions.length) finish(); else {setIdx(i=>i+1); setAnswered(null)} }}>{idx+1>=questions.length?'Finish':'Next question'}</button></div>}</div>
}

function Results({result,onDone}) { const rows = Object.entries(result.breakdown||{}); return <div className="card p-8"><div className="flex items-start justify-between gap-6"><div><div className={`text-sm font-black ${result.passed?'text-emerald-300':'text-red-300'}`}>{result.passed?'PASS':'FAIL'}</div><h2 className="mt-2 text-5xl font-black">{result.score}%</h2><p className="mt-2 text-slate-400">{result.correct} correct out of {result.total}. Passing score is 70%.</p></div><Trophy className="h-16 w-16 text-emerald-300"/></div><h3 className="mt-8 text-xl font-black">Objective breakdown</h3><div className="mt-4 space-y-3">{rows.map(([code,b])=>{ const pct=Math.round((b.correct/b.total)*100); return <div key={code}><div className="mb-1 flex justify-between text-sm"><span>{code} · {b.title}</span><span>{pct}%</span></div><div className="h-2 rounded-full bg-slate-800"><div className={`h-2 rounded-full ${pct>=70?'bg-emerald-400':'bg-red-400'}`} style={{width:`${pct}%`}}/></div></div>})}</div><div className="mt-8 rounded-2xl bg-slate-950/70 p-4"><div className="font-black">Weakest areas</div><p className="mt-2 text-sm text-slate-400">{rows.sort((a,b)=>(a[1].correct/a[1].total)-(b[1].correct/b[1].total)).slice(0,3).map(([c,b])=>`${c} ${b.title}`).join(' · ') || 'No weak areas in this attempt.'}</p></div><button className="btn btn-primary mt-6" onClick={onDone}>Back to dashboard</button></div> }

function HistoryPage(){ const [rows,setRows]=useState([]); useEffect(()=>{api('/attempts').then(setRows)},[]); return <div className="card p-6"><h2 className="text-2xl font-black">Attempt history</h2><div className="mt-4 overflow-auto scrollbar"><table className="w-full text-left"><thead className="text-slate-400"><tr><th>Date</th><th>Exam</th><th>Mode</th><th>Score</th><th>Result</th><th>Time</th></tr></thead><tbody>{rows.map(r=><tr className="border-t border-white/10" key={r.id}><td className="py-3">{new Date(r.created_at).toLocaleString()}</td><td>{r.exam_id}</td><td>{r.mode}</td><td>{r.score}%</td><td className={r.passed?'text-emerald-300':'text-red-300'}>{r.passed?'PASS':'FAIL'}</td><td>{fmtTime(r.time_taken_seconds)}</td></tr>)}</tbody></table></div></div> }

function AdminPage({exams}){ const [exam,setExam]=useState('MD-102'), [queue,setQueue]=useState([]), [runs,setRuns]=useState([]), [msg,setMsg]=useState(''); const load=()=>{api('/admin/review').then(setQueue);api('/admin/refresh-runs').then(setRuns)}; useEffect(load,[]); async function refresh(source){setMsg('Running refresh. If Claude key is absent, LLM generation will be skipped.'); const r=await api('/admin/refresh',{method:'POST',body:JSON.stringify({exam_id:exam,source})}); setMsg(`${r.status}: imported ${r.imported}, skipped ${r.skipped}. ${r.messages.join('; ')}`); load()} async function act(id,action){await api(`/admin/review/${id}`,{method:'POST',body:JSON.stringify({action})});load()} return <div className="grid gap-6 lg:grid-cols-[360px_1fr]"><aside className="card p-6"><h2 className="text-2xl font-black">Admin</h2><label className="mt-4 block text-sm text-slate-400">Exam</label><select className="input mt-1" value={exam} onChange={e=>setExam(e.target.value)}>{exams.map(e=><option key={e.id}>{e.id}</option>)}</select><div className="mt-4 grid gap-2"><button className="btn btn-primary" onClick={()=>refresh('all')}><RefreshCw className="mr-2 inline h-4 w-4"/>Check for new questions</button><button className="btn" onClick={()=>refresh('llm')}>Claude generation only</button><button className="btn" onClick={()=>refresh('scraper')}>Scraper only</button></div><p className="mt-4 text-sm text-slate-400">{msg}</p><ManualForm exam={exam} onDone={load}/></aside><section className="card p-6"><h3 className="text-xl font-black">Review queue</h3><div className="mt-4 max-h-[620px] space-y-4 overflow-auto pr-2 scrollbar">{queue.map(q=><div className="rounded-2xl bg-slate-950/70 p-4" key={q.id}><div className="text-xs text-cyan">{q.exam_id} · {q.objective_code} · {q.source}</div><p className="mt-2 font-semibold">{q.question_text}</p><p className="mt-2 text-sm text-slate-400">Answer {q.correct_choice}: {q.explanation}</p><div className="mt-3 flex gap-2"><button className="btn btn-primary" onClick={()=>act(q.id,'approve')}>Approve</button><button className="btn btn-danger" onClick={()=>act(q.id,'reject')}>Reject</button></div></div>)}</div><h3 className="mt-8 text-xl font-black">Refresh history</h3><div className="mt-3 space-y-2 text-sm text-slate-400">{runs.slice(0,6).map(r=><div key={r.id}>{r.created_at} · {r.exam_id} · {r.source} · imported {r.imported} · {r.message}</div>)}</div></section></div>}
function ManualForm({exam,onDone}){ const [text,setText]=useState(''); async function submit(){ let q; try{q=JSON.parse(text)}catch{alert('Paste valid JSON. Satan accepts strict syntax.');return} await api('/admin/questions',{method:'POST',body:JSON.stringify({exam_id:exam,verified:false,...q})}); setText(''); onDone()} return <div className="mt-8"><h3 className="font-black"><Plus className="mr-1 inline h-4 w-4"/>Manual import</h3><textarea className="input mt-2 h-48 font-mono text-xs" placeholder='{"objective_code":"1.1","question_text":"...","choices":["..."],"correct_choice":"A","explanation":"..."}' value={text} onChange={e=>setText(e.target.value)}/><button className="btn mt-2" onClick={submit}>Add to review queue</button></div> }

createRoot(document.getElementById('root')).render(<Shell />)
