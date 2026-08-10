'use client'

import { useRef, useState, useCallback, useEffect } from 'react'

/* ── Types ─────────────────────────────────────────────── */
interface DimensionScores {
  technical_competency: number
  problem_solving: number
  communication: number
  career_stability: number
  company_exposure: number
  academic_signal: number
  initiative: number
  risk_indicators: number
  role_domain_relevance: number
}

interface SourceURLs {
  github: string | null
  linkedin: string | null
  google_scholar: string | null
  researchgate: string | null
  kaggle: string | null
  devto: string | null
  medium: string | null
  hashnode: string | null
}

interface EvaluateResponse {
  candidate_name: string
  rescoring_score: number
  dimensions: DimensionScores
  reasoning: Record<string, string>
  source_urls: SourceURLs
  source_details?: Record<string, any>
  db_id: number
  scoring_failed?: boolean
  status?: string
  ai_summary?: string
  fit_direction?: string
  whats_changed_summary?: string
  re_engage_flag?: boolean
  original_role?: string
  possible_profiles?: Record<string, string[]>
  lifestyle_socials?: { facebook: string, instagram: string }
}

/* ── Constants ──────────────────────────────────────────── */
const API_URL = 'http://localhost:8000'

const DIMS = [
  { key: 'technical_competency', label: 'Technical competency', icon: 'ti-code', subtracted: false, primary: false },
  { key: 'problem_solving', label: 'Problem solving', icon: 'ti-puzzle', subtracted: false, primary: false },
  { key: 'communication', label: 'Communication', icon: 'ti-message', subtracted: false, primary: false },
  { key: 'career_stability', label: 'Career stability', icon: 'ti-calendar-check', subtracted: false, primary: false },
  { key: 'company_exposure', label: 'Company exposure', icon: 'ti-building', subtracted: false, primary: false },
  { key: 'academic_signal', label: 'Academic signal', icon: 'ti-school', subtracted: false, primary: false },
  { key: 'initiative', label: 'Initiative', icon: 'ti-rocket', subtracted: false, primary: false },
  { key: 'risk_indicators', label: 'Risk indicators', icon: 'ti-alert-triangle', subtracted: true, primary: false },
  { key: 'role_domain_relevance', label: 'Role domain relevance', icon: 'ti-target', subtracted: false, primary: true },
] as const

const SOURCES = [
  { key: 'github', label: 'GitHub', icon: 'ti-brand-github' },
  { key: 'linkedin', label: 'LinkedIn', icon: 'ti-brand-linkedin' },
  { key: 'google_scholar', label: 'Scholar', icon: 'ti-school' },
  { key: 'researchgate', label: 'ResearchGate', icon: 'ti-file-text' },
  { key: 'kaggle', label: 'Kaggle', icon: 'ti-chart-line' },
  { key: 'devto', label: 'Dev.to', icon: 'ti-brand-deviantart' },
  { key: 'medium', label: 'Medium', icon: 'ti-pencil' },
  { key: 'hashnode', label: 'Hashnode', icon: 'ti-hash' },
] as const

const USERNAME_FIELDS = [
  { key: 'github_username', label: 'GitHub', icon: 'ti-brand-github', placeholder: 'e.g. github.com/yourname', urlPattern: /github\.com\/([A-Za-z0-9_-]+)/ },
  { key: 'linkedin_username', label: 'LinkedIn', icon: 'ti-brand-linkedin', placeholder: 'e.g. linkedin.com/in/yourname', urlPattern: /(?:[a-z0-9\-]+\.)?linkedin\.com\/in\/([A-Za-z0-9_\-%]+)/i },
  { key: 'google_scholar_identifier', label: 'Google Scholar', icon: 'ti-school', placeholder: 'e.g. scholar.google.com/citations?user=yourname', urlPattern: /scholar\.google\.com\/citations\?user=([A-Za-z0-9_-]+)/ },
  { key: 'researchgate_identifier', label: 'ResearchGate', icon: 'ti-file-text', placeholder: 'e.g. ORCID or researchgate.net/profile/yourname', urlPattern: /researchgate\.net\/profile\/([A-Za-z0-9_.-]+)/ },
  { key: 'kaggle_username', label: 'Kaggle', icon: 'ti-chart-line', placeholder: 'e.g. kaggle.com/yourname', urlPattern: /kaggle\.com\/([A-Za-z0-9_-]+)/ },
  { key: 'devto_username', label: 'Dev.to', icon: 'ti-brand-deviantart', placeholder: 'e.g. dev.to/yourname', urlPattern: /dev\.to\/([A-Za-z0-9_-]+)/ },
  { key: 'medium_username', label: 'Medium', icon: 'ti-pencil', placeholder: 'e.g. medium.com/@yourname', urlPattern: /medium\.com\/@?([A-Za-z0-9_.-]+)/ },
  { key: 'hashnode_username', label: 'Hashnode', icon: 'ti-hash', placeholder: 'e.g. hashnode.dev/yourname', urlPattern: /hashnode\.dev\/([A-Za-z0-9_-]+)/ },
] as const

type UsernameKey = typeof USERNAME_FIELDS[number]['key']

const LOADING_STEPS = [
  'Searching public profiles...',
  'Analysing GitHub activity...',
  'Checking publications...',
  'Scoring 9 dimensions...',
]

