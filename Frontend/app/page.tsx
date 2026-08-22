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
  // Marketing
  instagram?: string | null
  tiktok?: string | null
  meta_ad_library?: string | null
  similarweb?: string | null
  // HR
  shrm?: string | null
  cipd?: string | null
  glassdoor?: string | null
  ssm_acra?: string | null
  // Design
  behance?: string | null
  dribbble?: string | null
  // Finance
  sc_mq?: string | null
}

interface EvaluateResponse {
  candidate_name: string
  rescoring_score: number
  dimensions: DimensionScores
  culture_fit_dimensions?: string[]
  reasoning: Record<string, string>
  source_urls: SourceURLs
  source_details?: Record<string, any>
  db_id: number
  scoring_failed?: boolean
  status?: string
  fit_direction?: string
  whats_changed_summary?: string
  re_engage_flag?: boolean
  executive_summary?: string
  original_role?: string
  original_tier?: string
  university?: string
  summary_profile?: string
}

interface PreferredUniversity {
  id: number
  name: string
  created_at: string
}

interface TalentRadarCandidate {
  id: number
  name: string
  university?: string | null
  culture_fit_dimensions?: string[]
  university_match?: boolean
  matched_culture_dimensions?: string[]
  preference_match?: boolean
  [key: string]: any
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

// Full source list from V1 (IT + Marketing + HR + Design + Finance)
const SOURCES = [
  { key: 'github',          label: 'GitHub',         icon: 'ti-brand-github' },
  { key: 'linkedin',        label: 'LinkedIn',       icon: 'ti-brand-linkedin' },
  { key: 'google_scholar',  label: 'Scholar',        icon: 'ti-school' },
  { key: 'researchgate',    label: 'ResearchGate',   icon: 'ti-file-text' },
  { key: 'kaggle',          label: 'Kaggle',         icon: 'ti-chart-line' },
  { key: 'devto',           label: 'Dev.to',         icon: 'ti-brand-deviantart' },
  { key: 'medium',          label: 'Medium',         icon: 'ti-pencil' },
  { key: 'hashnode',        label: 'Hashnode',       icon: 'ti-hash' },
  { key: 'instagram',       label: 'Instagram',      icon: 'ti-brand-instagram' },
  { key: 'tiktok',          label: 'TikTok',         icon: 'ti-brand-tiktok' },
  { key: 'meta_ad_library', label: 'Meta Ads',       icon: 'ti-ad' },
  { key: 'similarweb',      label: 'Similarweb',     icon: 'ti-chart-bar' },
  { key: 'shrm',            label: 'SHRM',           icon: 'ti-certificate' },
  { key: 'cipd',            label: 'CIPD',           icon: 'ti-certificate-2' },
  { key: 'glassdoor',       label: 'Glassdoor',      icon: 'ti-star' },
  { key: 'ssm_acra',        label: 'SSM/ACRA',       icon: 'ti-building-bank' },
  { key: 'behance',         label: 'Behance',        icon: 'ti-brand-behance' },
  { key: 'dribbble',        label: 'Dribbble',       icon: 'ti-brand-dribbble' },
  { key: 'sc_mq',           label: 'Finance Lic.',   icon: 'ti-license' },
]

// Must match Backend/database/db.py CULTURE_DIMENSIONS exactly (same keys)
const CULTURE_DIMENSIONS = [
  { key: 'innovation_risk_taking', label: 'Innovation & Risk Taking' },
  { key: 'attention_to_detail',    label: 'Attention to Detail' },
  { key: 'outcome_orientation',    label: 'Outcome Orientation' },
  { key: 'people_orientation',     label: 'People Orientation' },
  { key: 'team_orientation',       label: 'Team Orientation' },
  { key: 'aggressiveness',         label: 'Aggressiveness' },
  { key: 'stability',              label: 'Stability' },
] as const



const USERNAME_FIELDS = [
  { key: 'github_username',           label: 'GitHub',         icon: 'ti-brand-github',     placeholder: 'e.g. github.com/yourname',                         urlPattern: /github\.com\/([A-Za-z0-9_-]+)/ },
  { key: 'linkedin_username',         label: 'LinkedIn',       icon: 'ti-brand-linkedin',   placeholder: 'e.g. linkedin.com/in/yourname',                     urlPattern: /(?:[a-z0-9\-]+\.)?linkedin\.com\/in\/([A-Za-z0-9_\-%]+)/i },
  { key: 'google_scholar_identifier', label: 'Google Scholar', icon: 'ti-school',           placeholder: 'e.g. scholar.google.com/citations?user=yourname',   urlPattern: /scholar\.google\.com\/citations\?user=([A-Za-z0-9_-]+)/ },
  { key: 'researchgate_identifier',   label: 'ResearchGate',   icon: 'ti-file-text',        placeholder: 'e.g. ORCID or researchgate.net/profile/yourname',   urlPattern: /researchgate\.net\/profile\/([A-Za-z0-9_.-]+)/ },
  { key: 'kaggle_username',           label: 'Kaggle',         icon: 'ti-chart-line',       placeholder: 'e.g. kaggle.com/yourname',                          urlPattern: /kaggle\.com\/([A-Za-z0-9_-]+)/ },
  { key: 'devto_username',            label: 'Dev.to',         icon: 'ti-brand-deviantart', placeholder: 'e.g. dev.to/yourname',                              urlPattern: /dev\.to\/([A-Za-z0-9_-]+)/ },
  { key: 'medium_username',           label: 'Medium',         icon: 'ti-pencil',           placeholder: 'e.g. medium.com/@yourname',                         urlPattern: /medium\.com\/@?([A-Za-z0-9_.-]+)/ },
  { key: 'hashnode_username',         label: 'Hashnode',       icon: 'ti-hash',             placeholder: 'e.g. hashnode.dev/yourname',                        urlPattern: /hashnode\.dev\/([A-Za-z0-9_-]+)/ },
] as const

type UsernameKey = typeof USERNAME_FIELDS[number]['key']

const LOADING_STEPS = [
  'Searching public profiles...',
  'Analysing GitHub activity...',
  'Checking publications...',
  'Scoring 9 dimensions...',
]

/* ── Per-field URL extractor ────────────────────────────── */
function extractUsername(raw: string, urlPattern: RegExp): string {
  const trimmed = raw.trim()
  const match = trimmed.match(urlPattern)
  if (match && match[1]) return match[1].split('/')[0]
  return trimmed
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

  for (let i = 0; i < n; i++) {
    const a = (i / n) * 2 * Math.PI - Math.PI / 2
    ctx.beginPath()
    ctx.moveTo(cx, cy)
    ctx.lineTo(cx + r * Math.cos(a), cy + r * Math.sin(a))
    ctx.strokeStyle = 'rgba(255,255,255,0.07)'
    ctx.lineWidth = 0.5
    ctx.stroke()
  }

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

  vals.forEach((v, i) => {
    const a = (i / n) * 2 * Math.PI - Math.PI / 2
    const x = cx + r * v * Math.cos(a)
    const y = cy + r * v * Math.sin(a)
    ctx.beginPath()
    ctx.arc(x, y, 3.5, 0, Math.PI * 2)
    ctx.fillStyle = '#E8C96A'
    ctx.fill()
  })

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
const SECTORS = {
  "IT": ["Back-end Developer", "Front-End Developer", "Software Engineer", "AI-Engineer", "Software Tester"],
  "Marketing": ["Digital Marketer", "SEO Specialist", "Content Strategist"],
  "HR": ["Technical Recruiter", "HR Business Partner"],
  "Design": ["UX/UI Designer", "Product Designer"],
  "Finance": ["Financial Analyst", "Data Analyst (Finance)"],
  "Research": ["Research Scientist", "Academic Researcher"]
}

export default function Page() {
  const [view, setView] = useState<'search' | 'talent_radar' | 'preferences' | 'interviews'>('search')
  const [interviewsList, setInterviewsList] = useState<any[]>([])
  const [showNewInterview, setShowNewInterview] = useState(false)
  const [newInterviewForm, setNewInterviewForm] = useState({ title: '', candidate_name: '', google_meet_link: '', date: '', scheduled_time: '', description: '' })
  const [cvResult, setCvResult] = useState<any>(null)
  const [isGeneratingCV, setIsGeneratingCV] = useState(false)
  const [candidateName, setCandidateName] = useState('')
  const [originalRole, setOriginalRole] = useState('Senior Backend Engineer')
  const [isRoleDropdownOpen, setIsRoleDropdownOpen] = useState(false)
  const [originalTier, setOriginalTier] = useState('Tier 1')
  // V2: university + summary profile fields
  const [university, setUniversity] = useState('')
  const [summaryProfile, setSummaryProfile] = useState('')
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
  // V1: AI backend selector
  const [backend, setBackend] = useState<'gemini' | 'ollama' | 'openrouter'>('gemini')
  const [fieldUrlHints, setFieldUrlHints] = useState<Record<string, boolean>>({})

  // V2: Preferences page state
  const [culturePrefs, setCulturePrefs] = useState<Record<string, boolean>>({})
  const [preferredUnis, setPreferredUnis] = useState<PreferredUniversity[]>([])
  const [newUniInput, setNewUniInput] = useState('')
  const [prefsLoading, setPrefsLoading] = useState(false)
  const [prefsError, setPrefsError] = useState<string | null>(null)

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

  const handleUsernameChange = useCallback((key: UsernameKey, raw: string, urlPattern: RegExp) => {
    const username = extractUsername(raw, urlPattern)
    const wasUrl = username !== raw.trim() && raw.trim().length > 0
    setUsernames(prev => ({ ...prev, [key]: username }))
    setFieldUrlHints(prev => ({ ...prev, [key]: wasUrl }))
  }, [])

  /* V2: Preferences handlers */
  const fetchPreferences = useCallback(async () => {
    setPrefsLoading(true)
    setPrefsError(null)
    try {
      const [cultureRes, unisRes] = await Promise.all([
        fetch(`${API_URL}/preferences/culture`),
        fetch(`${API_URL}/preferences/universities`),
      ])
      if (!cultureRes.ok || !unisRes.ok) throw new Error('Failed to load preferences.')
      setCulturePrefs(await cultureRes.json())
      setPreferredUnis(await unisRes.json())
    } catch (e: unknown) {
      setPrefsError(e instanceof Error ? e.message : 'Unknown error')
    } finally {
      setPrefsLoading(false)
    }
  }, [])

  const toggleCultureDim = useCallback(async (dimKey: string) => {
    const nextSelected = Object.entries({ ...culturePrefs, [dimKey]: !culturePrefs[dimKey] })
      .filter(([, on]) => on)
      .map(([key]) => key)
    setCulturePrefs(prev => ({ ...prev, [dimKey]: !prev[dimKey] }))
    try {
      const res = await fetch(`${API_URL}/preferences/culture`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ selected: nextSelected }),
      })
      if (res.ok) setCulturePrefs(await res.json())
    } catch (e) {
      console.error('Failed to update culture preferences', e)
    }
  }, [culturePrefs])

  const addUniversity = useCallback(async () => {
    const name = newUniInput.trim()
    if (!name) return
    try {
      const res = await fetch(`${API_URL}/preferences/universities`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ name }),
      })
      if (!res.ok) {
        const err = await res.json().catch(() => ({ detail: `HTTP ${res.status}` }))
        throw new Error(err.detail ?? `HTTP ${res.status}`)
      }
      const created: PreferredUniversity = await res.json()
      setPreferredUnis(prev => [...prev, created].sort((a, b) => a.name.localeCompare(b.name)))
      setNewUniInput('')
    } catch (e: unknown) {
      setPrefsError(e instanceof Error ? e.message : 'Unknown error')
    }
  }, [newUniInput])

  const removeUniversity = useCallback(async (id: number) => {
    setPreferredUnis(prev => prev.filter(u => u.id !== id))
    try {
      await fetch(`${API_URL}/preferences/universities/${id}`, { method: 'DELETE' })
    } catch (e) {
      console.error('Failed to remove university', e)
    }
  }, [])

  /* V2: Interviews handlers */
  const fetchInterviews = useCallback(async () => {
    try {
      const res = await fetch(`${API_URL}/interviews`)
      if (res.ok) setInterviewsList(await res.json())
    } catch (e) { console.error('Failed to fetch interviews', e) }
  }, [])

  const createInterview = useCallback(async () => {
    try {
      const res = await fetch(`${API_URL}/interviews`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(newInterviewForm)
      })
      if (res.ok) {
        setShowNewInterview(false)
        setNewInterviewForm({ title: '', candidate_name: '', google_meet_link: '', date: '', scheduled_time: '', description: '' })
        fetchInterviews()
      }
    } catch (e) { console.error('Failed to create interview', e) }
  }, [newInterviewForm, fetchInterviews])

  const generateCV = useCallback(async (interviewId: number) => {
    setIsGeneratingCV(true)
    setCvResult(null)
    try {
      const res = await fetch(`${API_URL}/interviews/generate-cv`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ interview_id: interviewId })
      })
      if (res.ok) {
        setCvResult(await res.json())
      } else {
        alert("Failed to generate CV. Is transcript available?")
      }
    } catch (e) { console.error(e) }
    finally { setIsGeneratingCV(false) }
  }, [])

  const downloadPDF = useCallback(async () => {
    const element = document.getElementById('cv-pdf-content');
    if (!element) return;
    try {
      const html2canvas = (await import('html2canvas')).default;
      const jsPDF = (await import('jspdf')).default;
      
      const canvas = await html2canvas(element, { scale: 2 });
      const imgData = canvas.toDataURL('image/png');
      const pdf = new jsPDF('p', 'mm', 'a4');
      const pdfWidth = pdf.internal.pageSize.getWidth();
      const pdfHeight = (canvas.height * pdfWidth) / canvas.width;
      
      pdf.addImage(imgData, 'PNG', 0, 0, pdfWidth, pdfHeight);
      pdf.save(`${cvResult?.name || 'Candidate'}_CV.pdf`);
    } catch (err) {
      console.error('PDF generation error:', err);
      alert('Failed to download PDF. Please try again.');
    }
  }, [cvResult]);

  /* evaluation — includes V1 backend param + V2 university/summaryProfile */
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
          original_tier: originalTier.trim(),
          university: university.trim() || null,
          summary_profile: summaryProfile.trim() || null,
          job_requirements: requirements,
          backend: backend,
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
  }, [candidateName, requirements, usernames, originalRole, originalTier, university, summaryProfile, backend])

  useEffect(() => {
    if (result && !result.scoring_failed && canvasRef.current) {
      setTimeout(() => {
        if (canvasRef.current) drawRadar(canvasRef.current, result.dimensions)
      }, 10)
    }
  }, [result, view])

  // ── Stats Calculations for Dashboard ──
  const gh = result?.source_details?.github
  const ghFound = !!(gh && gh.profile_url)
  const ghStars = gh?.contribution_activity?.total_stars ?? 0
  const ghFollowers = gh?.contribution_activity?.followers ?? 0
  const ghRepos = gh?.contribution_activity?.public_repos ?? gh?.repos?.length ?? 0
  const ghLanguages = gh?.top_languages ?? []
  const ghLatestPush = gh?.latest_push ?? null

  const li = result?.source_details?.linkedin
  const liFound = !!(li && li.profile_url)
  const liRole = li?.current_role ?? null
  const liCompany = li?.company ?? null
  const liSummary = li?.summary ?? null

  const gs = result?.source_details?.google_scholar
  const rg = result?.source_details?.researchgate
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

  const devto = result?.source_details?.devto
  const medium = result?.source_details?.medium
  const hashnode = result?.source_details?.hashnode
  const kaggle = result?.source_details?.kaggle
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

  const isRecentPush = ghLatestPush ? new Date(ghLatestPush).getTime() > Date.now() - 90 * 24 * 60 * 60 * 1000 : false
  const totalActivity = ghRepos + ghStars + pubCount + totalBlogs

  let activityLevel = 'None'
  let activityColor = 'var(--muted)'
  if (totalActivity > 30 || ghStars > 50 || citations > 30 || (totalActivity > 10 && isRecentPush)) {
    activityLevel = 'High'; activityColor = 'var(--green)'
  } else if (totalActivity > 10 || citations > 5 || isRecentPush) {
    activityLevel = 'Medium'; activityColor = 'var(--amber)'
  } else if (totalActivity > 0 || ghFound) {
    activityLevel = 'Low'; activityColor = 'var(--gold2)'
  }

  const profilesFound = [ghFound, liFound, acadFound, blogsFound].filter(Boolean).length
  let confidenceLevel = 'Low'
  let confidenceColor = 'var(--red)'
  if (profilesFound >= 3 || (profilesFound >= 2 && kwStats.matched >= 3)) {
    confidenceLevel = 'High'; confidenceColor = 'var(--green)'
  } else if (profilesFound === 2 || (profilesFound === 1 && kwStats.matched >= 1)) {
    confidenceLevel = 'Medium'; confidenceColor = 'var(--amber)'
  } else if (profilesFound === 0) {
    confidenceLevel = 'None'; confidenceColor = 'var(--muted)'
  }

  /* ── Render ── */
  return (
    <div style={styles.page}>
      <div style={styles.shell}>

        {/* Header */}
        <header style={styles.header}>
          <div style={styles.logo}>
            <div style={styles.logoIcon}>
              <i className="ti ti-user-search" aria-hidden style={{ fontSize: 18, color: 'var(--navy)' }} />
            </div>
            <div>
              <div style={{ fontSize: 15, fontWeight: 500 }}>HireSystem</div>
              <div style={{ fontSize: 10, color: 'var(--gold)', letterSpacing: '0.08em', textTransform: 'uppercase' }}>AI Evaluation</div>
            </div>
          </div>
          <div style={{ display: 'flex', gap: 20 }}>
            <div style={{ display: 'flex', gap: 12 }}>
              <button
                onClick={() => setView('search')}
                style={{ background: view === 'search' && !result ? 'var(--navy4)' : 'transparent', border: 'none', color: view === 'search' && !result ? 'var(--gold2)' : 'var(--slate2)', padding: '8px 16px', borderRadius: 6, cursor: 'pointer', fontWeight: 500, fontSize: 12 }}
              >
                New Evaluation
              </button>
              <button
                onClick={async () => {
                  setView('talent_radar')
                  try {
                    const res = await fetch(`${API_URL}/candidates/prioritized`)
                    if (res.ok) setCandidates(await res.json())
                  } catch (e) { console.error('Failed to fetch candidates', e) }
                }}
                style={{ background: view === 'talent_radar' ? 'var(--navy4)' : 'transparent', border: 'none', color: view === 'talent_radar' ? 'var(--gold2)' : 'var(--slate2)', padding: '8px 16px', borderRadius: 6, cursor: 'pointer', fontWeight: 500, fontSize: 12 }}
              >
                Talent Radar
              </button>
              <button
                onClick={() => { setView('preferences'); fetchPreferences() }}
                style={{ background: view === 'preferences' ? 'var(--navy4)' : 'transparent', border: 'none', color: view === 'preferences' ? 'var(--gold2)' : 'var(--slate2)', padding: '8px 16px', borderRadius: 6, cursor: 'pointer', fontWeight: 500, fontSize: 12 }}
              >
                Preferences
              </button>
              <button
                onClick={() => { setView('interviews'); fetchInterviews() }}
                style={{ background: view === 'interviews' ? 'var(--navy4)' : 'transparent', border: 'none', color: view === 'interviews' ? 'var(--gold2)' : 'var(--slate2)', padding: '8px 16px', borderRadius: 6, cursor: 'pointer', fontWeight: 500, fontSize: 12 }}
              >
                Interviews
              </button>
            </div>
            <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
              <span className="badge badge-gold">9 dimensions</span>
              {/* V1: dynamic backend label */}
              <span className="badge badge-gold">
                {backend === 'gemini' ? 'Gemini Flash' : backend === 'ollama' ? 'Ollama (Local)' : 'OpenRouter'}
              </span>
            </div>
          </div>
        </header>

        {/* Body */}
        <div style={styles.body} className="layout-split">

          {/* ── Preferences view (V2) ── */}
          {view === 'preferences' ? (
            <div style={{ padding: '24px 40px', width: '100%', maxWidth: 900, margin: '0 auto', overflowY: 'auto' }}>
              <h2 style={{ fontSize: 24, fontWeight: 600, color: 'white', marginBottom: 8 }}>Preferences</h2>
              <p style={{ color: 'var(--slate2)', fontSize: 13, marginBottom: 32 }}>
                Set what HR is looking for. The Talent Radar surfaces matching candidates first — this never changes a candidate's underlying score.
              </p>

              {prefsError && (
                <div style={{ background: 'rgba(231,76,60,0.08)', border: '0.5px solid var(--red)', color: 'var(--red)', padding: 10, borderRadius: 6, fontSize: 12, marginBottom: 20 }}>
                  {prefsError}
                </div>
              )}

              {prefsLoading ? (
                <div style={{ display: 'flex', alignItems: 'center', gap: 8, color: 'var(--slate2)', fontSize: 13 }}>
                  <span className="spinner" style={{ width: 14, height: 14, borderWidth: 2 }} />
                  Loading preferences...
                </div>
              ) : (
                <div style={{ display: 'flex', flexDirection: 'column', gap: 32 }}>
                  <div>
                    <h3 style={{ fontSize: 15, fontWeight: 500, color: 'var(--gold2)', marginBottom: 4 }}>Company Culture</h3>
                    <p style={{ fontSize: 11.5, color: 'var(--muted)', marginBottom: 12 }}>
                      Select the dimensions that matter for this role. A candidate matches when their Summary Profile reflects any of these.
                    </p>
                    <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6 }}>
                      {CULTURE_DIMENSIONS.map(dim => {
                        const isSelected = !!culturePrefs[dim.key]
                        return (
                          <button
                            key={dim.key}
                            onClick={() => toggleCultureDim(dim.key)}
                            style={{
                              background: isSelected ? 'var(--gold-dim)' : 'var(--navy4)',
                              border: `0.5px solid ${isSelected ? 'var(--gold)' : 'var(--border)'}`,
                              color: isSelected ? 'var(--navy)' : 'var(--slate2)',
                              padding: '5px 10px', borderRadius: 12, fontSize: 11.5,
                              cursor: 'pointer', transition: 'all 0.2s',
                              display: 'flex', alignItems: 'center', gap: 5,
                            }}
                          >
                            {dim.label} <i className={`ti ${isSelected ? 'ti-check' : 'ti-plus'}`} style={{ fontSize: 10 }} />
                          </button>
                        )
                      })}
                    </div>
                  </div>

                  <div>
                    <h3 style={{ fontSize: 15, fontWeight: 500, color: 'var(--gold2)', marginBottom: 4 }}>Preferred Universities</h3>
                    <p style={{ fontSize: 11.5, color: 'var(--muted)', marginBottom: 12 }}>
                      Candidates from these universities are surfaced first on the Talent Radar.
                    </p>
                    <div style={{ display: 'flex', gap: 6, marginBottom: 12, maxWidth: 360 }}>
                      <input
                        className="field-input"
                        style={{ flex: 1 }}
                        placeholder="e.g. UTAR"
                        value={newUniInput}
                        onChange={e => setNewUniInput(e.target.value)}
                        onKeyDown={e => e.key === 'Enter' && addUniversity()}
                      />
                      <button className="btn btn-ghost" onClick={addUniversity} aria-label="Add university" style={{ padding: '9px 12px' }}>
                        <i className="ti ti-plus" aria-hidden style={{ fontSize: 15 }} />
                      </button>
                    </div>
                    <div style={{ display: 'flex', flexDirection: 'column', gap: 6, maxWidth: 360 }}>
                      {preferredUnis.map(u => (
                        <div key={u.id} style={styles.reqItem}>
                          <i className="ti ti-school" aria-hidden style={{ color: 'var(--gold)', fontSize: 13, flexShrink: 0 }} />
                          <span style={{ fontSize: 12, flex: 1 }}>{u.name}</span>
                          <button onClick={() => removeUniversity(u.id)} style={styles.reqRemove} aria-label={`Remove ${u.name}`}>
                            <i className="ti ti-x" aria-hidden style={{ fontSize: 12 }} />
                          </button>
                        </div>
                      ))}
                      {preferredUnis.length === 0 && (
                        <div style={{ fontSize: 11.5, color: 'var(--muted)', fontStyle: 'italic', padding: '8px 0' }}>
                          No preferred universities set yet.
                        </div>
                      )}
                    </div>
                  </div>
                </div>
              )}
            </div>

          /* ── Interviews view (V2) ── */
          ) : view === 'interviews' ? (
            <div style={{ padding: '24px 40px', width: '100%', maxWidth: 1200, margin: '0 auto', overflowY: 'auto' }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: 32 }}>
                <div>
                  <h2 style={{ fontSize: 24, fontWeight: 600, color: 'white', marginBottom: 8 }}>Interviews</h2>
                  <p style={{ color: 'var(--slate2)', fontSize: 13 }}>Manage interview sessions, bots, and generate CVs.</p>
                </div>
                <button onClick={() => setShowNewInterview(true)} className="btn btn-primary" style={{ padding: '8px 16px', borderRadius: 8 }}>
                  + New Interview
                </button>
              </div>

              {showNewInterview && (
                <div style={{ background: 'var(--navy3)', border: '1px solid var(--border)', borderRadius: 8, padding: 20, marginBottom: 32 }}>
                  <h3 style={{ fontSize: 16, color: 'white', marginBottom: 16 }}>Schedule New Interview</h3>
                  <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 16, marginBottom: 16 }}>
                    <div><label className="field-label">Candidate Name</label><input className="field-input" value={newInterviewForm.candidate_name} onChange={e => setNewInterviewForm(f => ({...f, candidate_name: e.target.value}))} /></div>
                    <div><label className="field-label">Interview Title</label><input className="field-input" value={newInterviewForm.title} onChange={e => setNewInterviewForm(f => ({...f, title: e.target.value}))} /></div>
                    <div><label className="field-label">Google Meet Link</label><input className="field-input" value={newInterviewForm.google_meet_link} onChange={e => setNewInterviewForm(f => ({...f, google_meet_link: e.target.value}))} /></div>
                    <div style={{ display: 'flex', gap: 16 }}>
                      <div style={{ flex: 1 }}><label className="field-label">Date (YYYY-MM-DD)</label><input className="field-input" type="date" value={newInterviewForm.date} onChange={e => setNewInterviewForm(f => ({...f, date: e.target.value}))} /></div>
                      <div style={{ flex: 1 }}><label className="field-label">Time</label><input className="field-input" type="time" value={newInterviewForm.scheduled_time} onChange={e => setNewInterviewForm(f => ({...f, scheduled_time: e.target.value}))} /></div>
                    </div>
                  </div>
                  <div style={{ marginBottom: 16 }}><label className="field-label">Description</label><input className="field-input" value={newInterviewForm.description} onChange={e => setNewInterviewForm(f => ({...f, description: e.target.value}))} /></div>
                  <div style={{ display: 'flex', gap: 12, justifyContent: 'flex-end' }}>
                    <button className="btn btn-ghost" onClick={() => setShowNewInterview(false)}>Cancel</button>
                    <button className="btn btn-primary" onClick={createInterview}>Schedule</button>
                  </div>
                </div>
              )}

              {cvResult && (
                <div style={{ position: 'fixed', top: 0, left: 0, right: 0, bottom: 0, background: 'rgba(0,0,0,0.8)', zIndex: 1000, display: 'flex', flexDirection: 'column', padding: 40, overflowY: 'auto' }}>
                  <div style={{ background: 'white', color: 'black', width: '100%', maxWidth: 800, margin: '0 auto', borderRadius: 8, padding: '40px 48px', fontFamily: 'Arial, sans-serif' }} id="cv-pdf-content">
                    {/* === NAME HEADER === */}
                    <h1 style={{ fontSize: 30, fontWeight: 800, color: '#1a1a2e', marginBottom: 4 }}>{cvResult.name}</h1>
                    <div style={{ display: 'flex', flexWrap: 'wrap', gap: 12, fontSize: 13, color: '#333', marginBottom: 16, borderBottom: '2px solid #1a1a2e', paddingBottom: 10 }}>
                      {cvResult.phone && <span>{cvResult.phone}</span>}
                      {cvResult.phone && cvResult.email && <span>|</span>}
                      {cvResult.email && <span>{cvResult.email}</span>}
                      {cvResult.linkedin && <><span>|</span><a href={cvResult.linkedin} style={{ color: '#0066cc' }}>LinkedIn</a></>}
                      {cvResult.github && <><span>|</span><a href={cvResult.github} style={{ color: '#0066cc' }}>Github</a></>}
                    </div>

                    {/* === PROFESSIONAL SUMMARY === */}
                    {cvResult.summary && (<>
                      <h2 style={{ fontSize: 13, fontWeight: 700, color: '#1a1a2e', textTransform: 'uppercase', letterSpacing: '1px', marginBottom: 6 }}>Professional Summary</h2>
                      <p style={{ fontSize: 13, lineHeight: 1.6, color: '#222', marginBottom: 16, borderBottom: '1px solid #ccc', paddingBottom: 12 }}>{cvResult.summary}</p>
                    </>)}

                    {/* === EDUCATION === */}
                    {cvResult.education?.length > 0 && (<>
                      <h2 style={{ fontSize: 13, fontWeight: 700, color: '#1a1a2e', textTransform: 'uppercase', letterSpacing: '1px', marginBottom: 8 }}>Education</h2>
                      <div style={{ marginBottom: 16, borderBottom: '1px solid #ccc', paddingBottom: 12 }}>
                        {cvResult.education.map((edu: any, i: number) => (
                          <div key={i} style={{ marginBottom: 10 }}>
                            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'baseline' }}>
                              <span style={{ fontWeight: 700, fontSize: 14 }}>{edu.degree}</span>
                              <span style={{ fontSize: 12, color: '#555' }}>{edu.start_date}{edu.end_date ? ` – ${edu.end_date}` : ''}</span>
                            </div>
                            <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 13, color: '#333' }}>
                              <span>{edu.institution}</span>
                              <span>{edu.location}</span>
                            </div>
                            {edu.cgpa && <div style={{ fontSize: 12, color: '#555', marginTop: 2 }}>CGPA: {edu.cgpa}</div>}
                          </div>
                        ))}
                      </div>
                    </>)}

                    {/* === COMPETITION === */}
                    {cvResult.competitions?.length > 0 && (<>
                      <h2 style={{ fontSize: 13, fontWeight: 700, color: '#1a1a2e', textTransform: 'uppercase', letterSpacing: '1px', marginBottom: 8 }}>Competition</h2>
                      <div style={{ marginBottom: 16, borderBottom: '1px solid #ccc', paddingBottom: 12 }}>
                        {cvResult.competitions.map((comp: any, i: number) => (
                          <div key={i} style={{ marginBottom: 12 }}>
                            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'baseline' }}>
                              <span style={{ fontWeight: 700, fontSize: 14 }}>{comp.name}</span>
                              <span style={{ fontSize: 12, color: '#555' }}>{comp.date}</span>
                            </div>
                            <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 13, color: '#333', marginBottom: 4 }}>
                              <span>{comp.role}</span>
                              <span>{comp.location}</span>
                            </div>
                            {comp.project && <div style={{ fontSize: 13, color: '#333', marginBottom: 4 }}>Project: {comp.project}</div>}
                            <ul style={{ margin: '4px 0 0 16px', padding: 0 }}>
                              {comp.bullets?.map((b: string, j: number) => (
                                <li key={j} style={{ fontSize: 13, color: '#222', lineHeight: 1.6, marginBottom: 2 }}>{b}</li>
                              ))}
                            </ul>
                          </div>
                        ))}
                      </div>
                    </>)}

                    {/* === PROJECTS === */}
                    {cvResult.projects?.length > 0 && (<>
                      <h2 style={{ fontSize: 13, fontWeight: 700, color: '#1a1a2e', textTransform: 'uppercase', letterSpacing: '1px', marginBottom: 8 }}>Project</h2>
                      <div style={{ marginBottom: 16, borderBottom: '1px solid #ccc', paddingBottom: 12 }}>
                        {cvResult.projects.map((proj: any, i: number) => (
                          <div key={i} style={{ marginBottom: 12 }}>
                            <div style={{ fontWeight: 700, fontSize: 14, marginBottom: 2 }}>
                              {proj.name}{proj.tech_stack ? <span style={{ fontWeight: 400, fontSize: 13 }}> | {proj.tech_stack}</span> : ''}
                            </div>
                            <ul style={{ margin: '4px 0 0 16px', padding: 0 }}>
                              {proj.bullets?.map((b: string, j: number) => (
                                <li key={j} style={{ fontSize: 13, color: '#222', lineHeight: 1.6, marginBottom: 2 }}>{b}</li>
                              ))}
                            </ul>
                          </div>
                        ))}
                      </div>
                    </>)}

                    {/* === ACADEMIC AWARDS === */}
                    {cvResult.academic_awards?.length > 0 && (<>
                      <h2 style={{ fontSize: 13, fontWeight: 700, color: '#1a1a2e', textTransform: 'uppercase', letterSpacing: '1px', marginBottom: 8 }}>Academic Award</h2>
                      <div style={{ marginBottom: 16, borderBottom: '1px solid #ccc', paddingBottom: 12 }}>
                        {cvResult.academic_awards.map((award: string, i: number) => (
                          <div key={i} style={{ fontWeight: 700, fontSize: 13, marginBottom: 2 }}>{award}</div>
                        ))}
                      </div>
                    </>)}

                    {/* === TECHNICAL SKILLS === */}
                    {cvResult.technical_skills && (<>
                      <h2 style={{ fontSize: 13, fontWeight: 700, color: '#1a1a2e', textTransform: 'uppercase', letterSpacing: '1px', marginBottom: 8 }}>Technical Skills</h2>
                      <div style={{ fontSize: 13, lineHeight: 1.8 }}>
                        {cvResult.technical_skills.languages && <div><strong>Languages</strong> | {cvResult.technical_skills.languages}</div>}
                        {cvResult.technical_skills.frameworks && <div><strong>Frameworks</strong> | {cvResult.technical_skills.frameworks}</div>}
                        {cvResult.technical_skills.developer_tools && <div><strong>Developer Tools</strong> | {cvResult.technical_skills.developer_tools}</div>}
                        {cvResult.technical_skills.libraries && <div><strong>Libraries</strong> | {cvResult.technical_skills.libraries}</div>}
                      </div>
                    </>)}
                  </div>
                  <div style={{ display: 'flex', gap: 16, justifyContent: 'center', marginTop: 24 }}>
                    <button className="btn btn-ghost" style={{ background: 'white', color: 'black' }} onClick={() => setCvResult(null)}>Close</button>
                    <button className="btn btn-primary" onClick={downloadPDF}>Download PDF</button>
                  </div>
                </div>
              )}

              <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
                {interviewsList.map(interview => (
                  <div key={interview.id} style={{ background: 'var(--navy3)', border: '1px solid var(--border)', borderRadius: 8, padding: 16, display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                    <div>
                      <div style={{ display: 'flex', gap: 12, alignItems: 'center', marginBottom: 4 }}>
                        <h4 style={{ fontSize: 16, color: 'white', fontWeight: 600 }}>{interview.candidate_name}</h4>
                        <span style={{ fontSize: 10, padding: '2px 8px', borderRadius: 12, background: interview.status === 'COMPLETED' ? 'rgba(46, 204, 113, 0.1)' : 'rgba(201,168,76,0.1)', color: interview.status === 'COMPLETED' ? 'var(--green)' : 'var(--gold2)' }}>
                          {interview.status}
                        </span>
                      </div>
                      <p style={{ fontSize: 12, color: 'var(--slate2)' }}>{interview.title} • {interview.date} {interview.scheduled_time} • {interview.google_meet_link}</p>
                    </div>
                    <div>
                      {interview.status === 'COMPLETED' && (
                        <button 
                          className="btn btn-primary" 
                          style={{ padding: '6px 12px', fontSize: 12 }}
                          onClick={() => generateCV(interview.id)}
                          disabled={isGeneratingCV}
                        >
                          {isGeneratingCV ? 'Generating...' : 'Generate CV'}
                        </button>
                      )}
                    </div>
                  </div>
                ))}
                {interviewsList.length === 0 && (
                  <div style={{ textAlign: 'center', padding: '60px 20px', color: 'var(--slate2)' }}>
                    No interviews scheduled yet.
                  </div>
                )}
              </div>
            </div>

          /* ── Talent Radar view (V2 with preference badges) ── */
          ) : view === 'talent_radar' ? (
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
                          <div key={c.id} style={{ background: 'var(--navy3)', border: c.preference_match ? '1px solid var(--gold-dim)' : '1px solid var(--border)', borderRadius: 8, padding: 16 }}>
                            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: 12 }}>
                              <div>
                                <div style={{ fontWeight: 600, color: 'white', fontSize: 15 }}>{c.name}</div>
                                <div style={{ fontSize: 11, color: 'var(--slate2)', marginTop: 2 }}>{c.original_role || 'Unknown Role'}</div>
                              </div>
                              {c.re_engage_flag && (
                                <span style={{ background: 'rgba(46, 204, 113, 0.1)', color: 'var(--green)', padding: '2px 8px', borderRadius: 12, fontSize: 10, fontWeight: 600 }}>ACT NOW</span>
                              )}
                            </div>

                            {(c.university_match || (c.matched_culture_dimensions?.length > 0)) && (
                              <div style={{ display: 'flex', flexWrap: 'wrap', gap: 5, marginBottom: 10 }}>
                                {c.university_match && (
                                  <span style={{ display: 'inline-flex', alignItems: 'center', gap: 4, background: 'rgba(201,168,76,0.10)', border: '0.5px solid var(--gold-border)', color: 'var(--gold2)', padding: '2px 8px', borderRadius: 10, fontSize: 10 }}>
                                    <i className="ti ti-school" aria-hidden style={{ fontSize: 10 }} />
                                    {c.university}
                                  </span>
                                )}
                                {c.matched_culture_dimensions?.map((dim: string) => (
                                  <span key={dim} style={{ display: 'inline-flex', alignItems: 'center', gap: 4, background: 'rgba(201,168,76,0.10)', border: '0.5px solid var(--gold-border)', color: 'var(--gold2)', padding: '2px 8px', borderRadius: 10, fontSize: 10 }}>
                                    <i className="ti ti-sparkles" aria-hidden style={{ fontSize: 10 }} />
                                    {CULTURE_DIMENSIONS.find(d => d.key === dim)?.label ?? dim}
                                  </span>
                                ))}
                              </div>
                            )}

                            <div style={{ fontSize: 12, color: 'var(--slate2)', background: 'var(--navy4)', padding: 10, borderRadius: 6, marginBottom: 12 }}>
                              {c.whats_changed_summary || 'No recent updates available.'}
                            </div>
                            <div style={{ display: 'flex', gap: 12, fontSize: 11 }}>
                              <div style={{ color: 'var(--slate)' }}>Tier: <span style={{ color: 'white' }}>{c.original_tier || 'N/A'}</span></div>
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

          /* ── Search / Evaluation view ── */
          ) : (
            <>
              {/* ── Left panel ── */}
              <div style={styles.panelLeft} className="panel-left">

                <div className="section-label">Candidate</div>
                <div style={{ marginBottom: 20 }}>
                  <label className="field-label">Full name</label>
                  <input className="field-input" placeholder="e.g. Andrew Ng" value={candidateName} onChange={e => setCandidateName(e.target.value)} />
                </div>

                {/* Optional usernames */}
                <div style={{ marginBottom: 20 }}>
                  <button
                    onClick={() => setShowUsernames(v => !v)}
                    style={{ display: 'flex', alignItems: 'center', gap: 6, background: 'none', border: 'none', cursor: 'pointer', padding: 0, fontSize: 11, color: 'var(--slate)', width: '100%', justifyContent: 'space-between' }}
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

                <div style={{ marginBottom: 20, position: 'relative' }}>
                  <label className="field-label">Original Role Applied For</label>
                  <div
                    className="field-input"
                    onClick={() => setIsRoleDropdownOpen(!isRoleDropdownOpen)}
                    style={{ cursor: 'pointer', display: 'flex', justifyContent: 'space-between', alignItems: 'center', backgroundColor: 'var(--slate-dark)', color: '#fff' }}
                  >
                    {originalRole || 'Select a role...'}
                    <i className="ti-chevron-down" style={{ fontSize: 12, color: 'var(--slate)' }}></i>
                  </div>
                  {isRoleDropdownOpen && (
                    <>
                      <div
                        style={{ position: 'fixed', inset: 0, zIndex: 9 }}
                        onClick={() => setIsRoleDropdownOpen(false)}
                      />
                      <div style={{
                        position: 'absolute',
                        top: '100%',
                        left: 0,
                        right: 0,
                        marginTop: 4,
                        backgroundColor: '#0f172a',
                        border: '1px solid var(--slate-border)',
                        borderRadius: 8,
                        zIndex: 10,
                        overflowY: 'auto',
                        maxHeight: '220px',
                        boxShadow: '0 4px 6px -1px rgba(0, 0, 0, 0.5), 0 2px 4px -1px rgba(0, 0, 0, 0.5)'
                      }}>
                        {Object.entries(SECTORS).map(([sector, roles]) => (
                          <div key={sector}>
                            <div style={{ padding: '8px 14px', fontSize: 11, fontWeight: 700, color: '#94a3b8', backgroundColor: '#1e293b', textTransform: 'uppercase', letterSpacing: '0.05em' }}>
                              {sector}
                            </div>
                            {roles.map(role => (
                              <div
                                key={role}
                                onClick={() => {
                                  setOriginalRole(role)
                                  setIsRoleDropdownOpen(false)
                                }}
                                style={{
                                  padding: '10px 14px 10px 24px',
                                  cursor: 'pointer',
                                  fontSize: 14,
                                  color: originalRole === role ? '#fff' : 'var(--slate)',
                                  backgroundColor: originalRole === role ? 'rgba(56, 189, 248, 0.1)' : 'transparent',
                                }}
                                onMouseEnter={e => e.currentTarget.style.backgroundColor = 'var(--slate-dark)'}
                                onMouseLeave={e => e.currentTarget.style.backgroundColor = originalRole === role ? 'rgba(56, 189, 248, 0.1)' : 'transparent'}
                              >
                                {role}
                              </div>
                            ))}
                          </div>
                        ))}
                      </div>
                    </>
                  )}
                </div>

                <div style={{ marginBottom: 20 }}>
                  <label className="field-label">Original HINT Tier</label>
                  <input className="field-input" placeholder="e.g. Tier 1" value={originalTier} onChange={e => setOriginalTier(e.target.value)} />
                </div>

                {/* V2: University + Summary Profile */}
                <div style={{ marginBottom: 20 }}>
                  <label className="field-label">University (optional)</label>
                  <input className="field-input" placeholder="e.g. UTAR" value={university} onChange={e => setUniversity(e.target.value)} />
                </div>
                <div style={{ marginBottom: 20 }}>
                  <label className="field-label">Summary Profile (optional)</label>
                  <textarea
                    className="field-input"
                    placeholder="Short paragraph describing the candidate's working style..."
                    value={summaryProfile}
                    onChange={e => setSummaryProfile(e.target.value)}
                    rows={3}
                    style={{ resize: 'vertical', minHeight: 60, width: '100%', fontFamily: 'inherit' }}
                  />
                </div>



                <div className="section-label">Job requirements</div>

                <div style={{ marginBottom: 12 }}>
                  <div style={{ fontSize: 10.5, color: 'var(--slate)', marginBottom: 6 }}>Trending Requirements</div>
                  <div style={{ display: 'flex', flexWrap: 'wrap', gap: 5 }}>
                    {['Machine Learning', 'Python', 'React', 'AWS', 'Node.js', 'System Design'].map(skill => {
                      const isSelected = requirements.includes(skill)
                      return (
                        <button
                          key={skill}
                          onClick={() => { if (!isSelected) setRequirements(prev => [...prev, skill]) }}
                          style={{ background: isSelected ? 'var(--gold-dim)' : 'var(--navy4)', border: `0.5px solid ${isSelected ? 'var(--gold)' : 'var(--border)'}`, color: isSelected ? 'var(--navy)' : 'var(--slate2)', padding: '3px 8px', borderRadius: 12, fontSize: 10, cursor: isSelected ? 'default' : 'pointer', transition: 'all 0.2s', display: 'flex', alignItems: 'center', gap: 4 }}
                          disabled={isSelected}
                        >
                          {skill} <i className={`ti ${isSelected ? 'ti-check' : 'ti-plus'}`} style={{ fontSize: 9 }} />
                        </button>
                      )
                    })}
                  </div>
                </div>

                <div style={{ display: 'flex', flexDirection: 'column', gap: 6, marginBottom: 10 }}>
                  {requirements.map((r, i) => (
                    <div key={i} style={styles.reqItem}>
                      <i className="ti ti-check" aria-hidden style={{ color: 'var(--gold)', fontSize: 13, flexShrink: 0 }} />
                      <span style={{ fontSize: 12, flex: 1 }}>{r}</span>
                      <button onClick={() => removeReq(i)} style={styles.reqRemove} aria-label={`Remove ${r}`}>
                        <i className="ti ti-x" aria-hidden style={{ fontSize: 12 }} />
                      </button>
                    </div>
                  ))}
                </div>

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

                {/* V1: AI Backend Selector */}
                <div style={{ marginBottom: 16, marginTop: 20 }}>
                  <label className="field-label" style={{ marginBottom: 8, display: 'flex', alignItems: 'center', gap: 5 }}>
                    <i className="ti ti-cpu" aria-hidden style={{ fontSize: 11 }} />
                    AI Backend
                  </label>
                  <div style={{ display: 'flex', gap: 6 }}>
                    {([
                      { value: 'gemini',     label: 'Gemini',     icon: 'ti-sparkles', desc: 'Google Gemini Flash' },
                      { value: 'ollama',     label: 'Ollama',     icon: 'ti-server',   desc: 'Local model' },
                      { value: 'openrouter', label: 'OpenRouter', icon: 'ti-cloud',    desc: 'DeepSeek / Claude' },
                    ] as const).map(opt => (
                      <button
                        key={opt.value}
                        onClick={() => setBackend(opt.value)}
                        title={opt.desc}
                        style={{
                          flex: 1, display: 'flex', flexDirection: 'column', alignItems: 'center',
                          gap: 4, padding: '8px 6px', borderRadius: 8, cursor: 'pointer',
                          fontFamily: 'inherit', fontSize: 10.5,
                          fontWeight: backend === opt.value ? 600 : 400,
                          transition: 'all 0.15s',
                          background: backend === opt.value ? 'rgba(201,168,76,0.12)' : 'var(--navy3)',
                          border: backend === opt.value ? '1.5px solid var(--gold-dim)' : '0.5px solid var(--border)',
                          color: backend === opt.value ? 'var(--gold2)' : 'var(--slate2)',
                        }}
                      >
                        <i className={`ti ${opt.icon}`} aria-hidden style={{ fontSize: 15 }} />
                        {opt.label}
                      </button>
                    ))}
                  </div>
                  <div style={{ marginTop: 6, fontSize: 10, color: 'var(--muted)', textAlign: 'center' }}>
                    {backend === 'gemini'     && 'Requires GEMINI_API_KEY in .env'}
                    {backend === 'ollama'     && 'Local — make sure ollama is running + model pulled'}
                    {backend === 'openrouter' && 'Requires OPENROUTER_API_KEY in .env'}
                  </div>
                </div>

                <button className="btn btn-primary" style={{ width: '100%', marginTop: 8 }} onClick={runEval} disabled={loading}>
                  {loading
                    ? <><span className="spinner" style={{ width: 16, height: 16, borderWidth: 2 }} />Evaluating...</>
                    : <><i className="ti ti-sparkles" aria-hidden style={{ fontSize: 16 }} />Evaluate candidate</>
                  }
                </button>

                <a href={`${API_URL}/candidates`} target="_blank" rel="noreferrer" style={styles.leaderboardLink}>
                  <i className="ti ti-trophy" aria-hidden style={{ fontSize: 13 }} />
                  View leaderboard
                </a>
              </div>

              {/* ── Right panel ── */}
              <div style={styles.panelRight}>

                {!loading && !result && !error && (
                  <div style={styles.emptyState}>
                    <i className="ti ti-chart-radar" aria-hidden style={{ fontSize: 44, color: 'var(--gold-dim)' }} />
                    <p style={{ fontSize: 13, color: 'var(--muted)', textAlign: 'center', maxWidth: 200, lineHeight: 1.7 }}>
                      Enter a candidate name and job requirements, then run evaluation
                    </p>
                  </div>
                )}

                {loading && (
                  <div style={styles.emptyState}>
                    <div className="spinner" />
                    <p className="pulse" style={{ fontSize: 12, color: 'var(--slate)', letterSpacing: '0.04em' }}>{LOADING_STEPS[loadingStep]}</p>
                  </div>
                )}

                {error && (
                  <div style={styles.emptyState}>
                    <i className="ti ti-wifi-off" aria-hidden style={{ fontSize: 36, color: 'var(--red)' }} />
                    <p style={{ color: 'var(--red)', fontSize: 13, textAlign: 'center' }}>{error}</p>
                    <p style={{ color: 'var(--muted)', fontSize: 11, textAlign: 'center' }}>Make sure the backend is running on port 8000</p>
                  </div>
                )}

                {result && (
                  <div style={{ display: 'flex', flexDirection: 'column', gap: 20, width: '100%' }}>

                    {result.scoring_failed && (
                      <div style={{ display: 'flex', alignItems: 'flex-start', gap: 10, padding: '10px 14px', borderRadius: 8, background: 'rgba(239,159,39,0.08)', border: '0.5px solid rgba(239,159,39,0.35)' }}>
                        <i className="ti ti-alert-triangle" aria-hidden style={{ fontSize: 16, color: 'var(--amber)', marginTop: 1, flexShrink: 0 }} />
                        <div>
                          <div style={{ fontSize: 12, fontWeight: 500, color: 'var(--amber)' }}>AI scoring unavailable</div>
                          <div style={{ fontSize: 11, color: 'var(--slate)', marginTop: 2, lineHeight: 1.5 }}>
                            Public profile data was collected and is shown below. Configure your AI API key to enable dimension scoring.
                          </div>
                        </div>
                      </div>
                    )}

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
                          <div style={{ fontSize: 28, fontWeight: 500, color: 'var(--gold2)', lineHeight: 1 }}>{Math.round(result.rescoring_score)}</div>
                          <div style={{ fontSize: 10, color: 'var(--gold-dim)', letterSpacing: '0.08em', textTransform: 'uppercase', marginTop: 2 }}>Overall</div>
                        </div>
                      )}
                    </div>

                    {!result.scoring_failed && (
                      <div style={{ display: 'flex', justifyContent: 'center' }}>
                        <canvas ref={canvasRef} width={280} height={280} aria-label="Radar chart of 9 dimension scores" />
                      </div>
                    )}

                    {!result.scoring_failed && (
                      <div>
                        <div className="section-label">Dimension scores</div>
                        <div style={styles.dimGrid}>
                          {DIMS.map(d => {
                            const val = result.dimensions[d.key as keyof DimensionScores] ?? 0
                            const cl = getColorClass(val, d.key === 'risk_indicators')
                            const color = getScoreColor(val, d.key === 'risk_indicators')
                            return (
                              <div key={d.key} style={{ ...styles.dimCard, ...(d.primary ? styles.dimCardPrimary : {}) }}>
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

                    {/* Source chips — full list from V1 */}
                    <div>
                      <div className="section-label">Public profiles found</div>
                      <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap' }}>
                        {SOURCES.map(s => {
                          const url = result.source_urls[s.key as keyof SourceURLs]
                          const found = !!url
                          return found ? (
                            <a key={s.key} href={url!} target="_blank" rel="noreferrer" style={styles.srcChipFound}>
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

                    {/* Analytical Dashboard */}
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

                      <div style={styles.dbGrid}>

                        {/* GitHub */}
                        <div style={styles.dbCard}>
                          <div style={styles.dbCardHeader}>
                            <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                              <i className="ti ti-brand-github" style={{ fontSize: 18, color: 'var(--gold2)' }} />
                              <span style={{ fontSize: 13, fontWeight: 600 }}>GitHub Activity</span>
                            </div>
                            {ghFound ? <span className="badge badge-green" style={{ fontSize: 9, padding: '2px 6px' }}>Active</span> : <span className="badge" style={{ fontSize: 9, padding: '2px 6px', background: 'var(--border2)', color: 'var(--muted)' }}>Not Found</span>}
                          </div>
                          {ghFound ? (
                            <div style={{ display: 'flex', flexDirection: 'column', gap: 12, marginTop: 10 }}>
                              <div style={styles.dbStatRow}>
                                <div style={styles.dbStatCol}><span style={styles.dbStatVal}>{ghRepos}</span><span style={styles.dbStatLabel}>Repos</span></div>
                                <div style={styles.dbStatCol}><span style={styles.dbStatVal}>{ghStars}</span><span style={styles.dbStatLabel}>Stars</span></div>
                                <div style={styles.dbStatCol}><span style={styles.dbStatVal}>{ghFollowers}</span><span style={styles.dbStatLabel}>Followers</span></div>
                              </div>
                              {ghLanguages.length > 0 && (
                                <div>
                                  <div style={styles.dbSubLabel}>Top Languages</div>
                                  <div style={{ display: 'flex', gap: 4, flexWrap: 'wrap', marginTop: 4 }}>
                                    {ghLanguages.slice(0, 4).map((lang: string) => <span key={lang} style={styles.langBadge}>{lang}</span>)}
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
                          ) : <div style={styles.dbCardEmpty}>No public GitHub activity data was retrieved.</div>}
                        </div>

                        {/* LinkedIn */}
                        <div style={styles.dbCard}>
                          <div style={styles.dbCardHeader}>
                            <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                              <i className="ti ti-briefcase" style={{ fontSize: 18, color: 'var(--gold2)' }} />
                              <span style={{ fontSize: 13, fontWeight: 600 }}>LinkedIn Profile</span>
                            </div>
                            {liFound ? <span className="badge badge-green" style={{ fontSize: 9, padding: '2px 6px' }}>Matched</span> : <span className="badge" style={{ fontSize: 9, padding: '2px 6px', background: 'var(--border2)', color: 'var(--muted)' }}>Not Found</span>}
                          </div>
                          {liFound ? (
                            <div style={{ display: 'flex', flexDirection: 'column', gap: 10, marginTop: 10 }}>
                              <div style={{ fontSize: 13, fontWeight: 500, color: 'var(--text)' }}>LinkedIn Profile Confirmed</div>
                              {liSummary && <p style={{ fontSize: 11, color: 'var(--slate2)', lineHeight: 1.5, fontStyle: 'italic' }}>"{liSummary.length > 140 ? liSummary.slice(0, 140) + '...' : liSummary}"</p>}
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
                                <a href={li.profile_url} target="_blank" rel="noreferrer" style={{ display: 'inline-flex', alignItems: 'center', gap: 4, fontSize: 11, color: 'var(--gold2)', textDecoration: 'none', marginTop: 4, fontWeight: 500 }}>
                                  View Profile <i className="ti ti-external-link" style={{ fontSize: 12 }} />
                                </a>
                              )}
                            </div>
                          ) : <div style={styles.dbCardEmpty}>No public LinkedIn profile data matched.</div>}
                        </div>

                        {/* Academic */}
                        <div style={styles.dbCard}>
                          <div style={styles.dbCardHeader}>
                            <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                              <i className="ti ti-school" style={{ fontSize: 18, color: 'var(--gold2)' }} />
                              <span style={{ fontSize: 13, fontWeight: 600 }}>Academic Footprint</span>
                            </div>
                            {acadFound ? <span className="badge badge-green" style={{ fontSize: 9, padding: '2px 6px' }}>Found</span> : <span className="badge" style={{ fontSize: 9, padding: '2px 6px', background: 'var(--border2)', color: 'var(--muted)' }}>Not Found</span>}
                          </div>
                          {acadFound ? (
                            <div style={{ display: 'flex', flexDirection: 'column', gap: 10, marginTop: 10 }}>
                              <div style={styles.dbStatRow}>
                                <div style={styles.dbStatCol}><span style={styles.dbStatVal}>{citations}</span><span style={styles.dbStatLabel}>Citations</span></div>
                                <div style={styles.dbStatCol}><span style={styles.dbStatVal}>{pubCount}</span><span style={styles.dbStatLabel}>Publications</span></div>
                              </div>
                              {interests.length > 0 && (
                                <div>
                                  <div style={styles.dbSubLabel}>Research Focus</div>
                                  <div style={{ display: 'flex', gap: 4, flexWrap: 'wrap', marginTop: 4 }}>
                                    {interests.slice(0, 3).map((item: string) => <span key={item} style={styles.interestBadge}>{item}</span>)}
                                  </div>
                                </div>
                              )}
                              {pubs.length > 0 && (
                                <div style={{ marginTop: 6 }}>
                                  <div style={styles.dbSubLabel}>Top Publications</div>
                                  <div style={{ display: 'flex', flexDirection: 'column', gap: 6, marginTop: 4 }}>
                                    {pubs.slice(0, 3).map((pub: any, idx: number) => (
                                      <a key={idx} href={pub.url || `https://scholar.google.com/scholar?q=${encodeURIComponent(pub.title || '')}`} target="_blank" rel="noreferrer" style={{ fontSize: 11, color: 'var(--gold2)', textDecoration: 'underline', display: 'block', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis', cursor: 'pointer' }}>
                                        <i className="ti ti-file-text" style={{ marginRight: 4 }} />{pub.title}
                                      </a>
                                    ))}
                                  </div>
                                </div>
                              )}
                            </div>
                          ) : <div style={styles.dbCardEmpty}>No papers, citations or ResearchGate profile found.</div>}
                        </div>

                        {/* Developer Community */}
                        <div style={styles.dbCard}>
                          <div style={styles.dbCardHeader}>
                            <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                              <i className="ti ti-pencil" style={{ fontSize: 18, color: 'var(--gold2)' }} />
                              <span style={{ fontSize: 13, fontWeight: 600 }}>Developer Community</span>
                            </div>
                            {blogsFound || result?.source_details?.kaggle?.profile_url ? <span className="badge badge-green" style={{ fontSize: 9, padding: '2px 6px' }}>Active</span> : <span className="badge" style={{ fontSize: 9, padding: '2px 6px', background: 'var(--border2)', color: 'var(--muted)' }}>Not Found</span>}
                          </div>
                          {(blogsFound || result?.source_details?.kaggle?.profile_url) ? (
                            <div style={{ display: 'flex', flexDirection: 'column', gap: 10, marginTop: 10 }}>
                              <div style={styles.dbStatRow}>
                                <div style={styles.dbStatCol}><span style={styles.dbStatVal}>{totalBlogs}</span><span style={styles.dbStatLabel}>Blog Posts</span></div>
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
                                    {allCommunityWorks.slice(0, 4).map((work: any, idx: number) => (
                                      <a key={idx} href={work.url || `https://www.google.com/search?q=${encodeURIComponent(work.title || '')}`} target="_blank" rel="noreferrer" style={{ fontSize: 11, color: 'var(--gold2)', textDecoration: 'underline', display: 'block', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis', cursor: 'pointer' }}>
                                        <i className="ti ti-link" style={{ marginRight: 4 }} />{work.title}
                                      </a>
                                    ))}
                                  </div>
                                </div>
                              )}
                            </div>
                          ) : <div style={styles.dbCardEmpty}>No active developer blogging or Kaggle profile found.</div>}
                        </div>

                        {/* ── Marketing Cards (V1) ── */}
                        {result?.source_details?.instagram?.profile_url && (
                          <div style={styles.dbCard}>
                            <div style={styles.dbCardHeader}>
                              <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}><i className="ti ti-brand-instagram" style={{ fontSize: 18, color: 'var(--gold2)' }} /><span style={{ fontSize: 13, fontWeight: 600 }}>Instagram</span></div>
                              <span className="badge badge-green" style={{ fontSize: 9, padding: '2px 6px' }}>Found</span>
                            </div>
                            <div style={{ display: 'flex', flexDirection: 'column', gap: 10, marginTop: 10 }}>
                              <div style={styles.dbStatRow}>
                                <div style={styles.dbStatCol}><span style={styles.dbStatVal}>{result.source_details.instagram.followers ?? 'N/A'}</span><span style={styles.dbStatLabel}>Followers</span></div>
                                <div style={styles.dbStatCol}><span style={styles.dbStatVal}>{result.source_details.instagram.posts ?? 'N/A'}</span><span style={styles.dbStatLabel}>Posts</span></div>
                              </div>
                              <div style={{ fontSize: 11, color: 'var(--slate)' }}>{result.source_details.instagram.summary}</div>
                            </div>
                          </div>
                        )}

                        {result?.source_details?.tiktok?.profile_url && (
                          <div style={styles.dbCard}>
                            <div style={styles.dbCardHeader}>
                              <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}><i className="ti ti-brand-tiktok" style={{ fontSize: 18, color: 'var(--gold2)' }} /><span style={{ fontSize: 13, fontWeight: 600 }}>TikTok</span></div>
                              <span className="badge badge-green" style={{ fontSize: 9, padding: '2px 6px' }}>Found</span>
                            </div>
                            <div style={{ display: 'flex', flexDirection: 'column', gap: 10, marginTop: 10 }}>
                              <div style={styles.dbStatRow}>
                                <div style={styles.dbStatCol}><span style={styles.dbStatVal}>{result.source_details.tiktok.followers ?? 'N/A'}</span><span style={styles.dbStatLabel}>Followers</span></div>
                                <div style={styles.dbStatCol}><span style={styles.dbStatVal}>{result.source_details.tiktok.likes ?? 'N/A'}</span><span style={styles.dbStatLabel}>Likes</span></div>
                              </div>
                              <div style={{ fontSize: 11, color: 'var(--slate)' }}>{result.source_details.tiktok.summary}</div>
                            </div>
                          </div>
                        )}

                        {result?.source_details?.meta_ad_library?.profile_url && (
                          <div style={styles.dbCard}>
                            <div style={styles.dbCardHeader}>
                              <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}><i className="ti ti-ad" style={{ fontSize: 18, color: 'var(--gold2)' }} /><span style={{ fontSize: 13, fontWeight: 600 }}>Meta Ad Library</span></div>
                              <span className="badge badge-green" style={{ fontSize: 9, padding: '2px 6px' }}>Searched</span>
                            </div>
                            <div style={{ marginTop: 10 }}>
                              {result.source_details.meta_ad_library.active_ads != null && (
                                <div style={styles.dbStatRow}><div style={styles.dbStatCol}><span style={styles.dbStatVal}>{result.source_details.meta_ad_library.active_ads}</span><span style={styles.dbStatLabel}>Active Ads</span></div></div>
                              )}
                              <div style={{ fontSize: 11, color: 'var(--slate)', marginTop: 8 }}>{result.source_details.meta_ad_library.summary}</div>
                            </div>
                          </div>
                        )}

                        {result?.source_details?.similarweb?.profile_url && (
                          <div style={styles.dbCard}>
                            <div style={styles.dbCardHeader}>
                              <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}><i className="ti ti-chart-bar" style={{ fontSize: 18, color: 'var(--gold2)' }} /><span style={{ fontSize: 13, fontWeight: 600 }}>Similarweb</span></div>
                              <span className="badge badge-green" style={{ fontSize: 9, padding: '2px 6px' }}>Found</span>
                            </div>
                            <div style={{ marginTop: 10 }}>
                              <div style={{ fontSize: 12, color: 'var(--slate2)' }}>{result.source_details.similarweb.traffic_trend ?? 'No traffic data'}</div>
                              <div style={{ fontSize: 11, color: 'var(--slate)', marginTop: 6 }}>{result.source_details.similarweb.summary}</div>
                            </div>
                          </div>
                        )}

                        {/* ── HR Cards (V1) ── */}
                        {result?.source_details?.shrm && (
                          <div style={styles.dbCard}>
                            <div style={styles.dbCardHeader}>
                              <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}><i className="ti ti-certificate" style={{ fontSize: 18, color: 'var(--gold2)' }} /><span style={{ fontSize: 13, fontWeight: 600 }}>SHRM Certification</span></div>
                              {result.source_details.shrm.verified ? <span className="badge badge-green" style={{ fontSize: 9, padding: '2px 6px' }}>Verified</span> : <span className="badge" style={{ fontSize: 9, padding: '2px 6px', background: 'var(--border2)', color: 'var(--muted)' }}>Not Found</span>}
                            </div>
                            <div style={{ marginTop: 10 }}>
                              {result.source_details.shrm.certification && <div style={{ fontSize: 14, fontWeight: 600, color: 'var(--green)', marginBottom: 6 }}>{result.source_details.shrm.certification}</div>}
                              <div style={{ fontSize: 11, color: 'var(--slate)' }}>{result.source_details.shrm.summary}</div>
                            </div>
                          </div>
                        )}

                        {result?.source_details?.cipd && (
                          <div style={styles.dbCard}>
                            <div style={styles.dbCardHeader}>
                              <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}><i className="ti ti-certificate-2" style={{ fontSize: 18, color: 'var(--gold2)' }} /><span style={{ fontSize: 13, fontWeight: 600 }}>CIPD Membership</span></div>
                              {result.source_details.cipd.verified ? <span className="badge badge-green" style={{ fontSize: 9, padding: '2px 6px' }}>Verified</span> : <span className="badge" style={{ fontSize: 9, padding: '2px 6px', background: 'var(--border2)', color: 'var(--muted)' }}>Not Found</span>}
                            </div>
                            <div style={{ marginTop: 10 }}>
                              {result.source_details.cipd.membership_grade && <div style={{ fontSize: 14, fontWeight: 600, color: 'var(--green)', marginBottom: 6 }}>{result.source_details.cipd.membership_grade}</div>}
                              <div style={{ fontSize: 11, color: 'var(--slate)' }}>{result.source_details.cipd.summary}</div>
                            </div>
                          </div>
                        )}

                        {result?.source_details?.glassdoor && (
                          <div style={styles.dbCard}>
                            <div style={styles.dbCardHeader}>
                              <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}><i className="ti ti-star" style={{ fontSize: 18, color: 'var(--gold2)' }} /><span style={{ fontSize: 13, fontWeight: 600 }}>Glassdoor</span></div>
                              {result.source_details.glassdoor.rating ? <span className="badge badge-green" style={{ fontSize: 9, padding: '2px 6px' }}>Found</span> : <span className="badge" style={{ fontSize: 9, padding: '2px 6px', background: 'var(--border2)', color: 'var(--muted)' }}>Not Found</span>}
                            </div>
                            <div style={{ marginTop: 10 }}>
                              {result.source_details.glassdoor.rating && (
                                <div style={styles.dbStatRow}>
                                  <div style={styles.dbStatCol}><span style={styles.dbStatVal}>{result.source_details.glassdoor.rating}</span><span style={styles.dbStatLabel}>Rating /5</span></div>
                                  <div style={styles.dbStatCol}><span style={styles.dbStatVal}>{result.source_details.glassdoor.review_count ?? '?'}</span><span style={styles.dbStatLabel}>Reviews</span></div>
                                </div>
                              )}
                              <div style={{ fontSize: 11, color: 'var(--slate)', marginTop: 8 }}>{result.source_details.glassdoor.summary}</div>
                            </div>
                          </div>
                        )}

                        {result?.source_details?.ssm_acra && (
                          <div style={styles.dbCard}>
                            <div style={styles.dbCardHeader}>
                              <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}><i className="ti ti-building-bank" style={{ fontSize: 18, color: 'var(--gold2)' }} /><span style={{ fontSize: 13, fontWeight: 600 }}>SSM / ACRA</span></div>
                              {result.source_details.ssm_acra.status ? <span className="badge badge-green" style={{ fontSize: 9, padding: '2px 6px' }}>Found</span> : <span className="badge" style={{ fontSize: 9, padding: '2px 6px', background: 'var(--border2)', color: 'var(--muted)' }}>Not Found</span>}
                            </div>
                            <div style={{ marginTop: 10 }}>
                              {result.source_details.ssm_acra.status && <div style={{ fontSize: 12, color: 'var(--green)', fontWeight: 600, marginBottom: 4 }}>{result.source_details.ssm_acra.status} — {result.source_details.ssm_acra.jurisdiction}</div>}
                              <div style={{ fontSize: 11, color: 'var(--slate)' }}>{result.source_details.ssm_acra.summary}</div>
                            </div>
                          </div>
                        )}

                        {/* ── Design Cards (V1) ── */}
                        {result?.source_details?.behance?.profile_url && (
                          <div style={styles.dbCard}>
                            <div style={styles.dbCardHeader}>
                              <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}><i className="ti ti-brand-behance" style={{ fontSize: 18, color: 'var(--gold2)' }} /><span style={{ fontSize: 13, fontWeight: 600 }}>Behance</span></div>
                              <span className="badge badge-green" style={{ fontSize: 9, padding: '2px 6px' }}>Found</span>
                            </div>
                            <div style={{ display: 'flex', flexDirection: 'column', gap: 10, marginTop: 10 }}>
                              <div style={styles.dbStatRow}>
                                <div style={styles.dbStatCol}><span style={styles.dbStatVal}>{result.source_details.behance.projects ?? 'N/A'}</span><span style={styles.dbStatLabel}>Projects</span></div>
                                <div style={styles.dbStatCol}><span style={styles.dbStatVal}>{result.source_details.behance.appreciations ?? 'N/A'}</span><span style={styles.dbStatLabel}>Appreciations</span></div>
                              </div>
                            </div>
                          </div>
                        )}

                        {result?.source_details?.dribbble?.profile_url && (
                          <div style={styles.dbCard}>
                            <div style={styles.dbCardHeader}>
                              <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}><i className="ti ti-brand-dribbble" style={{ fontSize: 18, color: 'var(--gold2)' }} /><span style={{ fontSize: 13, fontWeight: 600 }}>Dribbble</span></div>
                              <span className="badge badge-green" style={{ fontSize: 9, padding: '2px 6px' }}>Found</span>
                            </div>
                            <div style={{ display: 'flex', flexDirection: 'column', gap: 10, marginTop: 10 }}>
                              <div style={styles.dbStatRow}>
                                <div style={styles.dbStatCol}><span style={styles.dbStatVal}>{result.source_details.dribbble.shots ?? 'N/A'}</span><span style={styles.dbStatLabel}>Shots</span></div>
                                <div style={styles.dbStatCol}><span style={styles.dbStatVal}>{result.source_details.dribbble.followers ?? 'N/A'}</span><span style={styles.dbStatLabel}>Followers</span></div>
                              </div>
                            </div>
                          </div>
                        )}

                        {/* ── Finance Card (V1) ── */}
                        {result?.source_details?.sc_mq && (
                          <div style={styles.dbCard}>
                            <div style={styles.dbCardHeader}>
                              <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}><i className="ti ti-license" style={{ fontSize: 18, color: 'var(--gold2)' }} /><span style={{ fontSize: 13, fontWeight: 600 }}>Finance License</span></div>
                              {result.source_details.sc_mq.verified ? <span className="badge badge-green" style={{ fontSize: 9, padding: '2px 6px' }}>Verified</span> : <span className="badge" style={{ fontSize: 9, padding: '2px 6px', background: 'var(--border2)', color: 'var(--muted)' }}>Not Found</span>}
                            </div>
                            <div style={{ marginTop: 10 }}>
                              {result.source_details.sc_mq.license && <div style={{ fontSize: 14, fontWeight: 600, color: 'var(--green)', marginBottom: 6 }}>{result.source_details.sc_mq.license}</div>}
                              <div style={{ fontSize: 11, color: 'var(--slate)' }}>{result.source_details.sc_mq.summary}</div>
                            </div>
                          </div>
                        )}
                      </div>

                      {/* Keyword Alignment Banner */}
                      {kwStats.total > 0 && (
                        <div style={styles.kwAlignmentBox}>
                          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 10 }}>
                            <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                              <i className="ti ti-target" style={{ fontSize: 16, color: 'var(--gold2)' }} />
                              <span style={{ fontSize: 12.5, fontWeight: 500 }}>Job Description Keyword Relevance</span>
                            </div>
                            <span style={{ fontSize: 12, fontWeight: 600, color: 'var(--gold2)' }}>{kwStats.matched} / {kwStats.total} matched ({kwStats.percentage}%)</span>
                          </div>
                          <div style={{ height: 4, background: 'rgba(255,255,255,0.06)', borderRadius: 2, overflow: 'hidden', marginBottom: 12 }}>
                            <div style={{ height: '100%', width: `${kwStats.percentage}%`, background: 'var(--gold2)', borderRadius: 2, transition: 'width 1s ease-out' }} />
                          </div>
                          <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap' }}>
                            {kwStats.list.map(kw => (
                              <span key={kw.word} style={{ ...styles.kwChip, ...(kw.hit ? styles.kwChipHit : styles.kwChipMiss) }}>
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

                    {/* AI Summary placeholder */}
                    <div>
                      <div className="section-label">AI Summary</div>
                      <div style={styles.aiSummaryBox}>
                        <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 12 }}>
                          <div style={styles.aiSummaryIcon}>
                            <i className="ti ti-robot" aria-hidden style={{ fontSize: 18, color: 'var(--gold2)' }} />
                          </div>
                          <div>
                            <div style={{ fontSize: 13, fontWeight: 500, color: 'var(--text)' }}>AI-generated Candidate Summary</div>
                            <div style={{ fontSize: 11, color: 'var(--slate)', marginTop: 1 }}>Powered by your chosen AI model</div>
                          </div>
                        </div>
                        <div style={result.executive_summary ? { padding: '8px 4px' } : styles.aiSummaryPlaceholder}>
                          {result.executive_summary ? (
                            <div style={{ fontSize: 13, color: 'var(--text)', whiteSpace: 'pre-wrap', lineHeight: 1.6 }}>
                              {result.executive_summary}
                            </div>
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
  page: { minHeight: '100vh', display: 'flex', alignItems: 'flex-start', justifyContent: 'center', padding: '32px 16px', background: 'var(--navy)' },
  shell: { width: '100%', maxWidth: 1100, background: 'var(--navy2)', border: '0.5px solid var(--gold-border)', borderRadius: 'var(--radius-xl)', overflow: 'hidden' },
  header: { background: 'var(--navy)', padding: '18px 28px', borderBottom: '0.5px solid var(--gold-border)', display: 'flex', alignItems: 'center', justifyContent: 'space-between' },
  logo: { display: 'flex', alignItems: 'center', gap: 10 },
  logoIcon: { width: 34, height: 34, background: 'var(--gold)', borderRadius: 8, display: 'flex', alignItems: 'center', justifyContent: 'center' },
  body: { display: 'flex', minHeight: 600 },
  panelLeft: { width: 320, flexShrink: 0, borderRight: '0.5px solid var(--border)', padding: 24, display: 'flex', flexDirection: 'column' },
  panelRight: { flex: 1, padding: 28, display: 'flex', flexDirection: 'column', overflowY: 'auto', maxHeight: 'calc(100vh - 120px)' },
  emptyState: { flex: 1, display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', gap: 14, minHeight: 400 },
  reqItem: { display: 'flex', alignItems: 'center', gap: 8, background: 'var(--navy3)', border: '0.5px solid var(--border)', borderRadius: 6, padding: '7px 10px' },
  reqRemove: { background: 'none', border: 'none', cursor: 'pointer', color: 'var(--muted)', display: 'flex', alignItems: 'center', padding: 2, borderRadius: 4, marginLeft: 'auto' },
  leaderboardLink: { display: 'flex', alignItems: 'center', gap: 6, marginTop: 12, fontSize: 12, color: 'var(--slate)', justifyContent: 'center', textDecoration: 'none' },
  avatar: { width: 44, height: 44, borderRadius: '50%', background: 'rgba(201,168,76,0.15)', border: '1.5px solid var(--gold-dim)', display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 15, fontWeight: 500, color: 'var(--gold2)', flexShrink: 0 },
  scorePill: { background: 'rgba(201,168,76,0.10)', border: '1.5px solid var(--gold)', borderRadius: 12, padding: '10px 20px', textAlign: 'center', flexShrink: 0 },
  dimGrid: { display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(180px, 1fr))', gap: 8 },
  dimCard: { background: 'var(--navy3)', border: '0.5px solid var(--border)', borderRadius: 8, padding: '10px 12px' },
  dimCardPrimary: { background: 'rgba(201,168,76,0.06)', border: '0.5px solid var(--gold-dim)' },
  srcChipFound: { display: 'inline-flex', alignItems: 'center', gap: 5, padding: '5px 10px', borderRadius: 6, fontSize: 11, background: 'var(--green-bg)', border: '0.5px solid var(--green-border)', color: 'var(--green)', cursor: 'pointer', textDecoration: 'none' },
  srcChipMiss: { display: 'inline-flex', alignItems: 'center', gap: 5, padding: '5px 10px', borderRadius: 6, fontSize: 11, background: 'var(--border2)', border: '0.5px solid var(--border)', color: 'var(--muted)' },
  reasonBox: { background: 'var(--navy3)', border: '0.5px solid var(--border)', borderRadius: 8, padding: 14, fontSize: 12, color: 'var(--slate2)', lineHeight: 1.8, maxHeight: 180, overflowY: 'auto' },
  reasonItem: { padding: '4px 0', borderBottom: '0.5px solid var(--border2)' },
  dbGrid: { display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(230px, 1fr))', gap: '12px', marginBottom: '16px' },
  dbCard: { background: 'var(--navy3)', border: '0.5px solid var(--border)', borderRadius: '10px', padding: '14px', display: 'flex', flexDirection: 'column', justifyContent: 'space-between', minHeight: '140px' },
  dbCardHeader: { display: 'flex', justifyContent: 'space-between', alignItems: 'center', borderBottom: '0.5px solid var(--border2)', paddingBottom: '8px', marginBottom: '4px' },
  dbStatRow: { display: 'flex', justifyContent: 'space-around', alignItems: 'center', textAlign: 'center', background: 'rgba(255,255,255,0.02)', borderRadius: '6px', padding: '6px 0' },
  dbStatCol: { display: 'flex', flexDirection: 'column', alignItems: 'center' },
  dbStatVal: { fontSize: '18px', fontWeight: '600', color: 'var(--gold2)', lineHeight: '1.2' },
  dbStatLabel: { fontSize: '9.5px', color: 'var(--slate)', textTransform: 'uppercase', letterSpacing: '0.04em', marginTop: '2px' },
  dbSubLabel: { fontSize: '9.5px', color: 'var(--slate)', textTransform: 'uppercase', letterSpacing: '0.04em', marginBottom: '4px' },
  langBadge: { fontSize: '9.5px', background: 'var(--navy4)', border: '0.5px solid var(--border)', color: 'var(--slate2)', padding: '2px 6px', borderRadius: '4px' },
  interestBadge: { fontSize: '9.5px', background: 'rgba(201, 168, 76, 0.08)', border: '0.5px solid var(--gold-border)', color: 'var(--gold2)', padding: '2px 6px', borderRadius: '4px' },
  blogPlatformBadge: { fontSize: '9.5px', background: 'var(--border2)', border: '0.5px solid var(--border)', color: 'var(--slate2)', padding: '2px 6px', borderRadius: '4px' },
  dbCardEmpty: { fontSize: '11px', color: 'var(--muted)', textAlign: 'center', padding: '20px 10px', fontStyle: 'italic', flex: 1, display: 'flex', alignItems: 'center', justifyContent: 'center' },
  kwAlignmentBox: { background: 'var(--navy3)', border: '0.5px solid var(--border)', borderRadius: '10px', padding: '14px', marginBottom: '16px' },
  kwChip: { display: 'inline-flex', alignItems: 'center', gap: '4px', fontSize: '10.5px', padding: '3px 8px', borderRadius: '5px' },
  kwChipHit: { background: 'var(--green-bg)', border: '0.5px solid var(--green-border)', color: 'var(--green)' },
  kwChipMiss: { background: 'rgba(255,255,255,0.02)', border: '0.5px solid var(--border)', color: 'var(--muted)' },
  aiSummaryBox: { background: 'var(--navy3)', border: '0.5px solid var(--border)', borderRadius: '10px', padding: '16px' },
  aiSummaryIcon: { width: 36, height: 36, background: 'rgba(201,168,76,0.10)', border: '0.5px solid var(--gold-border)', borderRadius: 8, display: 'flex', alignItems: 'center', justifyContent: 'center', flexShrink: 0 },
  aiSummaryPlaceholder: { display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', padding: '24px 16px', borderRadius: 8, background: 'rgba(255,255,255,0.02)', border: '0.5px dashed var(--border)', minHeight: 110 },
}