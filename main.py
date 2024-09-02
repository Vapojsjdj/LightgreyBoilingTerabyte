from flask import Flask, request, jsonify, render_template_string
import re
import requests
import json

app = Flask(__name__)

YOUTUBE_API_KEY = "AIzaSyAUX2NELxQ4JwMll3llv9v4DFLsWLRFCRM"

def extract_video_id(url):
    patterns = [
        r'(?:https?:\/\/)?(?:www\.)?youtube\.com\/watch\?v=([^&]+)',
        r'(?:https?:\/\/)?(?:www\.)?youtu\.be\/([^?]+)',
        r'(?:https?:\/\/)?(?:www\.)?youtube\.com\/embed\/([^?]+)'
    ]
    
    for pattern in patterns:
        match = re.search(pattern, url)
        if match:
            return match.group(1)
    
    return None

def get_video_markers(video_id):
    url = f"https://www.youtube.com/watch?v={video_id}"
    response = requests.get(url)
    html_content = response.text

    json_match = re.search(r"var ytInitialData = ({.*?});", html_content)
    
    if not json_match:
        return None

    json_str = json_match.group(1)
    data = json.loads(json_str)

    try:
        framework_updates = data.get('frameworkUpdates', {})
        entity_batch_update = framework_updates.get('entityBatchUpdate', {})
        mutations = entity_batch_update.get('mutations', [])

        for mutation in mutations:
            if mutation.get('entityKey', '').startswith('Egp'):
                payload = mutation.get('payload', {})
                macro_markers_list_entity = payload.get('macroMarkersListEntity', {})
                
                if macro_markers_list_entity:
                    return {
                        'externalVideoId': macro_markers_list_entity.get('externalVideoId'),
                        'markersList': macro_markers_list_entity.get('markersList', {})
                    }

        return None
    except Exception as e:
        print(f"An error occurred: {e}")
        return None

def get_most_watched_timestamps(data):
    markers = data['markersList'].get('markers', [])
    sorted_markers = sorted(markers, key=lambda x: float(x.get('intensityScoreNormalized', 0)), reverse=True)
    
    most_watched_timestamps = []
    for marker in sorted_markers:
        start_millis = marker.get('startMillis', '0')
        if start_millis.isdigit():
            seconds = int(start_millis) / 1000
            intensity_score = float(marker.get('intensityScoreNormalized', 0))
            if not is_close_to_existing_timestamp(seconds, most_watched_timestamps):
                most_watched_timestamps.append((seconds, intensity_score))
            if len(most_watched_timestamps) == 10:
                break
    
    return sorted(most_watched_timestamps, key=lambda x: x[0])

def is_close_to_existing_timestamp(new_timestamp, existing_timestamps, threshold=15):
    for timestamp, _ in existing_timestamps:
        if abs(new_timestamp - timestamp) <= threshold:
            return True
    return False

def seconds_to_time_format(seconds):
    minutes, seconds = divmod(int(seconds), 60)
    hours, minutes = divmod(minutes, 60)
    return f"{hours:02d}:{minutes:02d}:{seconds:02d}"

@app.route('/analyze', methods=['POST'])
def analyze_video():
    video_url = request.json['url']
    video_id = extract_video_id(video_url)

    if not video_id:
        return jsonify({"error": "لم يتم العثور على معرف فيديو صالح في الرابط المدخل."})

    markers_data = get_video_markers(video_id)

    if not markers_data:
        return jsonify({"error": "لم يتم العثور على بيانات العلامات لهذا الفيديو."})

    most_watched_timestamps = get_most_watched_timestamps(markers_data)
    formatted_timestamps = [
        {
            "time": seconds_to_time_format(ts),
            "views": int(score * 100000)  # تقريب تقديري لعدد المشاهدات
        } for ts, score in most_watched_timestamps
    ]

    return jsonify({
        "video_id": video_id,
        "most_watched_timestamps": formatted_timestamps
    })

