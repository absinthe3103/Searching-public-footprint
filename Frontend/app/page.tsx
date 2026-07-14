'use client'

import { useRef, useState, useCallback } from 'react'

/* ── Types ─────────────────────────────────────────────── */
interface DimensionScores {
  technical_competency:  number
  problem_solving:       number
  communication:         number
  career_stability:      number
  company_exposure:      number
  academic_signal:       number
  initiative:            number
  risk_indicators:       number
  role_domain_relevance: number
}

interface SourceURLs {
  github:         string | null
  linkedin:       string | null
  google_scholar: string | null
  researchgate:   string | null
  kaggle:         string | null
  devto:          string | null
  medium:         string | null
  hashnode:       string | null
}

interface EvaluateResponse {
  candidate_name:  string
  rescoring_score: number
  dimensions:      DimensionScores
  reasoning:       Record<string, string>
  source_urls:     SourceURLs
  db_id:           number
}

/* ── Constants ──────────────────────────────────────────── */
const API_URL = 'http://localhost:8000'

const DIMS = [
  { key: 'technical_competency',  label: 'Technical competency', icon: 'ti-code',           subtracted: false, primary: false },
  { key: 'problem_solving',       label: 'Problem solving',      icon: 'ti-puzzle',          subtracted: false, primary: false },
  { key: 'communication',         label: 'Communication',        icon: 'ti-message',         subtracted: false, primary: false },
  { key: 'career_stability',      label: 'Career stability',     icon: 'ti-calendar-check',  subtracted: false, primary: false },
  { key: 'company_exposure',      label: 'Company exposure',     icon: 'ti-building',        subtracted: false, primary: false },
  { key: 'academic_signal',       label: 'Academic signal',      icon: 'ti-school',          subtracted: false, primary: false },
  { key: 'initiative',            label: 'Initiative',           icon: 'ti-rocket',          subtracted: false, primary: false },
  { key: 'risk_indicators',       label: 'Risk indicators',      icon: 'ti-alert-triangle',  subtracted: true,  primary: false },
  { key: 'role_domain_relevance', label: 'Role domain relevance',icon: 'ti-target',          subtracted: false, primary: true  },
] as const

const SOURCES = [
  { key: 'github',         label: 'GitHub',       icon: 'ti-brand-github'      },
  { key: 'linkedin',       label: 'LinkedIn',     icon: 'ti-brand-linkedin'    },
  { key: 'google_scholar', label: 'Scholar',      icon: 'ti-school'            },
  { key: 'researchgate',   label: 'ResearchGate', icon: 'ti-file-text'         },
  { key: 'kaggle',         label: 'Kaggle',       icon: 'ti-chart-line'        },
  { key: 'devto',          label: 'Dev.to',       icon: 'ti-brand-deviantart'  },
  { key: 'medium',         label: 'Medium',       icon: 'ti-pencil'            },
  { key: 'hashnode',       label: 'Hashnode',     icon: 'ti-hash'              },
] as const

// Sources where the candidate can supply an exact username to improve
// search accuracy (Google Scholar / ResearchGate are still name-based,
// so they're excluded here — see Backend/database/db.py USERNAME_COLUMNS)
const USERNAME_FIELDS = [
  { key: 'github_username',   label: 'GitHub',   icon: 'ti-brand-github',   placeholder: 'e.g. octocat' },
  { key: 'linkedin_username', label: 'LinkedIn', icon: 'ti-brand-linkedin', placeholder: 'e.g. andrew-ng' },
  { key: 'kaggle_username',   label: 'Kaggle',   icon: 'ti-chart-line',     placeholder: 'e.g. andrewng' },
  { key: 'devto_username',    label: 'Dev.to',   icon: 'ti-brand-deviantart', placeholder: 'e.g. andrewng' },
  { key: 'medium_username',   label: 'Medium',   icon: 'ti-pencil',         placeholder: 'e.g. andrewng' },
  { key: 'hashnode_username', label: 'Hashnode', icon: 'ti-hash',           placeholder: 'e.g. andrewng' },
] as const

type UsernameKey = typeof USERNAME_FIELDS[number]['key']

const LOADING_STEPS = [
  'Searching public profiles...',
  'Analysing GitHub activity...',
  'Checking publications...',
  'Scoring 9 dimensions...',
]

/* ── Helpers ────────────────────────────────────────────── */
function getInitials(name: string) {
  return name.split(' ').map(w => w[0]).join('').toUpperCase().slice(0, 2)
}

