PAGE_INDEX = """
<html>
<head>
  <title>Live Cam</title>
  <script>
    function updateSystemInfo() {
      fetch('/system.json')
        .then(response => response.json())
        .then(data => {
          document.getElementById('cpu').textContent = data.cpu + '%';
          document.getElementById('temp').textContent = data.temp + '°C';
          document.getElementById('storage').textContent = data.storage;
          document.getElementById('memory').textContent = data.memory + '%';
          // Update progress bars
          document.querySelector('#cpu + .progress-bar .progress-fill').style.width = data.cpu + '%';
          document.querySelector('#memory + .progress-bar .progress-fill').style.width = data.memory + '%';
          document.querySelector('#storage + .progress-bar .progress-fill').style.width = (data.storage_percent || 0) + '%';
        })
        .catch(err => console.log('Error fetching system info:', err));
    }
    // Update every 2 seconds
    setInterval(updateSystemInfo, 2000);
    window.onload = updateSystemInfo;
  </script>
  <style>
    * { margin:0; padding:0; }
    body {
      font-family: Arial, sans-serif;
      background-color: #f0f0f0;
    }
    .container {
      display: grid;
      grid-template-areas: "video" "stats";
      grid-template-columns: 1fr;
      gap: 16px;
      max-width: 1200px;
      margin: 0 auto;
      padding: 16px;
    }
    .video-section {
      grid-area: video;
      background: white;
      border-radius: 10px;
      padding: 15px;
      box-shadow: 0 2px 10px rgba(0,0,0,0.1);
    }
    .stats-section {
      grid-area: stats;
      background: white;
      border-radius: 10px;
      padding: 15px;
      box-shadow: 0 2px 10px rgba(0,0,0,0.1);
    }
    .stats-grid {
      display: grid;
      grid-template-columns: 1fr 1fr;
      gap: 15px;
    }
    .stat-item {
      display: flex;
      flex-direction: column;
      align-items: center;
      padding: 15px;
      background: #f8f9fa;
      border-radius: 8px;
      border: 1px solid #e9ecef;
    }
    .stat-label {
      font-size: 14px;
      color: #6c757d;
      margin-bottom: 5px;
    }
    .stat-value {
      font-size: 24px;
      font-weight: bold;
      color: #212529;
    }
    .progress-bar {
      width: 100%;
      height: 8px;
      background: #e9ecef;
      border-radius: 4px;
      overflow: hidden;
      margin-top: 5px;
    }
    .progress-fill {
      height: 100%;
      background: #0d6efd;
      width: var(--width);
      transition: width 0.3s ease;
    }
    .actions-section {
      grid-area: actions;
      background: white;
      border-radius: 10px;
      padding: 20px;
      box-shadow: 0 2px 10px rgba(0,0,0,0.1);
      text-align: center;
    }
    .action-button {
      display: inline-block;
      padding: 12px 24px;
      margin: 10px;
      background: #0d6efd;
      color: white;
      text-decoration: none;
      border-radius: 6px;
      font-weight: bold;
      font-size: 16px;
      border: none;
      cursor: pointer;
      transition: background 0.3s ease;
    }
    .action-button:hover {
      background: #0b5ed7;
    }
    img {
      width: 100%;
      aspect-ratio: 16/9;
      border-radius: 8px;
      display: block;
    }
    @media (max-width: 768px) {
      .container {
        grid-template-areas: "video" "stats" "actions";
        grid-template-columns: 1fr;
      }
    }
  </style>
</head>
<body>
  <div class="container">
    <div class="video-section">
      <img src="stream.mjpg" />
    </div>
    
    <div class="stats-section">
      <div class="stats-grid">
        <div class="stat-item">
          <div class="stat-label">CPU Usage</div>
          <div class="stat-value" id="cpu">--%</div>
          <div class="progress-bar">
            <div class="progress-fill" style="--width: 0%"></div>
          </div>
        </div>
        
        <div class="stat-item">
          <div class="stat-label">Storage Used</div>
          <div class="stat-value" id="storage">--</div>
          <div class="progress-bar">
            <div class="progress-fill" style="--width: 0%"></div>
          </div>
        </div>
      </div>
    </div>
  </div>
</body>
</html>
"""