@app.route('/search', methods=['GET'])
def search_videos():
    query = request.args.get('query', '')
    search_type = request.args.get('type', 'keyword')
    order = request.args.get('order', 'relevance')
    
    if not query:
        return jsonify({"error": "يرجى تقديم استعلام بحث."})

    if search_type == 'channel':
        channel_id = get_channel_id(query)
        if not channel_id:
            return jsonify({"error": "لم يتم العثور على القناة."})
        url = f"https://www.googleapis.com/youtube/v3/search?part=snippet&channelId={channel_id}&type=video&order={order}&key={YOUTUBE_API_KEY}&maxResults=50"
    else:
        url = f"https://www.googleapis.com/youtube/v3/search?part=snippet&q={query}&type=video&order={order}&key={YOUTUBE_API_KEY}&maxResults=50"
    
    response = requests.get(url)
    data = response.json()

    videos = []
    for item in data.get('items', []):
        video = {
            'id': item['id']['videoId'],
            'title': item['snippet']['title'],
            'thumbnail': item['snippet']['thumbnails']['medium']['url'],
            'channelTitle': item['snippet']['channelTitle'],
            'publishedAt': item['snippet']['publishedAt']
        }
        videos.append(video)

    return jsonify(videos)

def get_channel_id(channel_name):
    url = f"https://www.googleapis.com/youtube/v3/search?part=snippet&type=channel&q={channel_name}&key={YOUTUBE_API_KEY}"
    response = requests.get(url)
    data = response.json()

    if 'items' in data and len(data['items']) > 0:
        return data['items'][0]['id']['channelId']
    return None

