PAGE_INDEX = """
<html>
<head>
  <title>Live Cam</title>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <script>
    function updateSystemInfo() {
      fetch('/system.json')
        .then(response => response.json())
        .then(data => {
          document.getElementById('cpu').textContent = data.cpu + '%';
          document.getElementById('storage').textContent = data.storage || (data.storage_percent + '%');
          if (data.uptime_human && document.getElementById('uptime')) {
            document.getElementById('uptime').textContent = `Uptime: ${data.uptime_human}`;
          }
          // Update progress bars via explicit IDs for robustness
          const cpuProg = document.getElementById('cpu-progress');
          const storageProg = document.getElementById('storage-progress');
          if (cpuProg) cpuProg.style.width = (data.cpu || 0) + '%';
          if (storageProg) storageProg.style.width = (data.storage_percent || 0) + '%';
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
    }
    .video-section {
      grid-area: video;
    }
    .stats-section {
      grid-area: stats;
      background: white;
      border-radius: 10px;
      padding: 15px;
      box-shadow: 0 2px 10px rgba(0,0,0,0.1);
      max-width: 1200px;
      margin: 0 auto;
    }
    .stats-grid {
      display: grid;
      grid-template-columns: 1fr 1fr 1fr;
      gap: 15px;
    }
    .stat-item {
      display: flex;
      flex-direction: column;
      gap: 6px;
      padding: 8px 0;
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
    .uptime-note {
      font-size: 12px;
      color: #6c757d;
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
      .stats-grid {
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
            <div class="progress-fill" id="cpu-progress" style="width: 0%"></div>
          </div>
        </div>
        
        <div class="stat-item">
          <div class="stat-label">Storage Used</div>
          <div class="stat-value" id="storage">--</div>
          <div class="progress-bar">
            <div class="progress-fill" id="storage-progress" style="width: 0%"></div>
          </div>
          <div class="uptime-note" id="uptime">Uptime: --</div>
        </div>

        <div class="stat-item">
          <div class="stat-label">Recordings</div>
          <a href="/recordings" style="display:inline-block; font-weight:bold; color:#0d6efd; text-decoration:none;">View recordings →</a>
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
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <script>
    let currentPage = 1;
    let totalPages = 1;
    const perPage = 20;

    function updatePaginationUI() {
      const paginationContainer = document.getElementById('pagination');
      if (!paginationContainer) return;

      paginationContainer.innerHTML = '';
      
      if (totalPages <= 1) return;

      // Previous button
      const prevBtn = document.createElement('button');
      prevBtn.textContent = 'Previous';
      prevBtn.disabled = currentPage === 1;
      prevBtn.onclick = () => changePage(currentPage - 1);
      paginationContainer.appendChild(prevBtn);

      // Page numbers
      const pageInfo = document.createElement('span');
      pageInfo.className = 'page-info';
      pageInfo.textContent = `Page ${currentPage} of ${totalPages}`;
      paginationContainer.appendChild(pageInfo);

      // Next button
      const nextBtn = document.createElement('button');
      nextBtn.textContent = 'Next';
      nextBtn.disabled = currentPage >= totalPages;
      nextBtn.onclick = () => changePage(currentPage + 1);
      paginationContainer.appendChild(nextBtn);

      // Refresh button
      const refreshBtn = document.createElement('button');
      refreshBtn.innerHTML = '&#x21bb;';
      refreshBtn.title = 'Refresh';
      refreshBtn.className = 'refresh-page-btn';
      refreshBtn.onclick = () => loadRecordings();
      paginationContainer.appendChild(refreshBtn);
    }

    function changePage(page) {
      if (page < 1 || page > totalPages) return;
      currentPage = page;
      loadRecordings();
      window.scrollTo(0, 0);
    }

    function getCurrentDate() {
      const today = new Date();
      const year = today.getFullYear();
      const month = String(today.getMonth() + 1).padStart(2, '0');
      const day = String(today.getDate()).padStart(2, '0');
      return `${year}-${month}-${day}`;
    }

    function setupDatePicker() {
      const datePicker = document.getElementById('date-picker');
      const today = getCurrentDate();
      
      // Set default and max date (today)
      datePicker.value = today;
      datePicker.max = today;
      
      // Fetch the oldest recording date and set it as min date
      fetch('/api/oldest-date')
        .then(response => response.json())
        .then(data => {
          if (data.oldest_date) {
            datePicker.min = data.oldest_date;
            // If current date is before the oldest date, update it
            if (new Date(datePicker.value) < new Date(data.oldest_date)) {
              datePicker.value = data.oldest_date;
            }
          } else {
            // If no recordings, disable the date picker
            datePicker.disabled = true;
          }
        })
        .catch(err => {
          console.error('Error fetching oldest date:', err);
        });
      
      datePicker.addEventListener('change', () => {
        currentPage = 1;  // Reset to first page when changing date
        loadRecordings();
      });
    }

    function loadRecordings() {
      const container = document.getElementById('recordings-container');
      const date = document.getElementById('date-picker').value;
      container.innerHTML = '<p>Loading recordings...</p>';
      
      fetch(`/api/recordings?page=${currentPage}&date=${date}`)
        .then(response => response.json())
        .then(data => {
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
              <a href="/download/${video.path}" class="download-btn">Download</a>
              <video class="preview" controls>
                <source src="/download/${video.path}" type="video/mp4">
                Your browser does not support the video tag.
              </video>
            `;
            container.appendChild(videoDiv);
          });

          // Update pagination state
          if (data.pagination) {
            totalPages = data.pagination.total_pages;
            currentPage = data.pagination.current_page;
            updatePaginationUI();
          }
        })
        .catch(err => {
          console.error('Error loading recordings:', err);
          container.innerHTML = '<p>Error loading recordings. Please try again.</p>';
        });
    }
    
    window.onload = () => {
      setupDatePicker();
      loadRecordings();
    };
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
    .refresh-btn {
      display: inline-block;
      margin-left: 12px;
      padding: 8px 14px;
      background: #0d6efd;
      color: white;
      border: none;
      border-radius: 6px;
      font-weight: bold;
      cursor: pointer;
    }
    .refresh-btn:hover {
      background: #0b5ed7;
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
    .pagination {
      display: flex;
      justify-content: center;
      align-items: center;
      gap: 10px;
      margin: 20px 0;
    }

    .pagination button {
      padding: 5px 15px;
      background-color: #4CAF50;
      color: white;
      border: none;
      border-radius: 4px;
      cursor: pointer;
    }

    .pagination button:disabled {
      background-color: #cccccc;
      cursor: not-allowed;
    }

    .pagination .refresh-page-btn {
      margin-left: 15px;
      background-color: #4CAF50;
      color: white;
      border: none;
      border-radius: 4px;
      padding: 5px 15px;
      cursor: pointer;
      font-size: 1.1em;
    }

    .pagination .refresh-page-btn:hover {
      background-color: #45a049;
    }

    .page-info {
      margin: 0 15px;
      font-weight: bold;
    }

    .date-filter {
      margin: 15px 0;
      display: flex;
      align-items: center;
      gap: 10px;
    }

    .date-filter label {
      font-weight: bold;
      color: #333;
    }

    .date-filter input[type="date"] {
      padding: 8px 12px;
      border: 1px solid #ddd;
      border-radius: 4px;
      font-size: 14px;
    }

    .video-item {
      background: white;
      border-radius: 8px;
      padding: 15px;
      margin-bottom: 20px;
      box-shadow: 0 2px 4px rgba(0,0,0,0.1);
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
    <div class="date-filter">
      <label for="date-picker">Filter by Date:</label>
      <input type="date" id="date-picker">
    </div>
    <a href="/" class="back-link">← Back to Live Feed</a>
    <button class="refresh-btn" onclick="loadRecordings()">Refresh</button>
  </div>
  <div class="container">
    <h1>Recordings</h1>
    <div id="pagination" class="pagination"></div>
    <div id="recordings-container"></div>
    <div id="pagination-bottom" class="pagination"></div>
  </div>
</body>
</html>
"""