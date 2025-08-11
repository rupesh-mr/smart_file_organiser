const { app, BrowserWindow, ipcMain } = require('electron');
const path = require('path');
const sqlite3 = require('sqlite3').verbose();

const dbPath = path.join(__dirname, "..", 'file_logs.db');
const db = new sqlite3.Database(dbPath);
console.log(`✅ Database connected at ${dbPath}`);

function createWindow() {
  const win = new BrowserWindow({
    width: 1000,
    height: 700,
    resizable: true,
    webPreferences: {
      nodeIntegration: true,
      contextIsolation: false,
    },
  });

  win.loadFile('index.html');
}

app.whenReady().then(createWindow);

ipcMain.handle('get-logs', async (event, { search, category }) => {
  return new Promise((resolve, reject) => {
    let query = `SELECT * FROM files WHERE 1=1`;
    const params = [];

    if (search) {
      query += ` AND (filename LIKE ? OR summary LIKE ?)`;
      params.push(`%${search}%`, `%${search}%`);
    }

    if (category) {
      query += ` AND category = ?`;
      params.push(category);
    }

    console.log('📦 Running DB query with params:', params);
    db.all(query + ' ORDER BY timestamp DESC', params, (err, rows) => {
      if (err) reject(err);
      else resolve(rows);
    });
  });
});