@app.route('/')
def index():
    return render_template_string('''
<!DOCTYPE html>
<html lang="ar" dir="rtl">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>تحليل YouTube</title>
    <link href="https://fonts.googleapis.com/css2?family=Cairo:wght@400;700&display=swap" rel="stylesheet">
    <link href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/5.15.1/css/all.min.css" rel="stylesheet">
    <style>
        :root {
            --primary-color: #FF0000;
            --secondary-color: #282828;
            --background-color: #F9F9F9;
            --text-color: #333;
            --card-background: #FFFFFF;
        }
        body {
            font-family: 'Cairo', sans-serif;
            margin: 0;
            padding: 20px;
            background-color: var(--background-color);
            color: var(--text-color);
            transition: background-color 0.3s, color 0.3s;
        }
        .container {
            max-width: 800px;
            margin: 0 auto;
            background-color: var(--card-background);
            padding: 20px;
            border-radius: 8px;
            box-shadow: 0 2px 10px rgba(0,0,0,0.1);
        }
        h1 {
            color: var(--primary-color);
            display: flex;
            align-items: center;
            justify-content: center;
            margin-bottom: 20px;
        }
        h1 i {
            margin-left: 10px;
            font-size: 0.8em;
        }
        .search-container {
            display: flex;
            margin-bottom: 20px;
        }
        #searchQuery {
            flex-grow: 1;
            padding: 10px;
            border: 1px solid #ddd;
            border-radius: 4px 0 0 4px;
            font-size: 16px;
        }
        #searchButton {
            background-color: var(--primary-color);
            color: white;
            border: none;
            padding: 10px 20px;
            border-radius: 0 4px 4px 0;
            cursor: pointer;
            font-size: 16px;
        }
        .card {
            background-color: var(--card-background);
            border-radius: 8px;
            padding: 15px;
            margin-bottom: 20px;
            box-shadow: 0 2px 5px rgba(0,0,0,0.1);
        }
        .card h2 {
            color: var(--primary-color);
            margin-top: 0;
            display: flex;
            align-items: center;
        }
        .card h2 i {
            margin-left: 10px;
        }
        #videoPlayer {
            width: 100%;
            max-width: 640px;
            margin: 0 auto 20px;
            border-radius: 8px;
            overflow: hidden;
            box-shadow: 0 2px 10px rgba(0,0,0,0.1);
        }
        #player {
            width: 100%;
            aspect-ratio: 16 / 9;
        }
        .video-item {
            display: flex;
            align-items: center;
            margin-bottom: 10px;
            cursor: pointer;
            padding: 10px;
            border-radius: 4px;
            transition: background-color 0.2s;
        }
        .video-item:hover {
            background-color: #f0f0f0;
        }
        .video-item img {
            width: 120px;
            margin-left: 10px;
            border-radius: 4px;
        }
        .timestamp {
            cursor: pointer;
            color: var(--primary-color);
            text-decoration: underline;
            display: flex;
            justify-content: space-between;
            margin-bottom: 5px;
        }
        #darkModeToggle {
            position: fixed;
            top: 20px;
            left: 20px;
            background-color: var(--secondary-color);
            color: white;
            border: none;
            padding: 10px;
            border-radius: 50%;
            cursor: pointer;
            font-size: 16px;
        }
        .dark-mode {
            --background-color: #121212;
            --text-color: #FFFFFF;
            --card-background: #1E1E1E;
        }
        #searchResults {
            max-height: 400px;
            overflow-y: auto;
            margin-top: 20px;
        }
        #videoList {
            display: grid;
            grid-template-columns: repeat(auto-fill, minmax(150px, 1fr));
            gap: 15px;
        }
        .video-item {
            display: flex;
            flex-direction: column;
            align-items: center;
            text-align: center;
        }
        .video-item img {
            width: 100%;
            max-width: 150px;
            height: auto;
            margin-bottom: 10px;
        }
        .navigation-buttons {
            display: flex;
            justify-content: space-between;
            margin-top: 10px;
        }
        .nav-button {
            background-color: var(--primary-color);
            color: white;
            border: none;
            padding: 10px 20px;
            border-radius: 4px;
            cursor: pointer;
            font-size: 16px;
        }
        .nav-button:disabled {
            background-color: #ccc;
            cursor: not-allowed;
        }
        #timestamps {
            max-height: 200px;
            overflow-y: auto;
            border: 1px solid #ddd;
            border-radius: 4px;
            padding: 10px;
            margin-bottom: 10px;
        }
        .search-type, .search-order {
            display: flex;
            justify-content: center;
            margin-bottom: 10px;
        }
        .search-type label, .search-order label {
            margin: 0 10px;
        }
        .filter-container {
            display: flex;
            justify-content: space-between;
            margin-bottom: 10px;
        }
    </style>
</head>
<body>
    <div class="container">
        <h1><i class="fab fa-youtube"></i> تحليل YouTube</h1>
        <div class="filter-container">
            <div class="search-type">
                <label>
                    <input type="radio" name="searchType" value="keyword" checked> بحث بالكلمات المفتاحية
                </label>
                <label>
                    <input type="radio" name="searchType" value="channel"> بحث عن الفيديوهات من قناة
                </label>
            </div>
            <div class="search-order">
                <label>
                    <input type="radio" name="searchOrder" value="relevance" checked> الأكثر صلة
                </label>
                <label>
                    <input type="radio" name="searchOrder" value="date"> الأحدث
                </label>
                <label>
                    <input type="radio" name="searchOrder" value="viewCount"> الأكثر مشاهدة
                </label>
                <label>
                    <input type="radio" name="searchOrder" value="rating"> الأعلى تقييماً
                </label>
            </div>
        </div>
        <div class="search-container">
            <input type="text" id="searchQuery" placeholder="ابحث عن فيديوهات أو اسم القناة">
            <button id="searchButton" onclick="searchVideos()"><i class="fas fa-search"></i></button>
        </div>
        <div id="videoPlayer"></div>
        <div id="result" class="card">
            <h2><i class="fas fa-chart-line"></i> اللقطات العشر الأكثر مشاهدة</h2>
            <div id="timestamps"></div>
            <div class="navigation-buttons">
                <button id="prevButton" class="nav-button" onclick="navigateTimestamp(-1)" disabled>السابق</button>
                <button id="nextButton" class="nav-button" onclick="navigateTimestamp(1)" disabled>التالي</button>
            </div>
        </div>
        <div id="searchResults" class="card">
            <h2><i class="fas fa-list"></i> نتائج البحث</h2>
            <div id="videoList"></div>
        </div>
    </div>
    <button id="darkModeToggle" onclick="toggleDarkMode()"><i class="fas fa-moon"></i></button>

    <script src="https://www.youtube.com/iframe_api"></script>
    <script>
        let player;
        let isDarkMode = false;
        let currentTimestampIndex = -1;
        let timestamps = [];

        function onYouTubeIframeAPIReady() {
            console.log('YouTube API Ready');
        }

        async function searchVideos() {
            const query = document.getElementById('searchQuery').value;
            const searchType = document.querySelector('input[name="searchType"]:checked').value;
            const searchOrder = document.querySelector('input[name="searchOrder"]:checked').value;
            const searchResultsDiv = document.getElementById('videoList');
            searchResultsDiv.innerHTML = '<p>جارٍ البحث...</p>';

            try {
                const response = await fetch(`/search?query=${encodeURIComponent(query)}&type=${searchType}&order=${searchOrder}`);
                const videos = await response.json();

                if (videos.error) {
                    searchResultsDiv.textContent = videos.error;
                } else {
                    let resultsHtml = '';
                    videos.forEach(video => {
                        resultsHtml += `
                            <div class="video-item" onclick="loadVideo('${video.id}')">
                                <img src="${video.thumbnail}" alt="${video.title}">
                                <span>${video.title}</span>
                                <small>${video.channelTitle}</small>
                                <small>${new Date(video.publishedAt).toLocaleDateString()}</small>
                            </div>
                        `;
                    });
                    searchResultsDiv.innerHTML = resultsHtml;
                }
            } catch (error) {
                searchResultsDiv.textContent = 'حدث خطأ أثناء البحث: ' + error.message;
            }
        }

        async function loadVideo(videoId) {
            if (player) {
                player.destroy();
            }

            player = new YT.Player('videoPlayer', {
                height: '360',
                width: '640',
                videoId: videoId,
                events: {
                    'onReady': onPlayerReady
                }
            });

            try {
                const response = await fetch('/analyze', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                    },
                    body: JSON.stringify({ url: `https://www.youtube.com/watch?v=${videoId}` }),
                });
                const data = await response.json();

                if (data.error) {
                    document.getElementById('timestamps').textContent = data.error;
                } else {
                    timestamps = data.most_watched_timestamps;
                    updateTimestamps();
                }
            } catch (error) {
                document.getElementById('timestamps').textContent = 'حدث خطأ أثناء تحليل الفيديو: ' + error.message;
            }
        }

        function onPlayerReady(event) {
            console.log('Player is ready');
        }

        function updateTimestamps() {
            const timestampsDiv = document.getElementById('timestamps');
            timestampsDiv.innerHTML = timestamps.map((timestamp, index) => 
                `<div class="timestamp" onclick="seekTo(${index})">
                    <span>${timestamp.time}</span>
                    <span>${timestamp.views} مشاهدة</span>
                </div>`
            ).join('');

            document.getElementById('prevButton').disabled = true;
            document.getElementById('nextButton').disabled = false;
            currentTimestampIndex = -1;
        }

        function seekTo(index) {
            if (player && index >= 0 && index < timestamps.length) {
                const time = timestampToSeconds(timestamps[index].time);
                player.seekTo(time, true);
                currentTimestampIndex = index;
                updateNavigationButtons();
            }
        }

        function navigateTimestamp(direction) {
            const newIndex = currentTimestampIndex + direction;
            if (newIndex >= 0 && newIndex < timestamps.length) {
                seekTo(newIndex);
            }
        }

        function updateNavigationButtons() {
            document.getElementById('prevButton').disabled = currentTimestampIndex <= 0;
            document.getElementById('nextButton').disabled = currentTimestampIndex >= timestamps.length - 1;
        }

        function timestampToSeconds(timestamp) {
            const [hours, minutes, seconds] = timestamp.split(':').map(Number);
            return hours * 3600 + minutes * 60 + seconds;
        }

        function toggleDarkMode() {
            isDarkMode = !isDarkMode;
            document.body.classList.toggle('dark-mode', isDarkMode);
            const icon = document.querySelector('#darkModeToggle i');
            icon.classList.toggle('fa-moon', !isDarkMode);
            icon.classList.toggle('fa-sun', isDarkMode);
        }
    </script>
</body>
</html>
    ''')

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8080)