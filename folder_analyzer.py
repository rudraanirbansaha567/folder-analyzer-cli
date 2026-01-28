from fastapi import FastAPI, File, UploadFile, Form
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
import os
import tempfile
import shutil
from collections import defaultdict
import uvicorn

app = FastAPI()

# Enable CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

def human_size(bytes_size):
    for unit in ["B", "KB", "MB", "GB"]:
        if bytes_size < 1024.0:
            return f"{bytes_size:.2f} {unit}"
        bytes_size /= 1024.0
    return f"{bytes_size:.2f} GB"

@app.get("/")
async def home():
    """Serve a simple HTML page with folder upload"""
    html_content = """
    <!DOCTYPE html>
    <html>
    <head>
        <title>Folder Analyzer - IT WORKS!</title>
        <style>
            body {
                font-family: Arial, sans-serif;
                max-width: 800px;
                margin: 40px auto;
                padding: 20px;
                background: #f5f5f5;
            }
            .container {
                background: white;
                padding: 30px;
                border-radius: 10px;
                box-shadow: 0 2px 10px rgba(0,0,0,0.1);
            }
            h1 {
                color: #333;
                border-bottom: 2px solid #4CAF50;
                padding-bottom: 10px;
            }
            .upload-area {
                border: 3px dashed #4CAF50;
                border-radius: 10px;
                padding: 40px;
                text-align: center;
                margin: 20px 0;
                background: #f9f9f9;
                cursor: pointer;
            }
            .upload-area:hover {
                background: #f0f0f0;
                border-color: #45a049;
            }
            button {
                background: #4CAF50;
                color: white;
                border: none;
                padding: 15px 30px;
                font-size: 16px;
                border-radius: 5px;
                cursor: pointer;
                margin: 10px;
            }
            button:hover {
                background: #45a049;
            }
            button:disabled {
                background: #cccccc;
                cursor: not-allowed;
            }
            #status {
                margin: 20px 0;
                padding: 15px;
                border-radius: 5px;
                display: none;
            }
            .success {
                background: #d4edda;
                color: #155724;
                border: 1px solid #c3e6cb;
            }
            .error {
                background: #f8d7da;
                color: #721c24;
                border: 1px solid #f5c6cb;
            }
            .loading {
                background: #fff3cd;
                color: #856404;
                border: 1px solid #ffeaa7;
            }
            #results {
                margin-top: 30px;
                padding: 20px;
                background: #f8f9fa;
                border-radius: 5px;
                display: none;
            }
            table {
                width: 100%;
                border-collapse: collapse;
                margin-top: 15px;
            }
            th, td {
                padding: 12px;
                text-align: left;
                border-bottom: 1px solid #ddd;
            }
            th {
                background: #4CAF50;
                color: white;
            }
            tr:hover {
                background: #f5f5f5;
            }
        </style>
    </head>
    <body>
        <div class="container">
            <h1>📁 Folder Analyzer</h1>
            <p>Select a folder to analyze file types and sizes:</p>
            
            <div class="upload-area" onclick="document.getElementById('folderInput').click()">
                <h3>📂 Click here or drop a folder</h3>
                <p>Select a folder from your computer</p>
                <input type="file" id="folderInput" webkitdirectory directory multiple style="display: none;">
            </div>
            
            <button onclick="uploadFolder()" id="analyzeBtn" disabled>🔍 Analyze Folder</button>
            <button onclick="resetPage()">🔄 Reset</button>
            
            <div id="status"></div>
            
            <div id="results">
                <h2>📊 Analysis Results</h2>
                <div id="summary"></div>
                <table id="resultsTable">
                    <thead>
                        <tr>
                            <th>File Type</th>
                            <th>Count</th>
                            <th>Total Size</th>
                        </tr>
                    </thead>
                    <tbody></tbody>
                </table>
            </div>
        </div>

        <script>
            let selectedFiles = [];
            
            // Handle folder selection
            document.getElementById('folderInput').addEventListener('change', function(e) {
                selectedFiles = Array.from(e.target.files);
                updateUI();
            });
            
            // Handle drag and drop
            const dropArea = document.querySelector('.upload-area');
            
            ['dragenter', 'dragover', 'dragleave', 'drop'].forEach(eventName => {
                dropArea.addEventListener(eventName, preventDefaults, false);
            });
            
            function preventDefaults(e) {
                e.preventDefault();
                e.stopPropagation();
            }
            
            ['dragenter', 'dragover'].forEach(eventName => {
                dropArea.addEventListener(eventName, () => {
                    dropArea.style.borderColor = '#2196F3';
                    dropArea.style.background = '#e3f2fd';
                }, false);
            });
            
            ['dragleave', 'drop'].forEach(eventName => {
                dropArea.addEventListener(eventName, () => {
                    dropArea.style.borderColor = '#4CAF50';
                    dropArea.style.background = '#f9f9f9';
                }, false);
            });
            
            dropArea.addEventListener('drop', function(e) {
                const items = Array.from(e.dataTransfer.items);
                
                // Check if folder was dropped
                const folderItems = items.filter(item => {
                    if (item.kind === 'file') {
                        const entry = item.webkitGetAsEntry ? item.webkitGetAsEntry() : null;
                        return entry && entry.isDirectory;
                    }
                    return false;
                });
                
                if (folderItems.length > 0) {
                    // Get files from dropped folder
                    getFilesFromDirectory(folderItems[0].webkitGetAsEntry());
                } else {
                    showStatus('Please drop a folder, not individual files', 'error');
                }
            });
            
            function getFilesFromDirectory(directory) {
                selectedFiles = [];
                
                function readDirectory(dir, path = '') {
                    return new Promise((resolve) => {
                        const reader = dir.createReader();
                        reader.readEntries(async (entries) => {
                            const promises = [];
                            
                            for (const entry of entries) {
                                if (entry.isFile) {
                                    promises.push(new Promise((resolveFile) => {
                                        entry.file(file => {
                                            file.webkitRelativePath = path + entry.name;
                                            selectedFiles.push(file);
                                            resolveFile();
                                        });
                                    }));
                                } else if (entry.isDirectory) {
                                    promises.push(readDirectory(entry, path + entry.name + '/'));
                                }
                            }
                            
                            await Promise.all(promises);
                            resolve();
                        });
                    });
                }
                
                readDirectory(directory).then(() => {
                    updateUI();
                    showStatus(`Loaded ${selectedFiles.length} files from folder`, 'success');
                });
            }
            
            function updateUI() {
                const analyzeBtn = document.getElementById('analyzeBtn');
                if (selectedFiles.length > 0) {
                    analyzeBtn.disabled = false;
                    showStatus(`Ready to analyze: ${selectedFiles.length} files selected`, 'success');
                } else {
                    analyzeBtn.disabled = true;
                }
            }
            
            async function uploadFolder() {
                if (selectedFiles.length === 0) {
                    showStatus('Please select a folder first', 'error');
                    return;
                }
                
                showStatus('Uploading and analyzing...', 'loading');
                
                const formData = new FormData();
                
                // Add all files with their paths
                selectedFiles.forEach(file => {
                    formData.append('files', file, file.webkitRelativePath || file.name);
                });
                
                try {
                    const response = await fetch('/analyze', {
                        method: 'POST',
                        body: formData
                    });
                    
                    if (!response.ok) {
                        throw new Error(`Server error: ${response.status}`);
                    }
                    
                    const data = await response.json();
                    displayResults(data);
                    showStatus('Analysis complete!', 'success');
                    
                } catch (error) {
                    showStatus(`Error: ${error.message}`, 'error');
                    console.error(error);
                }
            }
            
            function displayResults(data) {
                const resultsDiv = document.getElementById('results');
                const summaryDiv = document.getElementById('summary');
                const tableBody = document.querySelector('#resultsTable tbody');
                
                // Show results section
                resultsDiv.style.display = 'block';
                
                // Update summary
                summaryDiv.innerHTML = `
                    <p><strong>Total Files:</strong> ${data.total_files}</p>
                    <p><strong>Total Size:</strong> ${data.total_size_human}</p>
                    <p><strong>File Types Found:</strong> ${Object.keys(data.extensions).length}</p>
                `;
                
                // Clear and populate table
                tableBody.innerHTML = '';
                
                for (const [ext, info] of Object.entries(data.extensions)) {
                    const row = tableBody.insertRow();
                    row.innerHTML = `
                        <td><strong>${ext || '(no extension)'}</strong></td>
                        <td>${info.count}</td>
                        <td>${info.size_human}</td>
                    `;
                }
                
                // Scroll to results
                resultsDiv.scrollIntoView({ behavior: 'smooth' });
            }
            
            function showStatus(message, type) {
                const statusDiv = document.getElementById('status');
                statusDiv.textContent = message;
                statusDiv.className = type;
                statusDiv.style.display = 'block';
            }
            
            function resetPage() {
                selectedFiles = [];
                document.getElementById('folderInput').value = '';
                document.getElementById('analyzeBtn').disabled = true;
                document.getElementById('results').style.display = 'none';
                document.getElementById('status').style.display = 'none';
            }
            
            // Initialize
            updateUI();
        </script>
    </body>
    </html>
    """
    return HTMLResponse(content=html_content)