function getColorClass(val: number, risk = false) {
  if (risk) return val > 60 ? 'low' : val > 30 ? 'mid' : 'good'
  return val >= 70 ? 'good' : val >= 40 ? 'mid' : 'low'
}

function getScoreColor(val: number, risk = false): string {
  const cl = getColorClass(val, risk)
  return cl === 'good' ? 'var(--green)' : cl === 'mid' ? 'var(--amber)' : 'var(--red)'
}

/* ── Radar chart (Canvas) ────────────────────────────────── */
function drawRadar(canvas: HTMLCanvasElement, scores: DimensionScores) {
  const ctx = canvas.getContext('2d')
  if (!ctx) return

  const size = canvas.width
  const cx = size / 2
  const cy = size / 2
  const r  = cx - 36
  const n  = DIMS.length

  const vals = DIMS.map(d => (scores[d.key as keyof DimensionScores] ?? 0) / 100)

  ctx.clearRect(0, 0, size, size)

  /* rings */
  ;[0.25, 0.5, 0.75, 1.0].forEach(ring => {
    ctx.beginPath()
    for (let i = 0; i < n; i++) {
      const a = (i / n) * 2 * Math.PI - Math.PI / 2
      const x = cx + r * ring * Math.cos(a)
      const y = cy + r * ring * Math.sin(a)
      i === 0 ? ctx.moveTo(x, y) : ctx.lineTo(x, y)
    }
    ctx.closePath()
    ctx.strokeStyle = 'rgba(255,255,255,0.06)'
    ctx.lineWidth = 0.5
    ctx.stroke()
  })

  /* spokes */
  for (let i = 0; i < n; i++) {
    const a = (i / n) * 2 * Math.PI - Math.PI / 2
    ctx.beginPath()
    ctx.moveTo(cx, cy)
    ctx.lineTo(cx + r * Math.cos(a), cy + r * Math.sin(a))
    ctx.strokeStyle = 'rgba(255,255,255,0.07)'
    ctx.lineWidth = 0.5
    ctx.stroke()
  }

  /* filled polygon */
  ctx.beginPath()
  vals.forEach((v, i) => {
    const a = (i / n) * 2 * Math.PI - Math.PI / 2
    const x = cx + r * v * Math.cos(a)
    const y = cy + r * v * Math.sin(a)
    i === 0 ? ctx.moveTo(x, y) : ctx.lineTo(x, y)
  })
  ctx.closePath()
  ctx.fillStyle   = 'rgba(201,168,76,0.18)'
  ctx.fill()
  ctx.strokeStyle = '#C9A84C'
  ctx.lineWidth   = 1.5
  ctx.stroke()

  /* dots */
  vals.forEach((v, i) => {
    const a = (i / n) * 2 * Math.PI - Math.PI / 2
    const x = cx + r * v * Math.cos(a)
    const y = cy + r * v * Math.sin(a)
    ctx.beginPath()
    ctx.arc(x, y, 3.5, 0, Math.PI * 2)
    ctx.fillStyle = '#E8C96A'
    ctx.fill()
  })

  /* labels */
  DIMS.forEach((d, i) => {
    const a  = (i / n) * 2 * Math.PI - Math.PI / 2
    const lx = cx + (r + 22) * Math.cos(a)
    const ly = cy + (r + 22) * Math.sin(a)
    ctx.textAlign    = 'center'
    ctx.textBaseline = 'middle'
    ctx.fillStyle    = d.primary ? '#E8C96A' : 'rgba(176,190,200,0.85)'
    ctx.font         = `${d.primary ? '500 ' : ''}10px Inter,sans-serif`
    const words = d.label.split(' ')
    if (words.length > 2) {
      ctx.fillText(words.slice(0, 2).join(' '), lx, ly - 6)
      ctx.fillText(words.slice(2).join(' '), lx, ly + 6)
    } else {
      ctx.fillText(d.label, lx, ly)
    }
  })
}

