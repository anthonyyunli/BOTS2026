import { useEffect, useRef, useState } from 'react'
import { Niivue, MULTIPLANAR_TYPE, SHOW_RENDER, SLICE_TYPE } from '@niivue/niivue'
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
}

export default function VolumeViewer(props: Props) {
  const { analysis, selected, mode, aortaOpacity, showBranches, window: intensityWindow, reset } = props
  const canvas = useRef<HTMLCanvasElement>(null)
  const viewer = useRef<Niivue | null>(null)
  const [ready, setReady] = useState(false)
  const [error, setError] = useState('')

  useEffect(() => {
    if (!canvas.current) return
    let cancelled = false
    const nv = new Niivue({
      backColor: [0.039, 0.059, 0.075, 1],
      crosshairColor: [0.42, 0.82, 0.70, 0.8],
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
    })
    viewer.current = nv
    const target = canvas.current
    async function load() {
      try {
        await nv.attachToCanvas(target)
        if (cancelled) return
        await nv.loadVolumes([
          { url: analysis.assets.ct, name: 'CT angiogram', colormap: 'gray', cal_min: 0, cal_max: 500 },
          { url: analysis.assets.aorta, name: 'Parent aorta', colormap: 'green', opacity: 0.28, cal_min: 0, cal_max: 1 },
          { url: analysis.assets.branches, name: 'Daughter centerlines', colormap: 'warm', opacity: 1 },
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
    if (!ready || !viewer.current) return
    const nv = viewer.current
    nv.setOpacity(1, aortaOpacity)
    nv.setOpacity(2, showBranches ? 1 : 0)
    nv.volumes[0].cal_min = intensityWindow[0]
    nv.volumes[0].cal_max = intensityWindow[1]
    nv.updateGLVolume()
  }, [ready, aortaOpacity, showBranches, intensityWindow])

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
    <canvas ref={canvas} aria-label="NiiVue medical image canvas" />
    {!ready && !error && <div className="viewer-message"><LoaderCircle className="spin" size={28} /><strong>Preparing your scan</strong><span>Loading CT and aligned vessel layers…</span></div>}
    {error && <div className="viewer-message"><TriangleAlert size={28} /><strong>Viewer unavailable</strong><span>{error}</span><small>This viewer needs WebGL2 enabled in your browser.</small></div>}
  </div>
}