PAGE_RECORDINGS = """
<html>
<head>
  <title>Recordings</title>
  <script>
    function loadRecordings() {
      fetch('/api/recordings')
        .then(response => response.json())
        .then(data => {
          const container = document.getElementById('recordings-container');
          container.innerHTML = '';
          
          if (data.videos.length === 0) {
            container.innerHTML = '<p>No recordings found.</p>';
            return;
          }
          
          data.videos.forEach(video => {
            const videoDiv = document.createElement('div');
            videoDiv.className = 'video-item';
            videoDiv.innerHTML = `
              <div class="video-info">
                <h3>${video.name}</h3>
                <p><strong>Date:</strong> ${video.date}</p>
                <p><strong>Size:</strong> ${video.size}</p>
              </div>
              <a href="/download/${encodeURIComponent(video.name)}" class="download-btn">Download</a>
              <video class="preview" controls>
                <source src="/download/${encodeURIComponent(video.name)}" type="video/mp4">
                Your browser does not support the video tag.
              </video>
            `;
            container.appendChild(videoDiv);
          });
        })
        .catch(err => {
          console.error('Error loading recordings:', err);
          document.getElementById('recordings-container').innerHTML = '<p>Error loading recordings.</p>';
        });
    }
    
    // Refresh every 30 seconds
    setInterval(loadRecordings, 30000);
    window.onload = loadRecordings;
  </script>
  <style>
    * { margin:0; padding:0; }
    body {
      font-family: Arial, sans-serif;
      background-color: #f0f0f0;
      color: #333;
    }
    .header {
      background: white;
      padding: 20px;
      border-bottom: 1px solid #ddd;
      box-shadow: 0 2px 5px rgba(0,0,0,0.1);
    }
    .header h1 {
      color: #212529;
    }
    .header .back-link {
      display: inline-block;
      margin-top: 10px;
      color: #0d6efd;
      text-decoration: none;
      font-weight: bold;
    }
    .header .back-link:hover {
      text-decoration: underline;
    }
    .container {
      max-width: 1200px;
      margin: 0 auto;
      padding: 20px;
    }
    #recordings-container {
      display: grid;
      grid-template-columns: repeat(2, minmax(0, 1fr));
      gap: 20px;
    }
    .video-item {
      background: white;
      border-radius: 10px;
      padding: 20px;
      margin-bottom: 20px;
      box-shadow: 0 2px 10px rgba(0,0,0,0.1);
      display: grid;
      grid-template-areas: "info download" "video video";
      grid-template-columns: 3fr 1fr;
      gap: 20px;
      align-items: center;
    }
    .video-info {
      grid-area: info;
    }
    .download-btn {
      grid-area: download;
      justify-self: end;
      padding: 10px 20px;
      background: #198754;
      color: white;
      text-decoration: none;
      border-radius: 6px;
      font-weight: bold;
      display: inline-block;
    }
    .download-btn:hover {
      background: #157347;
    }
    .preview {
      grid-area: video;
      width: 100%;
      aspect-ratio: 16/9;
      border-radius: 8px;
      border: 1px solid #ddd;
    }
    @media (max-width: 768px) {
      #recordings-container {
        grid-template-columns: 1fr;
      }
      .video-item {
        grid-template-areas: "info" "video" "download";
        grid-template-columns: 1fr;
      }
      .download-btn {
        justify-self: center;
      }
    }
  </style>
</head>
<body>
  <div class="header">
    <h1>Video Recordings</h1>
    <a href="/" class="back-link">← Back to Live Feed</a>
  </div>
  <div class="container">
    <div id="recordings-container">
      <p>Loading recordings...</p>
    </div>
  </div>
</body>
</html>
"""
