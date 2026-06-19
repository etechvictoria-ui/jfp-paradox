import { app, BrowserWindow, ipcMain } from 'electron'
import path from 'path'
import { fileURLToPath } from 'url'
import { spawn } from 'child_process'
import os from 'os'

const __filename = fileURLToPath(import.meta.url)
const __dirname = path.dirname(__filename)

let mainWindow
let daemonProcess = null

function createWindow() {
  mainWindow = new BrowserWindow({
    width: 1400,
    height: 900,
    minWidth: 1000,
    minHeight: 600,
    webPreferences: {
      preload: path.join(__dirname, 'preload.js'),
      contextIsolation: true,
      enableRemoteModule: false,
    },
    icon: path.join(__dirname, '../assets/icon.png'),
  })

  const isDev = process.env.NODE_ENV === 'development'
  const url = isDev ? 'http://localhost:5173' : `file://${path.join(__dirname, '../dist/index.html')}`

  mainWindow.loadURL(url)

  if (isDev) {
    mainWindow.webContents.openDevTools()
  }

  mainWindow.on('closed', () => {
    mainWindow = null
    if (daemonProcess) {
      daemonProcess.kill()
    }
  })
}

function startDaemon() {
  // Start jfpd daemon
  const daemonScript = path.join(__dirname, '../daemon/jfpd.py')
  
  process.env.JFP_DRY_RUN = '1'
  process.env.JFP_LOG_PATH = path.join(os.homedir(), '.jfp_paradox/proof.jsonl')
  process.env.JFP_SOCKET_PATH = path.join(os.homedir(), '.jfp_paradox/jfpd.sock')
  
  daemonProcess = spawn('python3', [daemonScript], {
    env: process.env,
  })

  daemonProcess.stdout.on('data', (data) => {
    console.log(`[daemon] ${data}`)
  })

  daemonProcess.stderr.on('data', (data) => {
    console.error(`[daemon error] ${data}`)
  })

  daemonProcess.on('close', (code) => {
    console.log(`Daemon exited with code ${code}`)
  })
}

app.on('ready', () => {
  createWindow()
  startDaemon()
})

app.on('window-all-closed', () => {
  if (process.platform !== 'darwin') {
    app.quit()
  }
})

app.on('activate', () => {
  if (mainWindow === null) {
    createWindow()
  }
})

// IPC handlers
ipcMain.handle('ping', () => 'pong')

ipcMain.handle('get-app-version', () => app.getVersion())

ipcMain.handle('get-daemon-status', () => {
  return {
    running: daemonProcess !== null,
    pid: daemonProcess?.pid || null,
  }
})