/* ══════════════════════════════════════════════════════════
   PAGE COMPONENT
══════════════════════════════════════════════════════════ */
export default function Page() {
  const [candidateName, setCandidateName]   = useState('')
  const [requirements,  setRequirements]    = useState<string[]>([])
  const [reqInput,      setReqInput]        = useState('')
  const [loading,       setLoading]         = useState(false)
  const [loadingStep,   setLoadingStep]     = useState(0)
  const [result,        setResult]          = useState<EvaluateResponse | null>(null)
  const [error,         setError]           = useState<string | null>(null)
  const [usernames,     setUsernames]       = useState<Record<UsernameKey, string>>({
    github_username: '', linkedin_username: '', kaggle_username: '',
    devto_username: '', medium_username: '', hashnode_username: '',
  })
  const [showUsernames, setShowUsernames]   = useState(false)

  const canvasRef = useRef<HTMLCanvasElement>(null)

  /* requirements */
  const addReq = useCallback(() => {
    const v = reqInput.trim()
    if (!v) return
    setRequirements(prev => [...prev, v])
    setReqInput('')
  }, [reqInput])

  const removeReq = useCallback((i: number) => {
    setRequirements(prev => prev.filter((_, idx) => idx !== i))
  }, [])

  /* evaluation */
  const runEval = useCallback(async () => {
    if (!candidateName.trim()) { alert('Enter a candidate name.'); return }
    if (requirements.length === 0) { alert('Add at least one job requirement.'); return }

    setLoading(true)
    setError(null)
    setResult(null)
    setLoadingStep(0)

    const interval = setInterval(() => {
      setLoadingStep(prev => (prev + 1) % LOADING_STEPS.length)
    }, 2200)

    try {
      // Only send usernames the user actually filled in
      const usernamePayload = Object.fromEntries(
        Object.entries(usernames)
          .filter(([, v]) => v.trim())
          .map(([k, v]) => [k, v.trim()])
      )

      const res = await fetch(`${API_URL}/evaluate`, {
        method:  'POST',
        headers: { 'Content-Type': 'application/json' },
        body:    JSON.stringify({
          candidate_name:   candidateName.trim(),
          job_requirements: requirements,
          ...usernamePayload,
        }),
      })

      if (!res.ok) {
        const err = await res.json().catch(() => ({ detail: `HTTP ${res.status}` }))
        throw new Error(err.detail ?? `HTTP ${res.status}`)
      }

      const data: EvaluateResponse = await res.json()
      setResult(data)

      /* draw radar after DOM update */
      setTimeout(() => {
        if (canvasRef.current) drawRadar(canvasRef.current, data.dimensions)
      }, 80)
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : 'Unknown error')
    } finally {
      clearInterval(interval)
      setLoading(false)
    }
  }, [candidateName, requirements, usernames])

  /* ── Render ── */
  return (
    <div style={styles.page}>

      {/* ── App shell ── */}
      <div style={styles.shell}>

        {/* Header */}
        <header style={styles.header}>
          <div style={styles.logo}>
            <div style={styles.logoIcon}>
              <i className="ti ti-user-search" aria-hidden style={{ fontSize: 18, color: 'var(--navy)' }} />
            </div>
            <div>
              <div style={{ fontSize: 15, fontWeight: 500 }}>HireSystem</div>
              <div style={{ fontSize: 10, color: 'var(--gold)', letterSpacing: '0.08em', textTransform: 'uppercase' }}>
                AI Evaluation
              </div>
            </div>
          </div>
          <div style={{ display: 'flex', gap: 8 }}>
            <span className="badge badge-gold">9 dimensions</span>
            <span className="badge badge-gold">Claude AI</span>
          </div>
        </header>

        {/* Body */}
        <div style={styles.body} className="layout-split">

          {/* ── Left panel ── */}
          <div style={styles.panelLeft} className="panel-left">

            <div className="section-label">Candidate</div>
            <div style={{ marginBottom: 20 }}>
              <label className="field-label">Full name</label>
              <input
                className="field-input"
                placeholder="e.g. Andrew Ng"
                value={candidateName}
                onChange={e => setCandidateName(e.target.value)}
              />
            </div>

            {/* Optional source usernames — improves search accuracy over
                guessing a username from the candidate's name */}
            <div style={{ marginBottom: 20 }}>
              <button
                onClick={() => setShowUsernames(v => !v)}
                style={{
                  display: 'flex', alignItems: 'center', gap: 6,
                  background: 'none', border: 'none', cursor: 'pointer',
                  padding: 0, fontSize: 11, color: 'var(--slate)',
                  width: '100%', justifyContent: 'space-between',
                }}
                aria-expanded={showUsernames}
              >
                <span style={{ display: 'flex', alignItems: 'center', gap: 5 }}>
                  <i className="ti ti-at" aria-hidden style={{ fontSize: 12 }} />
                  Source usernames (optional)
                </span>
                <i className={`ti ${showUsernames ? 'ti-chevron-up' : 'ti-chevron-down'}`} aria-hidden style={{ fontSize: 13 }} />
              </button>

              {showUsernames && (
                <div style={{ display: 'flex', flexDirection: 'column', gap: 8, marginTop: 10 }}>
                  <p style={{ fontSize: 10.5, color: 'var(--muted)', lineHeight: 1.5, marginBottom: 2 }}>
                    Exact handles help matching beat guesses from the name.
                    Google Scholar is still searched by full name.
                  </p>
                  {USERNAME_FIELDS.map(f => (
                    <div key={f.key}>
                      <label className="field-label" style={{ display: 'flex', alignItems: 'center', gap: 5 }}>
                        <i className={`ti ${f.icon}`} aria-hidden style={{ fontSize: 11 }} />
                        {f.label}
                      </label>
                      <input
                        className="field-input"
                        placeholder={f.placeholder}
                        value={usernames[f.key]}
                        onChange={e => setUsernames(prev => ({ ...prev, [f.key]: e.target.value }))}
                      />
                    </div>
                  ))}
                </div>
              )}
            </div>

            <div className="section-label">Job requirements</div>

            {/* Requirement list */}
            <div style={{ display: 'flex', flexDirection: 'column', gap: 6, marginBottom: 10 }}>
              {requirements.map((r, i) => (
                <div key={i} style={styles.reqItem}>
                  <i className="ti ti-check" aria-hidden style={{ color: 'var(--gold)', fontSize: 13, flexShrink: 0 }} />
                  <span style={{ fontSize: 12, flex: 1 }}>{r}</span>
                  <button
                    onClick={() => removeReq(i)}
                    style={styles.reqRemove}
                    aria-label={`Remove ${r}`}
                  >
                    <i className="ti ti-x" aria-hidden style={{ fontSize: 12 }} />
                  </button>
                </div>
              ))}
            </div>

            {/* Add requirement */}
            <div style={{ display: 'flex', gap: 6 }}>
              <input
                className="field-input"
                style={{ flex: 1 }}
                placeholder="Add a requirement..."
                value={reqInput}
                onChange={e => setReqInput(e.target.value)}
                onKeyDown={e => e.key === 'Enter' && addReq()}
              />
              <button className="btn btn-ghost" onClick={addReq} aria-label="Add requirement" style={{ padding: '9px 12px' }}>
                <i className="ti ti-plus" aria-hidden style={{ fontSize: 15 }} />
              </button>
            </div>

            {/* Evaluate button */}
            <button
              className="btn btn-primary"
              style={{ width: '100%', marginTop: 24 }}
              onClick={runEval}
              disabled={loading}
            >
              {loading
                ? <><span className="spinner" style={{ width: 16, height: 16, borderWidth: 2 }} />Evaluating...</>
                : <><i className="ti ti-sparkles" aria-hidden style={{ fontSize: 16 }} />Evaluate candidate</>
              }
            </button>

            {/* Leaderboard hint */}
            <a
              href={`${API_URL}/candidates`}
              target="_blank"
              rel="noreferrer"
              style={styles.leaderboardLink}
            >
              <i className="ti ti-trophy" aria-hidden style={{ fontSize: 13 }} />
              View leaderboard
            </a>
          </div>

          {/* ── Right panel ── */}
          <div style={styles.panelRight}>

            {/* Empty state */}
            {!loading && !result && !error && (
              <div style={styles.emptyState}>
                <i className="ti ti-chart-radar" aria-hidden style={{ fontSize: 44, color: 'var(--gold-dim)' }} />
                <p style={{ fontSize: 13, color: 'var(--muted)', textAlign: 'center', maxWidth: 200, lineHeight: 1.7 }}>
                  Enter a candidate name and job requirements, then run evaluation
                </p>
              </div>
            )}

            {/* Loading state */}
            {loading && (
              <div style={styles.emptyState}>
                <div className="spinner" />
                <p className="pulse" style={{ fontSize: 12, color: 'var(--slate)', letterSpacing: '0.04em' }}>
                  {LOADING_STEPS[loadingStep]}
                </p>
              </div>
            )}

            {/* Error state */}
            {error && (
              <div style={styles.emptyState}>
                <i className="ti ti-wifi-off" aria-hidden style={{ fontSize: 36, color: 'var(--red)' }} />
                <p style={{ color: 'var(--red)', fontSize: 13, textAlign: 'center' }}>{error}</p>
                <p style={{ color: 'var(--muted)', fontSize: 11, textAlign: 'center' }}>
                  Make sure the backend is running on port 8000
                </p>
              </div>
            )}

            {/* Result */}
            {result && (
              <div style={{ display: 'flex', flexDirection: 'column', gap: 20, width: '100%' }}>

                {/* Candidate header */}
                <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', gap: 12 }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
                    <div style={styles.avatar}>{getInitials(result.candidate_name)}</div>
                    <div>
                      <div style={{ fontSize: 16, fontWeight: 500 }}>{result.candidate_name}</div>
                      <div style={{ fontSize: 12, color: 'var(--slate)', marginTop: 2 }}>
                        Evaluated across {Object.keys(result.dimensions).length} dimensions · {requirements.length} requirements
                      </div>
                    </div>
                  </div>
                  <div style={styles.scorePill}>
                    <div style={{ fontSize: 28, fontWeight: 500, color: 'var(--gold2)', lineHeight: 1 }}>
                      {Math.round(result.rescoring_score)}
                    </div>
                    <div style={{ fontSize: 10, color: 'var(--gold-dim)', letterSpacing: '0.08em', textTransform: 'uppercase', marginTop: 2 }}>
                      Overall
                    </div>
                  </div>
                </div>

                {/* Radar chart */}
                <div style={{ display: 'flex', justifyContent: 'center' }}>
                  <canvas ref={canvasRef} width={280} height={280} aria-label="Radar chart of 9 dimension scores" />
                </div>

                {/* Dimension cards */}
                <div>
                  <div className="section-label">Dimension scores</div>
                  <div style={styles.dimGrid}>
                    {DIMS.map(d => {
                      const val = result.dimensions[d.key as keyof DimensionScores] ?? 0
                      const cl  = getColorClass(val, d.key === 'risk_indicators')
                      const color = getScoreColor(val, d.key === 'risk_indicators')
                      return (
                        <div
                          key={d.key}
                          style={{
                            ...styles.dimCard,
                            ...(d.primary ? styles.dimCardPrimary : {}),
                          }}
                        >
                          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 7 }}>
                            <span style={{ fontSize: 11, color: 'var(--slate2)', display: 'flex', alignItems: 'center', gap: 4 }}>
                              <i className={`ti ${d.icon}`} aria-hidden style={{ fontSize: 12 }} />
                              {d.label}
                              {d.subtracted && <span style={{ fontSize: 9, color: 'var(--muted)', marginLeft: 2 }}>(–)</span>}
                            </span>
                            <span style={{ fontSize: 13, fontWeight: 500, color }}>{val}</span>
                          </div>
                          <div className="bar-track">
                            <div className={`bar-fill ${cl}`} style={{ width: `${val}%` }} />
                          </div>
                        </div>
                      )
                    })}
                  </div>
                </div>

                {/* Source chips */}
                <div>
                  <div className="section-label">Public profiles found</div>
                  <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap' }}>
                    {SOURCES.map(s => {
                      const url = result.source_urls[s.key as keyof SourceURLs]
                      const found = !!url
                      return found ? (
                        <a
                          key={s.key}
                          href={url!}
                          target="_blank"
                          rel="noreferrer"
                          style={styles.srcChipFound}
                        >
                          <i className={`ti ${s.icon}`} aria-hidden style={{ fontSize: 12 }} />
                          {s.label}
                        </a>
                      ) : (
                        <span key={s.key} style={styles.srcChipMiss}>
                          <i className={`ti ${s.icon}`} aria-hidden style={{ fontSize: 12 }} />
                          {s.label}
                        </span>
                      )
                    })}
                  </div>
                </div>

                {/* AI reasoning */}
                <div>
                  <div className="section-label">AI reasoning</div>
                  <div style={styles.reasonBox}>
                    {DIMS.map(d => {
                      const text = result.reasoning[d.key]
                      if (!text) return null
                      return (
                        <div key={d.key} style={styles.reasonItem}>
                          <span style={{ color: 'var(--gold2)', fontSize: 11, fontWeight: 500 }}>{d.label}: </span>
                          {text}
                        </div>
                      )
                    })}
                  </div>
                </div>

              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  )
}

