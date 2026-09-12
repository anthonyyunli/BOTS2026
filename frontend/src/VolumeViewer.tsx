import { useEffect, useRef, useState } from 'react'
import { Niivue, MULTIPLANAR_TYPE, SHOW_RENDER, SLICE_TYPE } from '@niivue/niivue'
import type { NVConnectomeEdge, NVConnectomeNode } from '@niivue/niivue'
import { LoaderCircle, TriangleAlert } from 'lucide-react'
import { branchColors } from './types'
import type { Analysis } from './types'

type Props = {
  analysis: Analysis
  selected: number
  mode: SLICE_TYPE
  aortaOpacity: number
  showBranches: boolean
  window: [number, number]
  reset: number
  ctOpacity: number
  clip: { enabled: boolean; depth: number; axis: string }
}

export default function VolumeViewer(props: Props) {
  const { analysis, selected, mode, aortaOpacity, showBranches, window: intensityWindow, reset, ctOpacity, clip } = props
  const canvas = useRef<HTMLCanvasElement>(null)
  const viewer = useRef<Niivue | null>(null)
  const [ready, setReady] = useState(false)
  const [error, setError] = useState('')

  useEffect(() => {
    if (!canvas.current) return
    setReady(false)
    setError('')
    let cancelled = false
    const nv = new Niivue({
      backColor: [0.039, 0.059, 0.075, 1],
      crosshairColor: [0.42, 0.82, 0.70, 0.8],
      clipPlaneColor: [0.42, 0.82, 0.70, 0.08],
      fontColor: [0.6, 0.67, 0.7, 1],
      textHeight: 0.018,
      crosshairWidth: 1,
      isColorbar: false,
      isOrientCube: true,
      isCornerOrientationText: true,
      isRadiologicalConvention: true,
      multiplanarShowRender: SHOW_RENDER.ALWAYS,
      multiplanarLayout: MULTIPLANAR_TYPE.GRID,
      multiplanarEqualSize: true,
      multiplanarPadPixels: 14,
      dragAndDropEnabled: false,
      logLevel: 'error',
      meshXRay: 0.35,
      meshThicknessOn2D: 1.0,
      showLegend: false,
    })
    viewer.current = nv
    const target = canvas.current
    async function load() {
      try {
        await nv.attachToCanvas(target)
        if (cancelled) return
        await nv.loadVolumes([
          { url: analysis.assets.ct, name: 'ct.nii.gz', colormap: 'gray', cal_min: 0, cal_max: 500 },
          { url: analysis.assets.aorta, name: 'aorta.nii.gz', colormap: 'green', opacity: 0.28, cal_min: 0, cal_max: 1 },
          { url: analysis.assets.branches, name: 'branches.nii.gz', colormap: 'warm', opacity: 1 },
        ])
        if (cancelled) return
        nv.volumes[1].setColormapLabel({ R: [0, 105], G: [0, 216], B: [0, 181], A: [0, 255], I: [0, 1] })
        const colors = analysis.daughters.map((_, i) => branchColors[i % branchColors.length])
        const rgb = colors.map(color => [1, 3, 5].map(start => parseInt(color.slice(start, start + 2), 16)))
        if (rgb.length) nv.volumes[2].setColormapLabel({
          R: [0, ...rgb.map(c => c[0])], G: [0, ...rgb.map(c => c[1])],
          B: [0, ...rgb.map(c => c[2])], A: [0, ...rgb.map(() => 255)],
          I: [0, ...rgb.map((_, i) => i + 1)],
        })
        nv.updateGLVolume()
        setReady(true)
      } catch (cause) {
        if (!cancelled) setError(cause instanceof Error ? cause.message : 'Could not load the scan.')
      }
    }
    void load()
    return () => { cancelled = true; viewer.current = null; nv.cleanup() }
  }, [analysis])

  useEffect(() => {
    if (!ready || !viewer.current) return
    viewer.current.setSliceType(mode)
  }, [ready, mode])

  useEffect(() => {
    if (!ready || !viewer.current || !canvas.current) return
    const nv = viewer.current
    const target = canvas.current
    function zoom(factor: number) {
      nv.setScale(Math.min(8, Math.max(0.25, nv.scene.volScaleMultiplier * factor)))
    }
    function wheel(event: WheelEvent) {
      const bounds = target.getBoundingClientRect()
      const x = (event.clientX - bounds.left) * target.width / bounds.width
      const y = (event.clientY - bounds.top) * target.height / bounds.height
      if (nv.inRenderTile(x, y) < 0) return
      // NiiVue otherwise moves an active clipping plane instead of zooming.
      event.preventDefault()
      event.stopImmediatePropagation()
      target.focus({ preventScroll: true })
      const pixels = event.deltaY * (event.deltaMode === 1 ? 16 : event.deltaMode === 2 ? bounds.height : 1)
      zoom(Math.exp(-Math.max(-200, Math.min(200, pixels)) * 0.001))
    }
    function keydown(event: KeyboardEvent) {
      if (nv.opts.sliceType !== SLICE_TYPE.RENDER || event.ctrlKey || event.metaKey || event.altKey) return
      if (!['KeyW', 'KeyA', 'KeyS', 'KeyD', 'KeyQ', 'KeyE', 'KeyR'].includes(event.code)) return
      event.preventDefault()
      event.stopImmediatePropagation()
      const step = event.shiftKey ? 6 : 3
      switch (event.code) {
        case 'KeyW': zoom(1.06); break
        case 'KeyS': zoom(1 / 1.06); break
        case 'KeyA': nv.setRenderAzimuthElevation(nv.scene.renderAzimuth - step, nv.scene.renderElevation); break
        case 'KeyD': nv.setRenderAzimuthElevation(nv.scene.renderAzimuth + step, nv.scene.renderElevation); break
        case 'KeyQ': nv.setRenderAzimuthElevation(nv.scene.renderAzimuth, Math.min(89, nv.scene.renderElevation + step)); break
        case 'KeyE': nv.setRenderAzimuthElevation(nv.scene.renderAzimuth, Math.max(-89, nv.scene.renderElevation - step)); break
        case 'KeyR': nv.setScale(1); nv.setRenderAzimuthElevation(110, 10); break
      }
    }
    target.addEventListener('wheel', wheel, { capture: true, passive: false })
    target.addEventListener('keydown', keydown, true)
    return () => {
      target.removeEventListener('wheel', wheel, true)
      target.removeEventListener('keydown', keydown, true)
    }
  }, [ready])

  useEffect(() => {
    if (!ready || !viewer.current) return
    const nv = viewer.current
    nv.setOpacity(1, aortaOpacity)
    nv.setOpacity(0, ctOpacity)
    nv.setOpacity(2, showBranches ? 1 : 0)
    nv.volumes[0].cal_min = intensityWindow[0]
    nv.volumes[0].cal_max = intensityWindow[1]
    nv.updateGLVolume()
  }, [ready, aortaOpacity, showBranches, intensityWindow, ctOpacity])

  useEffect(() => {
    if (!ready || !viewer.current) return
    const nv = viewer.current
    for (const mesh of [...nv.meshes]) nv.removeMesh(mesh)
    if (!showBranches) return
    analysis.daughters.forEach((daughter, i) => {
      const color = branchColors[i % branchColors.length]
      const rgb = [1, 3, 5].map(start => parseInt(color.slice(start, start + 2), 16))
      const colormap = 'branch-' + i
      nv.addColormap(colormap, { R: [rgb[0], rgb[0]], G: [rgb[1], rgb[1]], B: [rgb[2], rgb[2]], A: [255, 255], I: [0, 255] })
      const nodes: NVConnectomeNode[] = daughter.centerline_points_mm.map((point, pointIndex) => ({
        name: daughter.instance_id, x: -point[0], y: -point[1], z: point[2],
        colorValue: 1, sizeValue: pointIndex === 0 ? 1.3 : 0,
      }))
      const edges: NVConnectomeEdge[] = nodes.slice(1).map((_, index) => ({ first: index, second: index + 1, colorValue: 1 }))
      const [x, y, z] = daughter.seed_xyz_mm
      // Radius is measured by geometry.py. Tube widths are display emphasis only.
      nodes.push({ name: daughter.instance_id + ' · 5 mm seed', x: -x, y: -y, z, colorValue: 1, sizeValue: daughter.radius_mm })
      nv.addMesh(nv.loadConnectomeAsMesh({
        name: daughter.instance_id, nodes, edges,
        nodeColormap: colormap, nodeColormapNegative: colormap, nodeMinColor: 0, nodeMaxColor: 1, nodeScale: 1,
        edgeColormap: colormap, edgeColormapNegative: colormap, edgeMin: 0, edgeMax: 1,
        edgeScale: i === selected ? 1.0 : 0.65, showLegend: false,
      }))
    })
    nv.drawScene()
  }, [ready, analysis, selected, showBranches])

  useEffect(() => {
    if (!ready || !viewer.current) return
    const angles: Record<string, [number, number]> = { Coronal: [0, 0], Sagittal: [90, 0], Axial: [0, 90] }
    viewer.current.setClipPlane([clip.enabled ? clip.depth : 3, ...angles[clip.axis]])
  }, [ready, clip])

  useEffect(() => {
    if (!ready || !viewer.current) return
    const nv = viewer.current
    const branch = analysis.daughters[selected]
    if (branch) {
      // SimpleITK uses LPS; NiiVue's world coordinates are RAS.
      const [left, posterior, superior] = branch.ostium_xyz_mm
      nv.scene.crosshairPos = nv.mm2frac([-left, -posterior, superior])
    }
    nv.drawScene()
  }, [ready, analysis, selected])

  useEffect(() => {
    if (!ready || !viewer.current || !reset) return
    const nv = viewer.current
    nv.scene.pan2Dxyzmm = [0, 0, 0, 1]
    nv.setScale(1)
    nv.setRenderAzimuthElevation(110, 10)
    nv.drawScene()
  }, [ready, reset])

  return <div className="volume-canvas" aria-label="Interactive CT and vessel viewer" aria-busy={!ready && !error}>
    <canvas ref={canvas} tabIndex={0} aria-label="NiiVue medical image canvas" />
    {!ready && !error && <div className="viewer-message"><LoaderCircle className="spin" size={28} /><strong>Preparing your scan</strong><span>Loading CT and aligned vessel layers…</span></div>}
    {error && <div className="viewer-message"><TriangleAlert size={28} /><strong>Viewer unavailable</strong><span>{error}</span><small>Reload the scan to try again.</small></div>}
  </div>
}
