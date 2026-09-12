export type Daughter = {
  instance_id: string
  parent_instance_id: string
  ostium_xyz_mm: [number, number, number]
  seed_xyz_mm: [number, number, number]
  direction_xyz: [number, number, number]
  radius_mm: number
  centerline_points_mm: [number, number, number][]
}

export type Analysis = {
  case_id: string
  daughters: Daughter[]
  runtime_seconds: number
  size: [number, number, number]
  spacing: [number, number, number]
  coordinate_system: 'LPS'
  assets: { ct: string; aorta: string; branches: string; prediction: string }
}

export const branchColors = ['#ffba80', '#a7b1ff', '#ff829b', '#86d5ec', '#e1cf75', '#c393df']