/* ── Per-field URL extractor ────────────────────────────── */
// If the user pastes a full URL into a platform field, strip it to just the username.
function extractUsername(raw: string, urlPattern: RegExp): string {
  const trimmed = raw.trim()
  const match = trimmed.match(urlPattern)
  if (match && match[1]) {
    return match[1].split('/')[0]  // remove any trailing path segments
  }
  return trimmed  // already a plain username — return as-is
}


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
  const r = cx - 36
  const n = DIMS.length

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
  ctx.fillStyle = 'rgba(201,168,76,0.18)'
  ctx.fill()
  ctx.strokeStyle = '#C9A84C'
  ctx.lineWidth = 1.5
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
    const a = (i / n) * 2 * Math.PI - Math.PI / 2
    const lx = cx + (r + 22) * Math.cos(a)
    const ly = cy + (r + 22) * Math.sin(a)
    ctx.textAlign = 'center'
    ctx.textBaseline = 'middle'
    ctx.fillStyle = d.primary ? '#E8C96A' : 'rgba(176,190,200,0.85)'
    ctx.font = `${d.primary ? '500 ' : ''}10px Inter,sans-serif`
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
  const [view, setView] = useState<'search' | 'talent_radar'>('search')
  const [candidateName, setCandidateName] = useState('')
  const [originalRole, setOriginalRole] = useState('Back-end Developer')
  const [requirements, setRequirements] = useState<string[]>([
    'Python', 'Machine Learning', 'API Design'
  ])
  const [reqInput, setReqInput] = useState('')
  const [loading, setLoading] = useState(false)
  const [loadingStep, setLoadingStep] = useState(0)
  const [result, setResult] = useState<EvaluateResponse | null>(null)
  const [candidates, setCandidates] = useState<any[]>([])
  const [error, setError] = useState<string | null>(null)
  const [usernames, setUsernames] = useState<Record<UsernameKey, string>>({
    github_username: '', linkedin_username: '',
    google_scholar_identifier: '', researchgate_identifier: '',
    kaggle_username: '', devto_username: '', medium_username: '', hashnode_username: '',
  })
  const [showUsernames, setShowUsernames] = useState(false)
  const [fieldUrlHints, setFieldUrlHints] = useState<Record<string, boolean>>({})
  const [hasEvaluatedBefore, setHasEvaluatedBefore] = useState(false)
  const [selectedCandidateId, setSelectedCandidateId] = useState('')

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

  /* Per-field username/URL handler — strips profile URLs to plain usernames */
  const handleUsernameChange = useCallback((
    key: UsernameKey,
    raw: string,
    urlPattern: RegExp,
  ) => {
    const username = extractUsername(raw, urlPattern)
    const wasUrl = username !== raw.trim() && raw.trim().length > 0
    setUsernames(prev => ({ ...prev, [key]: username }))
    setFieldUrlHints(prev => ({ ...prev, [key]: wasUrl }))
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
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          candidate_name: candidateName.trim(),
          original_role: originalRole.trim(),
          candidate_id: hasEvaluatedBefore && selectedCandidateId ? parseInt(selectedCandidateId, 10) : undefined,
          job_requirements: requirements,
          backend: 'gemini',
          ...usernamePayload,
        }),
      })

      if (!res.ok) {
        const err = await res.json().catch(() => ({ detail: `HTTP ${res.status}` }))
        throw new Error(err.detail ?? `HTTP ${res.status}`)
      }

      const data: EvaluateResponse = await res.json()
      setResult(data)

    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : 'Unknown error')
    } finally {
      clearInterval(interval)
      setLoading(false)
    }
  }, [candidateName, requirements, usernames, originalRole, hasEvaluatedBefore, selectedCandidateId])

  // Redraw radar chart whenever the tab changes or result updates
  useEffect(() => {
    if (result && !result.scoring_failed && canvasRef.current) {
      // Small timeout to ensure canvas is fully rendered and styled before drawing
      setTimeout(() => {
        if (canvasRef.current) drawRadar(canvasRef.current, result.dimensions)
      }, 10)
    }
  }, [result, view])

  // Fetch candidates when checkbox is checked
  useEffect(() => {
    if (hasEvaluatedBefore && candidates.length === 0) {
      fetch(`${API_URL}/candidates`)
        .then(res => res.ok ? res.json() : [])
        .then(data => setCandidates(data))
        .catch(e => console.error('Failed to fetch candidates', e))
    }
  }, [hasEvaluatedBefore])

  // ── Stats Calculations for Dashboard ──
  const isGuessed = (key: string) => !!result?.possible_profiles?.[key]?.length

  const gh = !isGuessed('github') ? result?.source_details?.github : null
  const ghFound = !!(gh && gh.profile_url)
  const ghStars = gh?.contribution_activity?.total_stars ?? 0
  const ghFollowers = gh?.contribution_activity?.followers ?? 0
  const ghRepos = gh?.contribution_activity?.public_repos ?? gh?.repos?.length ?? 0
  const ghLanguages = gh?.top_languages ?? []
  const ghLangStats = gh?.language_stats ?? {}
  const ghLatestPush = gh?.latest_push ?? null
  const ghCareer = gh?.career_indicators ?? null

  const li = !isGuessed('linkedin') ? result?.source_details?.linkedin : null
  const liFound = !!(li && li.profile_url)
  const liRole = li?.current_role ?? null
  const liCompany = li?.company ?? null
  const liSummary = li?.summary ?? null

  const gs = !isGuessed('google_scholar') ? result?.source_details?.google_scholar : null
  const rg = !isGuessed('researchgate') ? result?.source_details?.researchgate : null
  const acadFound = !!((gs && gs.profile_url) || (rg && rg.profile_url))
  const citations = Number(gs?.citations ?? rg?.citations ?? 0)
  const pubs = [...(gs?.publications ?? []), ...(rg?.publications ?? [])]
  const pubCount = pubs.length
  const rawInterests = gs?.interests ?? rg?.interests ?? []
  const interests: string[] = typeof rawInterests === 'string'
    ? rawInterests.split(',').map((s: string) => s.trim()).filter(Boolean)
    : Array.isArray(rawInterests)
      ? rawInterests.map((s: any) => String(s).trim()).filter(Boolean)
      : []

  const devto = !isGuessed('devto') ? result?.source_details?.devto : null
  const medium = !isGuessed('medium') ? result?.source_details?.medium : null
  const hashnode = !isGuessed('hashnode') ? result?.source_details?.hashnode : null
  const kaggle = !isGuessed('kaggle') ? result?.source_details?.kaggle : null
  const devtoCount = devto?.articles?.length ?? 0
  const mediumCount = medium?.articles?.length ?? 0
  const hashnodeCount = hashnode?.articles?.length ?? 0
  const totalBlogs = devtoCount + mediumCount + hashnodeCount
  const blogsFound = !!((devto && devto.profile_url) || (medium && medium.profile_url) || (hashnode && hashnode.profile_url))

  const allCommunityWorks = [
    ...(devto?.articles ?? []),
    ...(medium?.articles ?? []),
    ...(hashnode?.articles ?? []),
    ...(kaggle?.writeups ?? []),
    ...(kaggle?.pinned_works ?? [])
  ]

  const kwStats = (() => {
    if (!result || !result.source_details) return { total: 0, matched: 0, percentage: 0, list: [] as { word: string; hit: boolean }[] }
    const hits: Record<string, boolean> = {}
    Object.values(result.source_details).forEach((src: any) => {
      if (src && src.keyword_hits) {
        Object.entries(src.keyword_hits).forEach(([k, v]) => {
          if (v) hits[k] = true
          else if (hits[k] === undefined) hits[k] = false
        })
      }
    })
    const list = Object.entries(hits).map(([word, hit]) => ({ word, hit }))
    const total = list.length
    const matched = list.filter(x => x.hit).length
    const percentage = total > 0 ? Math.round((matched / total) * 100) : 0
    return { total, matched, percentage, list }
  })()

  // ── Compute Overall Activity & Confidence ──
  const isRecentPush = ghLatestPush ? new Date(ghLatestPush).getTime() > Date.now() - 90 * 24 * 60 * 60 * 1000 : false
  const totalActivity = ghRepos + ghStars + pubCount + totalBlogs

  let activityLevel = 'None'
  let activityColor = 'var(--muted)'
  if (totalActivity > 30 || ghStars > 50 || citations > 30 || (totalActivity > 10 && isRecentPush)) {
    activityLevel = 'High'
    activityColor = 'var(--green)'
  } else if (totalActivity > 10 || citations > 5 || isRecentPush) {
    activityLevel = 'Medium'
    activityColor = 'var(--amber)'
  } else if (totalActivity > 0 || ghFound) {
    activityLevel = 'Low'
    activityColor = 'var(--gold2)'
  }

  const profilesFound = [ghFound, liFound, acadFound, blogsFound].filter(Boolean).length
  let confidenceLevel = 'Low'
  let confidenceColor = 'var(--red)'
  if (profilesFound >= 3 || (profilesFound >= 2 && kwStats.matched >= 3)) {
    confidenceLevel = 'High'
    confidenceColor = 'var(--green)'
  } else if (profilesFound === 2 || (profilesFound === 1 && kwStats.matched >= 1)) {
    confidenceLevel = 'Medium'
    confidenceColor = 'var(--amber)'
  } else if (profilesFound === 0) {
    confidenceLevel = 'None'
    confidenceColor = 'var(--muted)'
  }

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
          <div style={{ display: 'flex', gap: 20 }}>
            <div style={{ display: 'flex', gap: 12 }}>
              <button
                onClick={() => { setView('search'); }}
                style={{
                  background: view === 'search' && !result ? 'var(--navy4)' : 'transparent',
                  border: 'none',
                  color: view === 'search' && !result ? 'var(--gold2)' : 'var(--slate2)',
                  padding: '8px 16px',
                  borderRadius: 6,
                  cursor: 'pointer',
                  fontWeight: 500,
                  fontSize: 12
                }}
              >
                New Evaluation
              </button>
              <button
                onClick={async () => {
                  setView('talent_radar')
                  try {
                    const res = await fetch(`${API_URL}/candidates`)
                    if (res.ok) setCandidates(await res.json())
                  } catch (e) {
                    console.error('Failed to fetch candidates', e)
                  }
                }}
                style={{
                  background: view === 'talent_radar' ? 'var(--navy4)' : 'transparent',
                  border: 'none',
                  color: view === 'talent_radar' ? 'var(--gold2)' : 'var(--slate2)',
                  padding: '8px 16px',
                  borderRadius: 6,
                  cursor: 'pointer',
                  fontWeight: 500,
                  fontSize: 12
                }}
              >
                Talent Radar
              </button>
            </div>
            <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
              <span className="badge badge-gold">9 dimensions</span>
              <span className="badge badge-gold">Gemini Flash</span>
            </div>
          </div>
        </header>

        {/* Body */}
        <div style={styles.body} className="layout-split">

          {view === 'talent_radar' ? (
            <div style={{ padding: '24px 40px', width: '100%', maxWidth: 1200, margin: '0 auto', overflowY: 'auto' }}>
              <h2 style={{ fontSize: 24, fontWeight: 600, color: 'white', marginBottom: 8 }}>Talent Radar</h2>
              <p style={{ color: 'var(--slate2)', fontSize: 13, marginBottom: 32 }}>All shortlisted candidates from past sessions, grouped by current status.</p>

              <div style={{ display: 'flex', flexDirection: 'column', gap: 32 }}>
                {['Active opportunity', 'Re-engage', 'Watch', 'Faded'].map(status => {
                  const group = candidates.filter(c => c.status === status)
                  if (group.length === 0) return null

                  return (
                    <div key={status}>
                      <h3 style={{ fontSize: 15, fontWeight: 500, color: 'var(--gold2)', marginBottom: 12, borderBottom: '1px solid var(--border)', paddingBottom: 8 }}>
                        {status} <span style={{ color: 'var(--slate2)', fontSize: 12 }}>({group.length})</span>
                      </h3>
                      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(300px, 1fr))', gap: 16 }}>
                        {group.map(c => (
                          <div key={c.id} style={{ background: 'var(--navy3)', border: '1px solid var(--border)', borderRadius: 8, padding: 16 }}>
                            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: 12 }}>
                              <div>
                                <div style={{ fontWeight: 600, color: 'white', fontSize: 15 }}>{c.name}</div>
                                <div style={{ fontSize: 11, color: 'var(--slate2)', marginTop: 2 }}>{c.original_role || 'Unknown Role'}</div>
                              </div>
                              {c.re_engage_flag && (
                                <span style={{ background: 'rgba(46, 204, 113, 0.1)', color: 'var(--green)', padding: '2px 8px', borderRadius: 12, fontSize: 10, fontWeight: 600 }}>ACT NOW</span>
                              )}
                            </div>

                            <div style={{ fontSize: 12, color: 'var(--slate2)', background: 'var(--navy4)', padding: 10, borderRadius: 6, marginBottom: 12 }}>
                              {c.whats_changed_summary || 'No recent updates available.'}
                            </div>

                            <div style={{ display: 'flex', gap: 12, fontSize: 11 }}>
                              <div style={{ color: 'var(--slate)' }}>Fit: <span style={{ color: 'white', textTransform: 'capitalize' }}>{c.fit_direction || 'N/A'}</span></div>
                            </div>
                          </div>
                        ))}
                      </div>
                    </div>
                  )
                })}
                {candidates.length === 0 && (
                  <div style={{ textAlign: 'center', padding: '60px 20px', color: 'var(--slate2)' }}>
                    No candidates evaluated yet. Run an evaluation to see them here!
                  </div>
                )}
              </div>
            </div>
          ) : (
            <>
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
                      Username or Profile URL (optional)
                    </span>
                    <i className={`ti ${showUsernames ? 'ti-chevron-up' : 'ti-chevron-down'}`} aria-hidden style={{ fontSize: 13 }} />
                  </button>

                  {showUsernames && (
                    <div style={{ display: 'flex', flexDirection: 'column', gap: 8, marginTop: 10 }}>
                      <p style={{ fontSize: 10.5, color: 'var(--muted)', lineHeight: 1.5, marginBottom: 2 }}>
                        Enter a username or paste a full profile URL — both work for all platforms,
                        including Google Scholar (user ID or full URL) and ResearchGate (profile slug or full URL).
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
                            onChange={e => handleUsernameChange(f.key, e.target.value, f.urlPattern)}
                          />
                          {fieldUrlHints[f.key] && (
                            <div style={{ marginTop: 4, fontSize: 10.5, color: 'var(--green)', display: 'flex', alignItems: 'center', gap: 4 }}>
                              <i className="ti ti-circle-check" aria-hidden style={{ fontSize: 11 }} />
                              URL detected — username extracted
                            </div>
                          )}
                        </div>
                      ))}
                    </div>
                  )}
                </div>

                <div style={{ marginBottom: 20 }}>
                  <label className="field-label">Original Role Applied For</label>
                  <select
                    className="field-input"
                    value={originalRole}
                    onChange={e => setOriginalRole(e.target.value)}
                  >
                    <option value="Back-end Developer">Back-end Developer</option>
                    <option value="Front-End Developer">Front-End Developer</option>
                    <option value="Software Engineer">Software Engineer</option>
                    <option value="AI-Engineer">AI-Engineer</option>
                    <option value="Software Tester">Software Tester</option>
                  </select>
                </div>

                <div className="section-label">Job requirements</div>

                {/* Trending Suggestions */}
                <div style={{ marginBottom: 12 }}>
                  <div style={{ fontSize: 10.5, color: 'var(--slate)', marginBottom: 6 }}>Trending Requirements</div>
                  <div style={{ display: 'flex', flexWrap: 'wrap', gap: 5 }}>
                    {['Machine Learning', 'Python', 'React', 'AWS', 'Node.js', 'System Design'].map(skill => {
                      const isSelected = requirements.includes(skill)
                      return (
                        <button
                          key={skill}
                          onClick={() => {
                            if (!isSelected) setRequirements(prev => [...prev, skill])
                          }}
                          style={{
                            background: isSelected ? 'var(--gold-dim)' : 'var(--navy4)',
                            border: `0.5px solid ${isSelected ? 'var(--gold)' : 'var(--border)'}`,
                            color: isSelected ? 'var(--navy)' : 'var(--slate2)',
                            padding: '3px 8px',
                            borderRadius: 12,
                            fontSize: 10,
                            cursor: isSelected ? 'default' : 'pointer',
                            transition: 'all 0.2s',
                            display: 'flex',
                            alignItems: 'center',
                            gap: 4
                          }}
                          disabled={isSelected}
                        >
                          {skill} <i className={`ti ${isSelected ? 'ti-check' : 'ti-plus'}`} style={{ fontSize: 9 }} />
                        </button>
                      )
                    })}
                  </div>
                </div>

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

                {/* Add custom requirement */}
                <div style={{ fontSize: 10.5, color: 'var(--slate)', marginBottom: 6, marginTop: 4 }}>Other Requirements</div>
                <div style={{ display: 'flex', gap: 6 }}>
                  <input
                    className="field-input"
                    style={{ flex: 1 }}
                    placeholder="Specify other requirements..."
                    value={reqInput}
                    onChange={e => setReqInput(e.target.value)}
                    onKeyDown={e => e.key === 'Enter' && addReq()}
                  />
                  <button className="btn btn-ghost" onClick={addReq} aria-label="Add requirement" style={{ padding: '9px 12px' }}>
                    <i className="ti ti-plus" aria-hidden style={{ fontSize: 15 }} />
                  </button>
                </div>

                <div style={{ marginTop: 24, padding: '12px 14px', background: 'var(--navy3)', borderRadius: 8, border: '1px solid var(--border)' }}>
                  <label style={{ display: 'flex', alignItems: 'flex-start', gap: 10, cursor: 'pointer', fontSize: 13, color: 'var(--gold2)' }}>
                    <input
                      type="checkbox"
                      checked={hasEvaluatedBefore}
                      onChange={e => setHasEvaluatedBefore(e.target.checked)}
                      style={{ accentColor: 'var(--gold2)', width: 16, height: 16, flexShrink: 0, marginTop: 2 }}
                    />
                    <span style={{ lineHeight: 1.4 }}>Previously evaluated candidate?</span>
                  </label>

                  {hasEvaluatedBefore && (
                    <div style={{ marginTop: 12 }}>
                      <select
                        className="field-input"
                        value={selectedCandidateId}
                        onChange={e => {
                          setSelectedCandidateId(e.target.value)
                          const selected = candidates.find(c => c.id.toString() === e.target.value)
                          if (selected) {
                            setCandidateName(selected.name)
                            setOriginalRole(selected.original_role || '')
                          }
                        }}
                        style={{ width: '100%', padding: '8px 12px', fontSize: 12 }}
                      >
                        <option value="">-- Select previously evaluated candidate --</option>
                        {candidates.map(c => (
                          <option key={c.id} value={c.id}>
                            {c.name} ({c.original_role || 'Unknown Role'})
                          </option>
                        ))}
                      </select>
                    </div>
                  )}
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

                    {/* AI scoring warning banner */}
                    {result.scoring_failed && (
                      <div style={{
                        display: 'flex', alignItems: 'flex-start', gap: 10,
                        padding: '10px 14px', borderRadius: 8,
                        background: 'rgba(239,159,39,0.08)', border: '0.5px solid rgba(239,159,39,0.35)',
                      }}>
                        <i className="ti ti-alert-triangle" aria-hidden style={{ fontSize: 16, color: 'var(--amber)', marginTop: 1, flexShrink: 0 }} />
                        <div>
                          <div style={{ fontSize: 12, fontWeight: 500, color: 'var(--amber)' }}>AI scoring unavailable</div>
                          <div style={{ fontSize: 11, color: 'var(--slate)', marginTop: 2, lineHeight: 1.5 }}>
                            Public profile data was collected and is shown below. Configure your AI API key to enable dimension scoring.
                          </div>
                        </div>
                      </div>
                    )}

                    {/* Candidate header */}
                    <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', gap: 12 }}>
                      <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
                        <div style={styles.avatar}>{getInitials(result.candidate_name)}</div>
                        <div>
                          <div style={{ fontSize: 16, fontWeight: 500 }}>{result.candidate_name}</div>
                          <div style={{ fontSize: 12, color: 'var(--slate)', marginTop: 2 }}>
                            {result.scoring_failed
                              ? `Public footprint search · ${requirements.length} requirements`
                              : `Evaluated across ${Object.keys(result.dimensions).length} dimensions · ${requirements.length} requirements`
                            }
                          </div>
                        </div>
                      </div>
                      {result.scoring_failed ? (
                        <div style={{ ...styles.scorePill, borderColor: 'rgba(239,159,39,0.4)', background: 'rgba(239,159,39,0.06)' }}>
                          <div style={{ fontSize: 13, fontWeight: 500, color: 'var(--amber)', lineHeight: 1 }}>N/A</div>
                          <div style={{ fontSize: 10, color: 'rgba(239,159,39,0.6)', letterSpacing: '0.08em', textTransform: 'uppercase', marginTop: 2 }}>Score</div>
                        </div>
                      ) : (
                        <div style={styles.scorePill}>
                          <div style={{ fontSize: 28, fontWeight: 500, color: 'var(--gold2)', lineHeight: 1 }}>
                            {Math.round(result.rescoring_score)}
                          </div>
                          <div style={{ fontSize: 10, color: 'var(--gold-dim)', letterSpacing: '0.08em', textTransform: 'uppercase', marginTop: 2 }}>
                            Overall
                          </div>
                        </div>
                      )}
                    </div>

                    {/* Radar chart — only when AI scores are available */}
                    {!result.scoring_failed && (
                      <div style={{ display: 'flex', justifyContent: 'center' }}>
                        <canvas ref={canvasRef} width={280} height={280} aria-label="Radar chart of 9 dimension scores" />
                      </div>
                    )}

                    {/* Dimension cards — only when AI scores are available */}
                    {!result.scoring_failed && (
                      <div>
                        <div className="section-label">Dimension scores</div>
                        <div style={styles.dimGrid}>
                          {DIMS.map(d => {
                            const val = result.dimensions[d.key as keyof DimensionScores] ?? 0
                            const cl = getColorClass(val, d.key === 'risk_indicators')
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
                    )}

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

                    {/* Possible Accounts */}
                    <div style={{ marginTop: 24 }}>
                      <div className="section-label">Possible Accounts</div>
                      {(!result.possible_profiles || Object.keys(result.possible_profiles).length === 0) ? (
                        <div style={{ fontSize: 12, color: 'var(--slate2)', fontStyle: 'italic', padding: '4px 0' }}>
                          No possible account Found
                        </div>
                      ) : (
                        <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
                          {Object.entries(result.possible_profiles).map(([platform, urls]) => {
                            const sourceDef = SOURCES.find(s => s.key === platform)
                            const label = sourceDef ? sourceDef.label : platform.charAt(0).toUpperCase() + platform.slice(1)
                            const icon = sourceDef ? sourceDef.icon : 'ti-link'
                            return (
                              <div key={platform} style={{ background: 'var(--navy3)', padding: 12, borderRadius: 8, border: '0.5px solid var(--border)' }}>
                                <div style={{ fontSize: 12, fontWeight: 600, color: 'var(--slate2)', marginBottom: 8, display: 'flex', alignItems: 'center', gap: 6 }}>
                                  <i className={`ti ${icon}`} style={{ fontSize: 14 }} />
                                  {label}
                                </div>
                                <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
                                  {urls.map((url, i) => (
                                    <a key={i} href={url} target="_blank" rel="noreferrer" style={{ fontSize: 11, color: 'var(--gold2)', textDecoration: 'none', wordBreak: 'break-all', display: 'flex', alignItems: 'center', gap: 4 }}>
                                      <i className="ti ti-external-link" style={{ fontSize: 12 }} />
                                      {url}
                                    </a>
                                  ))}
                                </div>
                              </div>
                            )
                          })}
                        </div>
                      )}
                    </div>

                    {/* Lifestyle Social Media */}
                    {result.lifestyle_socials && (
                      <div style={{ marginTop: 24 }}>
                        <div className="section-label">Lifestyle Social Media</div>
                        <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
                          {/* Facebook Card */}
                          <div style={{ background: 'var(--navy3)', padding: 12, borderRadius: 8, border: '0.5px solid var(--border)' }}>
                            <div style={{ fontSize: 12, fontWeight: 600, color: 'var(--slate2)', marginBottom: 8, display: 'flex', alignItems: 'center', gap: 6 }}>
                              <i className="ti ti-brand-facebook" style={{ fontSize: 14 }} />
                              Facebook
                            </div>
                            <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
                              {result.lifestyle_socials.facebook?.includes('http') ? (
                                <a href={result.lifestyle_socials.facebook} target="_blank" rel="noreferrer" style={{ fontSize: 11, color: 'var(--gold2)', textDecoration: 'none', wordBreak: 'break-all', display: 'flex', alignItems: 'center', gap: 4 }}>
                                  <i className="ti ti-external-link" style={{ fontSize: 12 }} />
                                  {result.lifestyle_socials.facebook}
                                </a>
                              ) : (
                                <span style={{ fontSize: 11, color: 'var(--slate2)', fontStyle: 'italic' }}>{result.lifestyle_socials.facebook || 'no account found'}</span>
                              )}
                            </div>
                          </div>

                          {/* Instagram Card */}
                          <div style={{ background: 'var(--navy3)', padding: 12, borderRadius: 8, border: '0.5px solid var(--border)' }}>
                            <div style={{ fontSize: 12, fontWeight: 600, color: 'var(--slate2)', marginBottom: 8, display: 'flex', alignItems: 'center', gap: 6 }}>
                              <i className="ti ti-brand-instagram" style={{ fontSize: 14 }} />
                              Instagram
                            </div>
                            <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
                              {result.lifestyle_socials.instagram?.includes('http') ? (
                                <a href={result.lifestyle_socials.instagram} target="_blank" rel="noreferrer" style={{ fontSize: 11, color: 'var(--gold2)', textDecoration: 'none', wordBreak: 'break-all', display: 'flex', alignItems: 'center', gap: 4 }}>
                                  <i className="ti ti-external-link" style={{ fontSize: 12 }} />
                                  {result.lifestyle_socials.instagram}
                                </a>
                              ) : (
                                <span style={{ fontSize: 11, color: 'var(--slate2)', fontStyle: 'italic' }}>{result.lifestyle_socials.instagram || 'no account found'}</span>
                              )}
                            </div>
                          </div>
                        </div>
                      </div>
                    )}

                    {/* ── Analytical Dashboard ── */}
                    <div style={{ marginTop: 8 }}>
                      <div className="section-label" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 16 }}>
                        <span>PUBLIC FOOTPRINT ANALYTICS</span>
                        <div style={{ display: 'flex', gap: 16 }}>
                          {result.fit_direction && (
                            <div style={{ display: 'flex', alignItems: 'center', gap: 6, background: 'rgba(255,255,255,0.03)', padding: '4px 10px', borderRadius: 20, border: '0.5px solid var(--border)' }}>
                              <span style={{ fontSize: 10, color: 'var(--slate2)', textTransform: 'none', letterSpacing: 'normal' }}>Fit:</span>
                              <span style={{ fontSize: 11, fontWeight: 600, color: 'white', textTransform: 'uppercase', letterSpacing: '0.04em' }}>{result.fit_direction}</span>
                            </div>
                          )}
                          {result.status && (
                            <div style={{ display: 'flex', alignItems: 'center', gap: 6, background: 'rgba(255,255,255,0.03)', padding: '4px 10px', borderRadius: 20, border: '0.5px solid var(--border)' }}>
                              <span style={{ fontSize: 10, color: 'var(--slate2)', textTransform: 'none', letterSpacing: 'normal' }}>Status:</span>
                              <span style={{ fontSize: 11, fontWeight: 600, color: 'var(--gold2)', textTransform: 'uppercase', letterSpacing: '0.04em' }}>{result.status}</span>
                            </div>
                          )}
                          <div style={{ display: 'flex', alignItems: 'center', gap: 6, background: 'rgba(255,255,255,0.03)', padding: '4px 10px', borderRadius: 20, border: '0.5px solid var(--border)' }}>
                            <span style={{ fontSize: 10, color: 'var(--slate2)', textTransform: 'none', letterSpacing: 'normal' }}>Activity:</span>
                            <span style={{ fontSize: 11, fontWeight: 600, color: activityColor, textTransform: 'uppercase', letterSpacing: '0.04em' }}>{activityLevel}</span>
                          </div>
                          <div style={{ display: 'flex', alignItems: 'center', gap: 6, background: 'rgba(255,255,255,0.03)', padding: '4px 10px', borderRadius: 20, border: '0.5px solid var(--border)' }}>
                            <span style={{ fontSize: 10, color: 'var(--slate2)', textTransform: 'none', letterSpacing: 'normal' }}>Confidence:</span>
                            <span style={{ fontSize: 11, fontWeight: 600, color: confidenceColor, textTransform: 'uppercase', letterSpacing: '0.04em' }}>{confidenceLevel}</span>
                          </div>
                        </div>
                      </div>

                      {result.whats_changed_summary && (
                        <div style={{ marginBottom: 20 }}>
                          <div style={styles.aiSummaryBox}>
                            <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 12 }}>
                              <div style={styles.aiSummaryIcon}>
                                <i className="ti ti-sparkles" aria-hidden style={{ fontSize: 18, color: 'var(--gold2)' }} />
                              </div>
                              <div>
                                <div style={{ fontSize: 13, fontWeight: 500, color: 'var(--text)' }}>AI-generated Update Summary</div>
                                <div style={{ fontSize: 11, color: 'var(--slate)', marginTop: 1 }}>Powered by Gemini 1.5</div>
                              </div>
                            </div>
                            <div style={{ fontSize: 13, color: 'var(--slate2)', lineHeight: 1.6, padding: '8px 12px', background: 'rgba(255,255,255,0.02)', borderRadius: 8 }}>
                              {result.whats_changed_summary}
                            </div>
                          </div>
                        </div>
                      )}

                      {/* Red Flags Alert Box */}
                      {result.dimensions?.risk_indicators < 50 && (
                        <div style={{ background: 'rgba(231, 76, 60, 0.1)', border: '1px solid rgba(231, 76, 60, 0.3)', borderRadius: 8, padding: 14, marginBottom: 20 }}>
                          <div style={{ display: 'flex', alignItems: 'center', gap: 8, color: '#e74c3c', fontWeight: 600, fontSize: 13, marginBottom: 6 }}>
                            <i className="ti ti-alert-triangle" style={{ fontSize: 16 }} />
                            High Risk / Red Flags Detected
                          </div>
                          <div style={{ fontSize: 12, color: 'var(--text)', lineHeight: 1.5 }}>
                            {result.reasoning?.risk_indicators || 'Significant inconsistencies or lack of verifiable public presence detected.'}
                          </div>
                        </div>
                      )}

                      <div style={styles.dbGrid}>

                        {/* GitHub Card */}
                        <div style={styles.dbCard}>
                          <div style={styles.dbCardHeader}>
                            <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                              <i className="ti ti-brand-github" style={{ fontSize: 18, color: 'var(--gold2)' }} />
                              <span style={{ fontSize: 13, fontWeight: 600 }}>GitHub Activity</span>
                            </div>
                            {ghFound ? (
                              <span className="badge badge-green" style={{ fontSize: 9, padding: '2px 6px' }}>Active</span>
                            ) : (
                              <span className="badge" style={{ fontSize: 9, padding: '2px 6px', background: 'var(--border2)', color: 'var(--muted)' }}>Not Found</span>
                            )}
                          </div>

                          {ghFound ? (
                            <div style={{ display: 'flex', flexDirection: 'column', gap: 12, marginTop: 10 }}>
                              <div style={styles.dbStatRow}>
                                <div style={styles.dbStatCol}>
                                  <span style={styles.dbStatVal}>{ghRepos}</span>
                                  <span style={styles.dbStatLabel}>Repos</span>
                                </div>
                                <div style={styles.dbStatCol}>
                                  <span style={styles.dbStatVal}>{ghStars}</span>
                                  <span style={styles.dbStatLabel}>Stars</span>
                                </div>
                                <div style={styles.dbStatCol}>
                                  <span style={styles.dbStatVal}>{ghFollowers}</span>
                                  <span style={styles.dbStatLabel}>Followers</span>
                                </div>
                              </div>

                              {ghLanguages.length > 0 && (
                                <div>
                                  <div style={styles.dbSubLabel}>Top Languages</div>
                                  <div style={{ display: 'flex', flexDirection: 'column', gap: 6, marginTop: 8 }}>
                                    {ghLanguages.slice(0, 4).map((lang: string) => {
                                      const count = ghLangStats[lang] || 0
                                      const total = Object.values(ghLangStats).reduce((a: any, b: any) => a + b, 0) as number
                                      const pct = total > 0 ? Math.round((count / total) * 100) : 0
                                      return (
                                        <div key={lang} style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                                          <span style={{ fontSize: 11, width: 65, color: 'var(--text)', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>{lang}</span>
                                          <div style={{ flex: 1, height: 4, background: 'rgba(255,255,255,0.06)', borderRadius: 2, overflow: 'hidden' }}>
                                            <div style={{ height: '100%', width: `${pct}%`, background: 'var(--gold2)', borderRadius: 2 }} />
                                          </div>
                                          <span style={{ fontSize: 10, color: 'var(--muted)', width: 25, textAlign: 'right' }}>{pct}%</span>
                                        </div>
                                      )
                                    })}
                                  </div>
                                </div>
                              )}

                              {ghLatestPush && (
                                <div style={{ fontSize: 11, color: 'var(--slate)', display: 'flex', alignItems: 'center', gap: 4 }}>
                                  <i className="ti ti-history" style={{ fontSize: 12 }} />
                                  Latest Push: {ghLatestPush}
                                </div>
                              )}
                            </div>
                          ) : (
                            <div style={styles.dbCardEmpty}>
                              No public GitHub activity data was retrieved.
                            </div>
                          )}
                        </div>


                        {/* Career Timeline Card */}
                        {(ghCareer?.github_account_created || ghCareer?.first_commit_around) && (
                          <div style={styles.dbCard}>
                            <div style={styles.dbCardHeader}>
                              <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                                <i className="ti ti-timeline" style={{ fontSize: 18, color: 'var(--gold2)' }} />
                                <span style={{ fontSize: 13, fontWeight: 600 }}>Career Timeline</span>
                              </div>
                            </div>
                            <div style={{ display: 'flex', flexDirection: 'column', gap: 12, marginTop: 10 }}>
                              <div style={{ display: 'flex', alignItems: 'flex-start', gap: 10 }}>
                                <div style={{ width: 8, height: 8, borderRadius: 4, background: 'var(--gold2)', marginTop: 4 }} />
                                <div>
                                  <div style={{ fontSize: 12, color: 'var(--text)', fontWeight: 500 }}>Started Coding Publicly</div>
                                  <div style={{ fontSize: 11, color: 'var(--slate2)' }}>{ghCareer.github_account_created || ghCareer.first_commit_around}</div>
                                </div>
                              </div>
                              <div style={{ width: 2, height: 16, background: 'rgba(255,255,255,0.1)', marginLeft: 3, marginTop: -8, marginBottom: -8 }} />
                              <div style={{ display: 'flex', alignItems: 'flex-start', gap: 10 }}>
                                <div style={{ width: 8, height: 8, borderRadius: 4, background: 'var(--gold2)', marginTop: 4 }} />
                                <div>
                                  <div style={{ fontSize: 12, color: 'var(--text)', fontWeight: 500 }}>Estimated Tenure</div>
                                  <div style={{ fontSize: 11, color: 'var(--slate2)' }}>{ghCareer.estimated_tenure}</div>
                                </div>
                              </div>
                              <div style={{ width: 2, height: 16, background: 'rgba(255,255,255,0.1)', marginLeft: 3, marginTop: -8, marginBottom: -8 }} />
                              <div style={{ display: 'flex', alignItems: 'flex-start', gap: 10 }}>
                                <div style={{ width: 8, height: 8, borderRadius: 4, background: 'var(--green)', marginTop: 4, boxShadow: '0 0 8px var(--green)' }} />
                                <div>
                                  <div style={{ fontSize: 12, color: 'var(--text)', fontWeight: 500 }}>Latest Activity</div>
                                  <div style={{ fontSize: 11, color: 'var(--slate2)' }}>{ghLatestPush || 'Unknown'}</div>
                                </div>
                              </div>
                            </div>
                          </div>
                        )}

                        {/* Career & Role Card (LinkedIn) */}
                        <div style={styles.dbCard}>
                          <div style={styles.dbCardHeader}>
                            <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                              <i className="ti ti-briefcase" style={{ fontSize: 18, color: 'var(--gold2)' }} />
                              <span style={{ fontSize: 13, fontWeight: 600 }}>LinkedIn Profile</span>
                            </div>
                            {liFound ? (
                              <span className="badge badge-green" style={{ fontSize: 9, padding: '2px 6px' }}>Matched</span>
                            ) : (
                              <span className="badge" style={{ fontSize: 9, padding: '2px 6px', background: 'var(--border2)', color: 'var(--muted)' }}>Not Found</span>
                            )}
                          </div>

                          {liFound ? (
                            <div style={{ display: 'flex', flexDirection: 'column', gap: 10, marginTop: 10 }}>
                              <div style={{ fontSize: 13, fontWeight: 500, color: 'var(--text)' }}>
                                LinkedIn Profile Confirmed
                              </div>

                              {liSummary && (
                                <p style={{ fontSize: 11, color: 'var(--slate2)', lineHeight: 1.5, fontStyle: 'italic' }}>
                                  "{liSummary.length > 140 ? liSummary.slice(0, 140) + '...' : liSummary}"
                                </p>
                              )}

                              <div style={{ display: 'flex', flexDirection: 'column', gap: 6, background: 'linear-gradient(135deg, rgba(46, 204, 113, 0.15), rgba(46, 204, 113, 0.05))', padding: '12px 14px', borderRadius: 8, border: '1px solid rgba(46, 204, 113, 0.3)', marginTop: 4, marginBottom: 12 }}>
                                <div style={{ fontSize: 12, color: 'var(--text)', display: 'flex', alignItems: 'center', gap: 8 }}>
                                  <i className="ti ti-briefcase" style={{ color: 'var(--green)', fontSize: 14 }} />
                                  <span style={{ color: 'var(--slate2)', fontWeight: 500, width: 130 }}>Employment Status:</span>
                                  <span style={{ fontWeight: 600, color: liRole ? '#00F0FF' : 'var(--muted)', letterSpacing: '0.02em' }}>{liRole || 'Not specified'}</span>
                                </div>
                                <div style={{ fontSize: 12, color: 'var(--text)', display: 'flex', alignItems: 'center', gap: 8 }}>
                                  <i className="ti ti-building" style={{ color: 'var(--green)', fontSize: 14 }} />
                                  <span style={{ color: 'var(--slate2)', fontWeight: 500, width: 130 }}>Current Company:</span>
                                  <span style={{ fontWeight: 600, color: liCompany ? '#00F0FF' : 'var(--muted)', letterSpacing: '0.02em' }}>{liCompany || 'Not specified'}</span>
                                </div>
                              </div>

                              {li?.profile_url && (
                                <a
                                  href={li.profile_url}
                                  target="_blank"
                                  rel="noreferrer"
                                  style={{
                                    display: 'inline-flex', alignItems: 'center', gap: 4,
                                    fontSize: 11, color: 'var(--gold2)', textDecoration: 'none',
                                    marginTop: 4, fontWeight: 500,
                                  }}
                                >
                                  View Profile <i className="ti ti-external-link" style={{ fontSize: 12 }} />
                                </a>
                              )}
                            </div>
                          ) : (
                            <div style={styles.dbCardEmpty}>
                              No public LinkedIn profile data matched.
                            </div>
                          )}
                        </div>

                        {/* Academic Signal Card (Scholar + ResearchGate) */}
                        <div style={styles.dbCard}>
                          <div style={styles.dbCardHeader}>
                            <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                              <i className="ti ti-school" style={{ fontSize: 18, color: 'var(--gold2)' }} />
                              <span style={{ fontSize: 13, fontWeight: 600 }}>Academic Footprint</span>
                            </div>
                            {acadFound ? (
                              <span className="badge badge-green" style={{ fontSize: 9, padding: '2px 6px' }}>Found</span>
                            ) : (
                              <span className="badge" style={{ fontSize: 9, padding: '2px 6px', background: 'var(--border2)', color: 'var(--muted)' }}>Not Found</span>
                            )}
                          </div>

                          {acadFound ? (
                            <div style={{ display: 'flex', flexDirection: 'column', gap: 10, marginTop: 10 }}>
                              <div style={styles.dbStatRow}>
                                <div style={styles.dbStatCol}>
                                  <span style={styles.dbStatVal}>{citations}</span>
                                  <span style={styles.dbStatLabel}>Citations</span>
                                </div>
                                <div style={styles.dbStatCol}>
                                  <span style={styles.dbStatVal}>{pubCount}</span>
                                  <span style={styles.dbStatLabel}>Publications</span>
                                </div>
                              </div>

                              {interests.length > 0 && (
                                <div>
                                  <div style={styles.dbSubLabel}>Research Focus</div>
                                  <div style={{ display: 'flex', gap: 4, flexWrap: 'wrap', marginTop: 4 }}>
                                    {interests.slice(0, 3).map((item: string) => (
                                      <span key={item} style={styles.interestBadge}>
                                        {item}
                                      </span>
                                    ))}
                                  </div>
                                </div>
                              )}

                              {pubs.length > 0 && (
                                <div style={{ marginTop: 6 }}>
                                  <div style={styles.dbSubLabel}>Top Publications</div>
                                  <div style={{ display: 'flex', flexDirection: 'column', gap: 6, marginTop: 4 }}>
                                    {pubs.slice(0, 3).map((pub: any, idx: number) => {
                                      const targetUrl = pub.url || `https://scholar.google.com/scholar?q=${encodeURIComponent(pub.title || '')}`
                                      return (
                                        <a
                                          key={idx}
                                          href={targetUrl}
                                          target="_blank"
                                          rel="noreferrer"
                                          style={{
                                            fontSize: 11,
                                            color: 'var(--gold2)',
                                            textDecoration: 'underline',
                                            display: 'block',
                                            whiteSpace: 'nowrap',
                                            overflow: 'hidden',
                                            textOverflow: 'ellipsis',
                                            cursor: 'pointer'
                                          }}
                                        >
                                          <i className="ti ti-file-text" style={{ marginRight: 4 }} />
                                          {pub.title}
                                        </a>
                                      )
                                    })}
                                  </div>
                                </div>
                              )}
                            </div>
                          ) : (
                            <div style={styles.dbCardEmpty}>
                              No papers, citations or ResearchGate profile found.
                            </div>
                          )}
                        </div>

                        {/* Blogging & Writing Card */}
                        <div style={styles.dbCard}>
                          <div style={styles.dbCardHeader}>
                            <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                              <i className="ti ti-pencil" style={{ fontSize: 18, color: 'var(--gold2)' }} />
                              <span style={{ fontSize: 13, fontWeight: 600 }}>Developer Community</span>
                            </div>
                            {blogsFound || result?.source_details?.kaggle?.profile_url ? (
                              <span className="badge badge-green" style={{ fontSize: 9, padding: '2px 6px' }}>Active</span>
                            ) : (
                              <span className="badge" style={{ fontSize: 9, padding: '2px 6px', background: 'var(--border2)', color: 'var(--muted)' }}>Not Found</span>
                            )}
                          </div>

                          {(blogsFound || result?.source_details?.kaggle?.profile_url) ? (
                            <div style={{ display: 'flex', flexDirection: 'column', gap: 10, marginTop: 10 }}>
                              <div style={styles.dbStatRow}>
                                <div style={styles.dbStatCol}>
                                  <span style={styles.dbStatVal}>{totalBlogs}</span>
                                  <span style={styles.dbStatLabel}>Blog Posts</span>
                                </div>
                                <div style={styles.dbStatCol}>
                                  <span style={{ ...styles.dbStatVal, fontSize: 13, color: result?.source_details?.kaggle?.profile_url ? 'var(--green)' : 'var(--muted)', marginTop: 6, display: 'inline-block' }}>
                                    {result?.source_details?.kaggle?.profile_url ? 'Found' : 'None'}
                                  </span>
                                  <span style={styles.dbStatLabel}>Kaggle profile</span>
                                </div>
                              </div>

                              <div style={{ display: 'flex', gap: 5, flexWrap: 'wrap', marginTop: 4 }}>
                                {devtoCount > 0 && <span style={styles.blogPlatformBadge}>Dev.to ({devtoCount})</span>}
                                {mediumCount > 0 && <span style={styles.blogPlatformBadge}>Medium ({mediumCount})</span>}
                                {hashnodeCount > 0 && <span style={styles.blogPlatformBadge}>Hashnode ({hashnodeCount})</span>}
                              </div>

                              {allCommunityWorks.length > 0 && (
                                <div style={{ marginTop: 6 }}>
                                  <div style={styles.dbSubLabel}>Featured Work & Articles</div>
                                  <div style={{ display: 'flex', flexDirection: 'column', gap: 6, marginTop: 4 }}>
                                    {allCommunityWorks.slice(0, 4).map((work: any, idx: number) => {
                                      const targetUrl = work.url || `https://www.google.com/search?q=${encodeURIComponent(work.title || '')}`
                                      return (
                                        <a
                                          key={idx}
                                          href={targetUrl}
                                          target="_blank"
                                          rel="noreferrer"
                                          style={{
                                            fontSize: 11,
                                            color: 'var(--gold2)',
                                            textDecoration: 'underline',
                                            display: 'block',
                                            whiteSpace: 'nowrap',
                                            overflow: 'hidden',
                                            textOverflow: 'ellipsis',
                                            cursor: 'pointer'
                                          }}
                                        >
                                          <i className="ti ti-link" style={{ marginRight: 4 }} />
                                          {work.title}
                                        </a>
                                      )
                                    })}
                                  </div>
                                </div>
                              )}
                            </div>
                          ) : (
                            <div style={styles.dbCardEmpty}>
                              No active developer blogging or Kaggle profile found.
                            </div>
                          )}
                        </div>
                      </div>

                      {/* Keyword Alignment Banner */}
                      {kwStats.total > 0 && (
                        <div style={styles.kwAlignmentBox}>
                          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 10 }}>
                            <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                              <i className="ti ti-target" style={{ fontSize: 16, color: 'var(--gold2)' }} />
                              <span style={{ fontSize: 12.5, fontWeight: 500 }}>Job Description Keyword Relevance</span>
                            </div>
                            <span style={{ fontSize: 12, fontWeight: 600, color: 'var(--gold2)' }}>
                              {kwStats.matched} / {kwStats.total} matched ({kwStats.percentage}%)
                            </span>
                          </div>

                          <div style={{ height: 4, background: 'rgba(255,255,255,0.06)', borderRadius: 2, overflow: 'hidden', marginBottom: 12 }}>
                            <div style={{ height: '100%', width: `${kwStats.percentage}%`, background: 'var(--gold2)', borderRadius: 2, transition: 'width 1s ease-out' }} />
                          </div>

                          <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap' }}>
                            {kwStats.list.map(kw => (
                              <span
                                key={kw.word}
                                style={{
                                  ...styles.kwChip,
                                  ...(kw.hit ? styles.kwChipHit : styles.kwChipMiss)
                                }}
                              >
                                <i className={`ti ${kw.hit ? 'ti-circle-check' : 'ti-circle-x'}`} aria-hidden style={{ fontSize: 11 }} />
                                {kw.word}
                              </span>
                            ))}
                          </div>
                        </div>
                      )}
                    </div>

                    {/* AI reasoning */}
                    {result.reasoning && (
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
                    )}

                    {/* ── AI Summary (placeholder — backend TBD) ── */}
                    <div>
                      <div className="section-label">AI Summary</div>

                      {/* Strengths and Weaknesses */}
                      {((result.top_strengths && result.top_strengths.length > 0) || (result.top_weaknesses && result.top_weaknesses.length > 0)) && (
                        <div style={{ display: 'flex', gap: 20, marginBottom: 16 }}>
                          {result.top_strengths && result.top_strengths.length > 0 && (
                            <div style={{ flex: 1, background: 'rgba(46, 204, 113, 0.05)', border: '1px solid rgba(46, 204, 113, 0.2)', borderRadius: 8, padding: 12 }}>
                              <div style={{ fontSize: 12, fontWeight: 600, color: 'var(--green)', marginBottom: 8, display: 'flex', alignItems: 'center', gap: 6 }}>
                                <i className="ti ti-thumb-up" /> Top Strengths
                              </div>
                              <ul style={{ margin: 0, paddingLeft: 20, fontSize: 12, color: 'var(--text)', lineHeight: 1.6 }}>
                                {result.top_strengths.map((s, i) => <li key={i}>{s}</li>)}
                              </ul>
                            </div>
                          )}
                          {result.top_weaknesses && result.top_weaknesses.length > 0 && (
                            <div style={{ flex: 1, background: 'rgba(231, 76, 60, 0.05)', border: '1px solid rgba(231, 76, 60, 0.2)', borderRadius: 8, padding: 12 }}>
                              <div style={{ fontSize: 12, fontWeight: 600, color: '#e74c3c', marginBottom: 8, display: 'flex', alignItems: 'center', gap: 6 }}>
                                <i className="ti ti-thumb-down" /> Weaknesses / Concerns
                              </div>
                              <ul style={{ margin: 0, paddingLeft: 20, fontSize: 12, color: 'var(--text)', lineHeight: 1.6 }}>
                                {result.top_weaknesses.map((w, i) => <li key={i}>{w}</li>)}
                              </ul>
                            </div>
                          )}
                        </div>
                      )}

                      <div style={styles.aiSummaryBox}>
                        <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 12 }}>
                          <div style={styles.aiSummaryIcon}>
                            <i className="ti ti-robot" aria-hidden style={{ fontSize: 18, color: 'var(--gold2)' }} />
                          </div>
                          <div>
                            <div style={{ fontSize: 13, fontWeight: 500, color: 'var(--text)' }}>AI-generated Candidate Summary</div>
                            <div style={{ fontSize: 11, color: 'var(--slate)', marginTop: 1 }}>Powered by your chosen AI model</div>
                          </div>
                          <span className="badge" style={{ marginLeft: 'auto', fontSize: 9, padding: '2px 8px', background: 'rgba(201,168,76,0.08)', border: '0.5px solid var(--gold-dim)', color: 'var(--gold-dim)' }}>Coming soon</span>
                        </div>
                        <div style={styles.aiSummaryPlaceholder}>
                          {result.ai_summary ? (
                            <p style={{ fontSize: 13, color: 'var(--text)', lineHeight: 1.6, whiteSpace: 'pre-line', textAlign: 'left' }}>
                              {result.ai_summary}
                            </p>
                          ) : (
                            <>
                              <i className="ti ti-sparkles" aria-hidden style={{ fontSize: 28, color: 'var(--gold-dim)', marginBottom: 8 }} />
                              <p style={{ fontSize: 12, color: 'var(--muted)', textAlign: 'center', lineHeight: 1.7, maxWidth: 280 }}>
                                A concise natural-language summary of this candidate's public footprint will appear here once an AI model is configured.
                              </p>
                            </>
                          )}
                        </div>
                      </div>
                    </div>
                  </div>
                )}
              </div>
            </>
          )}
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
  dbGrid: {
    display: 'grid',
    gridTemplateColumns: 'repeat(auto-fit, minmax(230px, 1fr))',
    gap: '12px',
    marginBottom: '16px',
  },
  dbCard: {
    background: 'var(--navy3)',
    border: '0.5px solid var(--border)',
    borderRadius: '10px',
    padding: '14px',
    display: 'flex',
    flexDirection: 'column',
    justifyContent: 'space-between',
    minHeight: '140px',
  },
  dbCardHeader: {
    display: 'flex',
    justifyContent: 'space-between',
    alignItems: 'center',
    borderBottom: '0.5px solid var(--border2)',
    paddingBottom: '8px',
    marginBottom: '4px',
  },
  dbStatRow: {
    display: 'flex',
    justifyContent: 'space-around',
    alignItems: 'center',
    textAlign: 'center',
    background: 'rgba(255,255,255,0.02)',
    borderRadius: '6px',
    padding: '6px 0',
  },
  dbStatCol: {
    display: 'flex',
    flexDirection: 'column',
    alignItems: 'center',
  },
  dbStatVal: {
    fontSize: '18px',
    fontWeight: '600',
    color: 'var(--gold2)',
    lineHeight: '1.2',
  },
  dbStatLabel: {
    fontSize: '9.5px',
    color: 'var(--slate)',
    textTransform: 'uppercase',
    letterSpacing: '0.04em',
    marginTop: '2px',
  },
  dbSubLabel: {
    fontSize: '9.5px',
    color: 'var(--slate)',
    textTransform: 'uppercase',
    letterSpacing: '0.04em',
    marginBottom: '4px',
  },
  langBadge: {
    fontSize: '9.5px',
    background: 'var(--navy4)',
    border: '0.5px solid var(--border)',
    color: 'var(--slate2)',
    padding: '2px 6px',
    borderRadius: '4px',
  },
  interestBadge: {
    fontSize: '9.5px',
    background: 'rgba(201, 168, 76, 0.08)',
    border: '0.5px solid var(--gold-border)',
    color: 'var(--gold2)',
    padding: '2px 6px',
    borderRadius: '4px',
  },
  blogPlatformBadge: {
    fontSize: '9.5px',
    background: 'var(--border2)',
    border: '0.5px solid var(--border)',
    color: 'var(--slate2)',
    padding: '2px 6px',
    borderRadius: '4px',
  },
  dbCardEmpty: {
    fontSize: '11px',
    color: 'var(--muted)',
    textAlign: 'center',
    padding: '20px 10px',
    fontStyle: 'italic',
    flex: 1,
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
  },
  kwAlignmentBox: {
    background: 'var(--navy3)',
    border: '0.5px solid var(--border)',
    borderRadius: '10px',
    padding: '14px',
    marginBottom: '16px',
  },
  kwChip: {
    display: 'inline-flex',
    alignItems: 'center',
    gap: '4px',
    fontSize: '10.5px',
    padding: '3px 8px',
    borderRadius: '5px',
  },
  kwChipHit: {
    background: 'var(--green-bg)',
    border: '0.5px solid var(--green-border)',
    color: 'var(--green)',
  },
  kwChipMiss: {
    background: 'rgba(255,255,255,0.02)',
    border: '0.5px solid var(--border)',
    color: 'var(--muted)',
  },
  aiSummaryBox: {
    background: 'var(--navy3)',
    border: '0.5px solid var(--border)',
    borderRadius: '10px',
    padding: '16px',
  },
  aiSummaryIcon: {
    width: 36,
    height: 36,
    background: 'rgba(201,168,76,0.10)',
    border: '0.5px solid var(--gold-border)',
    borderRadius: 8,
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    flexShrink: 0,
  },
  aiSummaryPlaceholder: {
    display: 'flex',
    flexDirection: 'column',
    alignItems: 'center',
    justifyContent: 'center',
    padding: '24px 16px',
    borderRadius: 8,
    background: 'rgba(255,255,255,0.02)',
    border: '0.5px dashed var(--border)',
    minHeight: 110,
  },
}