/* ── Inline styles ─────────────────────────────────────── */
const styles: Record<string, React.CSSProperties> = {
  page: {
    minHeight: '100vh',
    display: 'flex',
    alignItems: 'flex-start',
    justifyContent: 'center',
    padding: '32px 16px',
    background: 'var(--navy)',
  },
  shell: {
    width: '100%',
    maxWidth: 1100,
    background: 'var(--navy2)',
    border: '0.5px solid var(--gold-border)',
    borderRadius: 'var(--radius-xl)',
    overflow: 'hidden',
  },
  header: {
    background: 'var(--navy)',
    padding: '18px 28px',
    borderBottom: '0.5px solid var(--gold-border)',
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'space-between',
  },
  logo: {
    display: 'flex',
    alignItems: 'center',
    gap: 10,
  },
  logoIcon: {
    width: 34,
    height: 34,
    background: 'var(--gold)',
    borderRadius: 8,
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
  },
  body: {
    display: 'flex',
    minHeight: 600,
  },
  panelLeft: {
    width: 320,
    flexShrink: 0,
    borderRight: '0.5px solid var(--border)',
    padding: 24,
    display: 'flex',
    flexDirection: 'column',
  },
  panelRight: {
    flex: 1,
    padding: 28,
    display: 'flex',
    flexDirection: 'column',
    overflowY: 'auto',
    maxHeight: 'calc(100vh - 120px)',
  },
  emptyState: {
    flex: 1,
    display: 'flex',
    flexDirection: 'column',
    alignItems: 'center',
    justifyContent: 'center',
    gap: 14,
    minHeight: 400,
  },
  reqItem: {
    display: 'flex',
    alignItems: 'center',
    gap: 8,
    background: 'var(--navy3)',
    border: '0.5px solid var(--border)',
    borderRadius: 6,
    padding: '7px 10px',
  },
  reqRemove: {
    background: 'none',
    border: 'none',
    cursor: 'pointer',
    color: 'var(--muted)',
    display: 'flex',
    alignItems: 'center',
    padding: 2,
    borderRadius: 4,
    marginLeft: 'auto',
  },
  leaderboardLink: {
    display: 'flex',
    alignItems: 'center',
    gap: 6,
    marginTop: 12,
    fontSize: 12,
    color: 'var(--slate)',
    justifyContent: 'center',
    textDecoration: 'none',
  },
  avatar: {
    width: 44,
    height: 44,
    borderRadius: '50%',
    background: 'rgba(201,168,76,0.15)',
    border: '1.5px solid var(--gold-dim)',
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    fontSize: 15,
    fontWeight: 500,
    color: 'var(--gold2)',
    flexShrink: 0,
  },
  scorePill: {
    background: 'rgba(201,168,76,0.10)',
    border: '1.5px solid var(--gold)',
    borderRadius: 12,
    padding: '10px 20px',
    textAlign: 'center',
    flexShrink: 0,
  },
  dimGrid: {
    display: 'grid',
    gridTemplateColumns: 'repeat(auto-fit, minmax(180px, 1fr))',
    gap: 8,
  },
  dimCard: {
    background: 'var(--navy3)',
    border: '0.5px solid var(--border)',
    borderRadius: 8,
    padding: '10px 12px',
  },
  dimCardPrimary: {
    background: 'rgba(201,168,76,0.06)',
    border: '0.5px solid var(--gold-dim)',
  },
  srcChipFound: {
    display: 'inline-flex',
    alignItems: 'center',
    gap: 5,
    padding: '5px 10px',
    borderRadius: 6,
    fontSize: 11,
    background: 'var(--green-bg)',
    border: '0.5px solid var(--green-border)',
    color: 'var(--green)',
    cursor: 'pointer',
    textDecoration: 'none',
  },
  srcChipMiss: {
    display: 'inline-flex',
    alignItems: 'center',
    gap: 5,
    padding: '5px 10px',
    borderRadius: 6,
    fontSize: 11,
    background: 'var(--border2)',
    border: '0.5px solid var(--border)',
    color: 'var(--muted)',
  },
  reasonBox: {
    background: 'var(--navy3)',
    border: '0.5px solid var(--border)',
    borderRadius: 8,
    padding: 14,
    fontSize: 12,
    color: 'var(--slate2)',
    lineHeight: 1.8,
    maxHeight: 180,
    overflowY: 'auto',
  },
  reasonItem: {
    padding: '4px 0',
    borderBottom: '0.5px solid var(--border2)',
  },
}