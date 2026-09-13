import { useEffect, useState } from 'react'
import { SLICE_TYPE } from '@niivue/niivue'
import { Activity, ArrowDownToLine, ArrowRight, Box, Check, ChevronRight, Crosshair, FileUp, Files, GitFork, Layers3, LoaderCircle, RotateCcw, Scan, ShieldCheck, SlidersHorizontal, TriangleAlert, Upload, X } from 'lucide-react'
import VolumeViewer from './VolumeViewer'
import { branchColors } from './types'
import type { Analysis } from './types'
import './App.css'

const modes = [
  { label: 'Multiplanar', value: SLICE_TYPE.MULTIPLANAR },
  { label: 'Axial', value: SLICE_TYPE.AXIAL },
  { label: 'Coronal', value: SLICE_TYPE.CORONAL },
  { label: 'Sagittal', value: SLICE_TYPE.SAGITTAL },
  { label: '3D', value: SLICE_TYPE.RENDER },
]
const windows: Record<string, [number, number]> = { Angiography: [0, 500], 'Soft tissue': [-160, 240], Bone: [-500, 1500] }

function App() {
  useEffect(() => {
    const intro = document.getElementById('startup-screen')
    if (!intro) return
    // Let the logo finish once; slow bundle loads do not add another delay.
    const reducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches
    const delay = reducedMotion ? 0 : Math.max(0, 1800 - performance.now())
    const reveal = window.setTimeout(() => intro.classList.add('is-ready'), delay)
    const remove = window.setTimeout(() => {
      intro.remove()
      document.getElementById('root')?.removeAttribute('inert')
    }, delay + (reducedMotion ? 150 : 400))
    return () => { window.clearTimeout(reveal); window.clearTimeout(remove) }
  }, [])

  const [cases, setCases] = useState<string[]>([])
  const [caseId, setCaseId] = useState('subject002')
  const [source, setSource] = useState<'sample' | 'upload'>('sample')
  const [image, setImage] = useState<File | null>(null)
  const [mask, setMask] = useState<File | null>(null)
  const [analysis, setAnalysis] = useState<Analysis | null>(null)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const [caseError, setCaseError] = useState('')
  const [selected, setSelected] = useState(0)
  const [mode, setMode] = useState(SLICE_TYPE.MULTIPLANAR)
  const [aortaOpacity, setAortaOpacity] = useState(0.28)
  const [showBranches, setShowBranches] = useState(true)
  const [preset, setPreset] = useState('Angiography')
  const [reset, setReset] = useState(0)
  const [help, setHelp] = useState(false)
  const [ctOpacity, setCtOpacity] = useState(1)
  const [clip, setClip] = useState({ enabled: false, depth: 0, axis: 'Coronal' })

  useEffect(() => {
    let cancelled = false
    fetch('/api/cases')
      .then(response => { if (!response.ok) throw new Error(); return response.json() })
      .then((data: { cases: string[] }) => {
        if (cancelled) return
        setCases(data.cases)
        setCaseId(data.cases.includes('subject002') ? 'subject002' : data.cases[0] || '')
      })
      .catch(() => { if (!cancelled) setCaseError('Could not reach the local analysis service. Refresh once it is running.') })
    return () => { cancelled = true }
  }, [])

  async function analyze() {
    if (busy) return
    setBusy(true)
    setError('')
    const form = new FormData()
    if (source === 'sample') form.set('case_id', caseId)
    else {
      if (!image || !mask) { setBusy(false); return }
      form.set('image', image)
      form.set('mask', mask)
    }
    try {
      const response = await fetch('/api/analyze', { method: 'POST', body: form })
      const data = await response.json()
      if (!response.ok) throw new Error(data.error || 'Analysis failed. Check the image and mask.')
      setAnalysis(data)
      setSelected(0)
      setMode(SLICE_TYPE.MULTIPLANAR)
      setShowBranches(true)
      setAortaOpacity(0.28)
      setPreset('Angiography')
      setCtOpacity(1)
      setClip({ enabled: false, depth: 0, axis: 'Coronal' })
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : 'Could not complete the analysis.')
    } finally { setBusy(false) }
  }

  const branch = analysis?.daughters[selected]
  const pathLength = branch?.centerline_points_mm.slice(1).reduce((length, point, i) =>
    length + Math.hypot(...point.map((value, axis) => value - branch.centerline_points_mm[i][axis])), 0)
  const canRun = source === 'sample' ? cases.includes(caseId) : Boolean(image && mask)

  return (
    <div className="app-shell">
      <header className="app-header">
        <a className="brand" href="/" aria-label="BranchSeed home"><span className="brand-mark"><GitFork size={24} strokeWidth={2.1} /></span>BranchSeed<span className="brand-dot">.</span></a>
        <div className="header-divider" />
        <span className="header-context">Vascular workspace</span>
        <div className="header-right"><span className="local-status"><i /> Local analysis</span><button className="help-button" onClick={() => setHelp(true)}>Quick guide <ChevronRight size={14} /></button><span className="avatar">BS</span></div>
      </header>

      <div className="workspace-heading">
        <div><div className="eyebrow">WORKSPACE <ChevronRight size={11} /> DAUGHTER VESSEL ANALYSIS</div><h1>See where every branch begins.</h1><p>Explore the aorta. Follow its daughters. Review the geometry.</p></div>
        <span className="research-badge"><Activity size={14} /> Research prototype</span>
      </div>

      <main className="workspace-grid">
        <aside className="source-panel">
          <div className="panel-heading"><span className="section-icon"><Files size={17} /></span><h2>Case input</h2><span className="step-number">01</span></div>
          <div className="source-tabs"><button className={source === 'sample' ? 'active' : ''} disabled={busy} onClick={() => setSource('sample')}>Sample cases</button><button className={source === 'upload' ? 'active' : ''} disabled={busy} onClick={() => setSource('upload')}>Upload files</button></div>
          {source === 'sample' ? <div className="input-content">
            <label className="field-label" htmlFor="case-select">SELECT A CASE <span>{cases.length} available</span></label>
            <select id="case-select" value={caseId} disabled={busy || !cases.length} onChange={event => setCaseId(event.target.value)}>
              {!cases.length && <option value="">No cases loaded</option>}
              {cases.map(id => <option key={id} value={id}>{id}</option>)}
            </select>
            <div className="file-card"><span className="file-icon"><Scan size={18} /></span><div><strong>CT angiogram</strong><small>{caseId ? 'orig' + Number(caseId.slice(7)) + '.nii' : 'Select a case'}</small></div><Check className="file-check" size={15} /></div>
            <div className="file-card"><span className="file-icon mint"><Layers3 size={18} /></span><div><strong>Aorta mask</strong><small>{caseId ? 'mask' + Number(caseId.slice(7)) + '.nii' : 'Select a case'}</small></div><Check className="file-check" size={15} /></div>
            {caseError && <p className="inline-error">{caseError}</p>}
          </div> : <div className="input-content">
            {([{ label: 'CT angiogram', file: image, set: setImage }, { label: 'Aorta mask', file: mask, set: setMask }]).map(input => <label className={'upload-field ' + (input.file ? 'has-file' : '')} key={input.label}>
              {input.file ? <Check size={21} /> : <FileUp size={22} />}
              <strong>{input.label}</strong><span>{input.file ? input.file.name : 'Choose a .nii or .nii.gz file'}</span>
              <input type="file" aria-label={input.label} accept=".nii,.nii.gz" disabled={busy} onChange={event => input.set(event.target.files?.[0] || null)} />
            </label>)}
            <p className="input-note">CT and mask must share the same spatial grid.</p>
          </div>}
          <button className="primary-button run-button" disabled={!canRun || busy} onClick={() => void analyze()}>
            {busy ? <LoaderCircle size={17} className="spin" /> : <Activity size={17} />}{busy ? 'Analyzing scan…' : 'Run analysis'}{!busy && <ArrowRight size={17} />}
          </button>
          <div className="processing-note"><ShieldCheck size={14} /><span>Processed on your local machine.</span></div>
          <div className="panel-rule" />
          <div className="panel-heading"><span className="section-icon"><SlidersHorizontal size={17} /></span><h2>Display controls</h2></div>
          <label className="field-label" htmlFor="window-preset">CT WINDOW</label>
          <select id="window-preset" disabled={!analysis} value={preset} onChange={event => setPreset(event.target.value)}>{Object.keys(windows).map(value => <option key={value}>{value}</option>)}</select>
          <div className="window-values"><span>Level <b>{(windows[preset][0] + windows[preset][1]) / 2}</b></span><span>Width <b>{windows[preset][1] - windows[preset][0]}</b></span><small>HU</small></div>
          <div className="layer-control"><span><i className="color-swatch aorta-color" /> Aorta overlay</span><output>{Math.round(aortaOpacity * 100)}%</output></div>
          <input className="opacity-slider" type="range" aria-label="Aorta overlay opacity" min="0" max="0.7" step="0.01" disabled={!analysis} value={aortaOpacity} onChange={event => setAortaOpacity(Number(event.target.value))} />
          <label className="layer-control branch-switch"><span><i className="color-swatch branch-color" /> Traced branches</span><input type="checkbox" disabled={!analysis} checked={showBranches} onChange={event => setShowBranches(event.target.checked)} /><span className="switch-track" /></label>
          <div className="sidebar-tip"><Crosshair size={17} /><p>Select a branch to jump to its origin in every slice.</p></div>
          <div className="panel-rule" />
          <div className="panel-heading"><span className="section-icon"><Box size={17} /></span><h2>Explore anatomy</h2></div>
          <div className="explore-buttons">
            <button disabled={!analysis} onClick={() => { setShowBranches(true); setCtOpacity(0); setAortaOpacity(0.45); setMode(SLICE_TYPE.RENDER); setClip(value => ({ ...value, enabled: false })) }}>Vessel focus</button>
            <button disabled={!analysis} onClick={() => { setShowBranches(false); setAortaOpacity(0); setCtOpacity(1); setMode(SLICE_TYPE.MULTIPLANAR); setClip(value => ({ ...value, enabled: false })) }}>Inspect raw CT</button>
          </div>
          <div className="layer-control"><span>CT opacity</span><output>{Math.round(ctOpacity * 100)}%</output></div>
          <input className="opacity-slider" type="range" aria-label="CT opacity" min="0" max="1" step="0.05" disabled={!analysis} value={ctOpacity} onChange={event => setCtOpacity(Number(event.target.value))} />
          <label className="layer-control branch-switch"><span>3D clipping plane</span><input type="checkbox" disabled={!analysis} checked={clip.enabled} onChange={event => { setClip(value => ({ ...value, enabled: event.target.checked })); if (event.target.checked) setMode(SLICE_TYPE.RENDER) }} /><span className="switch-track" /></label>
          {clip.enabled && <div className="clip-controls">
            <label className="field-label" htmlFor="clip-axis">CUT DIRECTION</label>
            <select id="clip-axis" value={clip.axis} onChange={event => setClip(value => ({ ...value, axis: event.target.value }))}>{['Coronal', 'Sagittal', 'Axial'].map(axis => <option key={axis}>{axis}</option>)}</select>
            <label className="field-label clip-depth-label" htmlFor="clip-depth">PLANE POSITION <span>{clip.depth.toFixed(2)}</span></label>
            <input id="clip-depth" className="opacity-slider" type="range" min="-1" max="1" step="0.02" value={clip.depth} onChange={event => setClip(value => ({ ...value, depth: Number(event.target.value) }))} />
            <p className="explore-note">Move the plane with this slider. The wheel zooms the 3D view.</p>
          </div>}
          <p className="explore-note">Explore the original CT intensities, cropped around the aorta. Clipping reveals structures outside the detected branches. Unlabelled anatomy is not classified.</p>
        </aside>

        <section className="scan-panel">
          <div className="scan-heading"><div className="scan-title"><span className="scan-icon"><Scan size={20} /></span><div><h2>{analysis?.case_id || 'Your scan workspace'}</h2><span>{analysis ? 'Abdominal aorta · CT angiography' : 'Three dimensions. One clear picture.'}</span></div></div><span className={'scan-status ' + (analysis ? 'is-ready' : '')}><i />{busy ? 'Analyzing' : analysis ? 'Ready to explore' : 'Awaiting scan'}</span></div>
          {error && <div role="alert" className="error-banner"><TriangleAlert size={18} /><div><strong>Could not analyze this case</strong><p>{error}</p>{analysis && <small>Previous scan remains displayed.</small>}</div><button aria-label="Dismiss error" onClick={() => setError('')}><X size={16} /></button></div>}
          <div className="viewer-toolbar"><div className="view-tabs">{modes.map(item => <button key={item.value} disabled={!analysis} className={mode === item.value ? 'active' : ''} onClick={() => setMode(item.value)}>{item.value === SLICE_TYPE.RENDER && <Box size={13} />}{item.label}</button>)}</div><button className="reset-button" title="Reset zoom and rotation" aria-label="Reset view" disabled={!analysis} onClick={() => setReset(value => value + 1)}><RotateCcw size={15} /></button></div>
          <div className="viewer-stage">
            {analysis ? <VolumeViewer key={analysis.assets.ct} analysis={analysis} selected={selected} mode={mode} aortaOpacity={aortaOpacity} showBranches={showBranches} window={windows[preset]} reset={reset} ctOpacity={ctOpacity} clip={clip} /> : <div className="empty-viewer">
              <div className="scan-grid"><div className="scan-orbit"><Scan size={49} strokeWidth={1} /><span className="orbit-point" /></div></div>
              <span className="viewer-eyebrow">AORTIC BRANCH EXPLORER</span><h2>Anatomy, in perspective.</h2><p>Load a case to explore aligned CT slices,<br />aorta segmentation, and daughter centerlines.</p>
              <button className="viewer-start" disabled={!canRun || busy} onClick={() => void analyze()}>{busy ? <LoaderCircle className="spin" size={16} /> : <Scan size={16} />}{source === 'sample' ? 'Explore ' + caseId : 'Analyze uploaded scan'}<ArrowRight size={15} /></button>
            </div>}
            {busy && analysis && <div className="analysis-overlay"><LoaderCircle className="spin" size={25} /><strong>Tracing daughter vessels</strong><span>Processing the selected scan…</span></div>}
          </div>
          <div className="viewer-footer"><span><span className="live-dot" /> {analysis ? 'NiiVue · linked views' : 'NiiVue · 3D ready'}</span><span>{mode === SLICE_TYPE.RENDER ? 'Drag to orbit · Wheel / W S zoom · A D orbit · Q E tilt · R reset' : 'Scroll to slice · Drag to navigate · Right-drag for contrast'}</span></div>
          <div className="scan-metadata"><div><span>VOLUME</span><strong>{analysis ? analysis.size.join(' × ') : '—'}<small>{analysis && ' voxels'}</small></strong></div><div><span>VOXEL SPACING</span><strong>{analysis ? analysis.spacing.map(value => value.toFixed(2)).join(' × ') : '—'}<small>{analysis && ' mm'}</small></strong></div><div><span>ANALYSIS TIME</span><strong>{analysis ? analysis.runtime_seconds.toFixed(2) : '—'}<small>{analysis && ' sec'}</small></strong></div></div>
        </section>

        <aside className="results-panel">
          <div className="panel-heading"><span className="section-icon"><GitFork size={18} /></span><h2>Daughter vessels</h2><span className="count-pill">{analysis?.daughters.length ?? '—'}</span></div>
          <p className="panel-subtitle">{analysis ? 'Traced from the parent aorta' : 'Your detected branches will appear here'}</p>
          {!analysis ? <div className="empty-results"><div className="branch-illustration"><GitFork size={41} strokeWidth={1.2} /></div><strong>Follow every origin.</strong><p>Review each vessel’s seed,<br />radius, and initial direction.</p><div className="empty-result-row" /><div className="empty-result-row short" /><div className="empty-result-row" /></div> : !analysis.daughters.length ? <div className="empty-results"><Scan size={30} /><strong>No eligible branches found</strong><p>No candidate met the tracing criteria. Review the scan and mask.</p></div> : <div className="branch-list">{analysis.daughters.map((daughter, i) => <button key={daughter.instance_id} className={'branch-card ' + (selected === i ? 'selected' : '')} aria-pressed={selected === i} onClick={() => setSelected(i)}><span className="branch-dot" style={{ background: branchColors[i % branchColors.length] }} /><div><strong>{daughter.instance_id}</strong><span>Parent: aorta</span></div><div className="branch-radius"><strong>{daughter.radius_mm.toFixed(2)} <small>mm</small></strong><span>radius</span></div><Crosshair size={15} /></button>)}</div>}
          {branch && <div className="branch-detail">
            <div className="detail-heading"><span>BRANCH GEOMETRY</span><Crosshair size={14} /></div>
            <div className="geometry-stats"><div><strong>{branch.radius_mm.toFixed(2)}<small>mm</small></strong><span>Lumen radius</span></div><div><strong>{pathLength?.toFixed(1)}<small>mm</small></strong><span>Traced length</span></div></div>
            <div className="coordinate-heading"><span>PHYSICAL COORDINATES</span><span>LPS · mm</span></div>
            <div className="coordinate-table"><span /><span>X</span><span>Y</span><span>Z</span><strong>Origin</strong>{branch.ostium_xyz_mm.map((value, i) => <span key={'o' + i}>{value.toFixed(1)}</span>)}<strong>5 mm seed</strong>{branch.seed_xyz_mm.map((value, i) => <span key={'s' + i}>{value.toFixed(1)}</span>)}</div>
            <div className="direction-row"><span>Direction</span><code>{branch.direction_xyz.map(value => value.toFixed(2)).join(', ')}</code></div>
            <p className="geometry-note">Sphere: measured radius at the 5 mm seed.<br />Centerline width is enlarged for visibility.</p>
          </div>}
          <div className="results-bottom">{analysis ? <a className="export-button" href={analysis.assets.prediction} download><ArrowDownToLine size={17} />Export prediction<small>JSON</small></a> : <button className="export-button" disabled><ArrowDownToLine size={17} />Export prediction<small>JSON</small></button>}<p>Algorithm-generated results.<br />Review against the source images.</p></div>
        </aside>
      </main>

      <footer className="app-footer"><span>BRANCHSEED <span className="footer-slash">/</span> From image to insight.</span><span><span className="legend-dot" /> Parent aorta <span className="legend-dot peach" /> Daughter vessels</span></footer>
      {help && <div className="modal-backdrop" onClick={() => setHelp(false)}><section className="help-dialog" role="dialog" aria-modal="true" aria-labelledby="help-title" onClick={event => event.stopPropagation()}><button autoFocus className="dialog-close" onClick={() => setHelp(false)} aria-label="Close guide"><X size={19} /></button><span className="section-icon"><Scan size={23} /></span><h2 id="help-title">A quick look around.</h2><p>Choose a sample case or upload a CT and binary aorta mask. Run analysis to load the viewer.</p><div><Upload size={19} /><p><strong>Start with a matching pair.</strong><br />Both NIfTI files need the same grid and physical geometry.</p></div><div><Layers3 size={19} /><p><strong>Explore the layers.</strong><br />Switch views, scroll through slices, and adjust the green aorta overlay.</p></div><div><Crosshair size={19} /><p><strong>Inspect a daughter.</strong><br />Click a branch to center all slices on its origin. Export its physical geometry as JSON.</p></div><button className="primary-button" onClick={() => setHelp(false)}>Got it <Check size={16} /></button></section></div>}
    </div>
  )
}

export default App