@app.post("/analyze")
async def analyze_folder(files: list[UploadFile] = File(...)):
    """
    Analyze uploaded folder files
    """
    temp_dir = tempfile.mkdtemp()
    summary = defaultdict(lambda: {"count": 0, "size": 0})
    total_files = total_size = 0
    
    try:
        # Save all files with their structure
        for file in files:
            # Get the full path from the filename (browser preserves structure)
            file_path = file.filename
            
            # Create directory if needed
            full_path = os.path.join(temp_dir, file_path)
            os.makedirs(os.path.dirname(full_path), exist_ok=True)
            
            # Save file
            content = await file.read()
            with open(full_path, "wb") as f:
                f.write(content)
            
            # Analyze
            size = len(content)
            ext = os.path.splitext(file_path)[1].lower() or "no_extension"
            
            summary[ext]["count"] += 1
            summary[ext]["size"] += size
            total_files += 1
            total_size += size
        
        # Prepare response
        result = {
            "total_files": total_files,
            "total_size_bytes": total_size,
            "total_size_human": human_size(total_size),
            "extensions": {
                ext: {
                    "count": data["count"],
                    "size_bytes": data["size"],
                    "size_human": human_size(data["size"])
                } for ext, data in summary.items()
            }
        }
        
        return result
        
    except Exception as e:
        return {"error": str(e)}
    finally:
        # Cleanup
        shutil.rmtree(temp_dir, ignore_errors=True)
