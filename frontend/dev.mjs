import { spawn } from 'node:child_process'
import { fileURLToPath } from 'node:url'
import { createServer } from 'vite'

const root = fileURLToPath(new URL('../', import.meta.url))
let api
let vite

async function apiReady() {
  try {
    const response = await fetch('http://127.0.0.1:8000/api/cases', { signal: AbortSignal.timeout(800) })
    return response.ok && Array.isArray((await response.json()).cases)
  } catch { return false }
}

async function shutdown() {
  api?.kill('SIGTERM')
  await vite?.close()
}
process.once('SIGINT', () => { void shutdown().then(() => process.exit(0)) })
process.once('SIGTERM', () => { void shutdown().then(() => process.exit(0)) })

try {
  if (!await apiReady()) {
    api = spawn(root + '.env/bin/python', ['-m', 'uvicorn', 'web.api:app', '--host', '127.0.0.1', '--port', '8000'], {
      cwd: root, stdio: 'inherit',
    })
    let failure
    api.on('error', error => { failure = error })
    let ready = false
    for (let attempt = 0; attempt < 50; attempt++) {
      if (failure) throw failure
      if (api.exitCode !== null) throw new Error('Python API exited. Check the error above.')
      if (await apiReady()) { ready = true; break }
      await new Promise(resolve => setTimeout(resolve, 200))
    }
    if (!ready) throw new Error('Python API did not start on port 8000.')
  }
  vite = await createServer({ server: { host: '127.0.0.1' } })
  await vite.listen()
  vite.printUrls()
  console.log('BranchSeed API ready at http://127.0.0.1:8000')
} catch (error) {
  console.error(error.message)
  console.error('Install Python dependencies with: .env/bin/python -m pip install -r requirements.txt (from the project root).')
  await shutdown()
  process.exitCode = 1
}
