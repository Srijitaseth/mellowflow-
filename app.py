import base64
import requests
from flask import Flask, render_template, request, redirect, url_for, session
import json
import os
from dotenv import load_dotenv


app = Flask(__name__)
app.secret_key = 'your-secret-key'  # Replace with a secure secret key

load_dotenv()

CLIENT_ID = os.getenv('CLIENT_ID')
CLIENT_SECRET = os.getenv('CLIENT_SECRET')
REDIRECT_URI = 'http://127.0.0.1:5000/callback'  # Ensure this matches your Spotify app settings
SCOPE = 'playlist-modify-public'

# Define routes
@app.route('/')
def index():
    return render_template('index.html')

@app.route('/generate', methods=['POST'])
def generate():
    prompt = request.form.get('prompt')
    if not prompt:
        return redirect(url_for('index'))

    # Redirect to the energy level page with the prompt
    return redirect(url_for('set_energy_level', prompt=prompt))

@app.route('/set_energy_level', methods=['GET', 'POST'])
def set_energy_level():
    prompt = request.args.get('prompt')
    if request.method == 'POST':
        energy_level = request.form.get('energy_level')
        explicit_filter = 'explicit_filter' in request.form  # Check if checkbox is ticked

        if not energy_level:
            return redirect(url_for('set_energy_level', prompt=prompt))

        energy_level = int(energy_level)
        if not (0 <= energy_level <= 100):
            return redirect(url_for('set_energy_level', prompt=prompt))

        # Redirect to the generate_suggestions page with prompt, energy level, and explicit filter
        return redirect(url_for('generate_suggestions', prompt=prompt, energy_level=energy_level, explicit_filter=explicit_filter))

    return render_template('energy_level.html', prompt=prompt)

@app.route('/generate_suggestions', methods=['GET'])
def generate_suggestions():
    prompt = request.args.get('prompt')
    energy_level = request.args.get('energy_level')
    explicit_filter = request.args.get('explicit_filter')

    if not prompt or not energy_level:
        return redirect(url_for('index'))

    # Convert energy_level to integer
    energy_level = int(energy_level)

    # Fetch suggestions from Spotify
    suggestions = fetch_suggestions(prompt, energy_level, explicit_filter)

    # Debugging output
    print(f"Received prompt: {prompt}")
    print(f"Received energy level: {energy_level}")
    print(f"Explicit filter applied: {explicit_filter}")
    print(f"Suggestions: {suggestions}")

    # Render the suggestions template
    return render_template('suggestions.html', prompt=prompt, energy_level=energy_level, suggestions=suggestions)

@app.route('/create_playlist', methods=['POST'])
def create_playlist():
    token = session.get('spotify_user_token')
    if not token:
        return redirect(url_for('get_spotify_user_token'))  # Redirect to the token URL if token is missing

    playlist_name = request.form.get('playlist_name')
    if not playlist_name:
        return redirect(url_for('generate_suggestions'))

    suggestions = request.form.get('suggestions')
    if not suggestions:
        return redirect(url_for('generate_suggestions'))

    try:
        suggestions = json.loads(suggestions)  # Convert string representation of list back to list
    except json.JSONDecodeError as e:
        print(f"Error decoding suggestions: {e}")
        return redirect(url_for('generate_suggestions'))

    print(f"Parsed suggestions: {suggestions}")

    user_id = get_spotify_user_id(token)
    if not user_id:
        return 'Failed to get user ID. Unable to create playlist.'

    playlist_id = create_playlist_on_spotify(token, playlist_name)
    if not playlist_id:
        return 'Failed to create playlist on Spotify.'

    track_uris = [track['uri'] for track in suggestions]
    if not add_tracks_to_playlist(token, playlist_id, track_uris):
        return 'Failed to add tracks to playlist on Spotify.'

    playlist_link = f"https://open.spotify.com/playlist/{playlist_id}"

    return render_template('create_playlist.html', playlist_link=playlist_link, playlist_created=True)

@app.route('/get_spotify_user_token')
def get_spotify_user_token():
    # Generate the Spotify authorization URL
    auth_url = 'https://accounts.spotify.com/authorize'
    params = {
        'response_type': 'code',
        'client_id': CLIENT_ID,
        'scope': SCOPE,
        'redirect_uri': REDIRECT_URI,
        'state': 'state'
    }
    return redirect(f"{auth_url}?{requests.compat.urlencode(params)}")

@app.route('/callback')
def callback():
    print("Callback route")
    # Extract the authorization code from the URL query parameters
    code = request.args.get('code')
    print(f"Authorization code: {code}")  # Debugging statement
    if not code:
        return 'No authorization code found in callback.'

    # Exchange the authorization code for an access token
    try:
        token = get_spotify_user_token_from_code(code)
        session['spotify_user_token'] = token  # Store the token in the session
        return redirect(url_for('generate_suggestions'))
    except Exception as e:
        return f'Failed to get token from callback. Ensure that the redirect URI and client configuration are correct. Error: {e}'

def get_spotify_user_token_from_code(code):
    auth_url = 'https://accounts.spotify.com/api/token'
    headers = {
        'Authorization': 'Basic ' + base64.b64encode(f'{CLIENT_ID}:{CLIENT_SECRET}'.encode()).decode('ascii'),
        'Content-Type': 'application/x-www-form-urlencoded'
    }
    data = {
        'grant_type': 'authorization_code',
        'code': code,
        'redirect_uri': REDIRECT_URI
    }
    response = requests.post(auth_url, headers=headers, data=data)
    response_data = response.json()
    if 'access_token' in response_data:
        session['spotify_user_token'] = response_data['access_token']
        session['spotify_refresh_token'] = response_data['refresh_token']
        return response_data['access_token']
    else:
        raise Exception("Failed to get Spotify user access token.")


def refresh_spotify_token(refresh_token):
    auth_url = 'https://accounts.spotify.com/api/token'
    headers = {
        'Authorization': 'Basic ' + base64.b64encode(f'{CLIENT_ID}:{CLIENT_SECRET}'.encode()).decode('ascii'),
        'Content-Type': 'application/x-www-form-urlencoded'
    }
    data = {
        'grant_type': 'refresh_token',
        'refresh_token': refresh_token
    }
    response = requests.post(auth_url, headers=headers, data=data)
    response_data = response.json()
    if 'access_token' in response_data:
        session['spotify_user_token'] = response_data['access_token']
        return response_data['access_token']
    else:
        print("Failed to refresh Spotify access token.")
        return None


def fetch_suggestions(prompt, energy_level, explicit_filter):
    token = get_spotify_token()
    headers = {
        'Authorization': f'Bearer {token}'
    }

    search_url = 'https://api.spotify.com/v1/search'
    params = {
        'q': prompt,
        'type': 'track',
        'limit': 10  # Number of tracks to fetch
    }
    if explicit_filter:
        params['filter'] = 'explicit'  # Add filter for explicit content

    response = requests.get(search_url, headers=headers, params=params)
    data = response.json()
    
    # Debugging output
    print(f"Spotify API response: {data}")

    tracks = data.get('tracks', {}).get('items', [])
    suggestions = []
    for track in tracks:
        suggestion = {
            'name': track['name'],
            'artist': track['artists'][0]['name'],
            'image': track['album']['images'][0]['url'],  # URL for the album cover image
            'uri': track['uri']  # Spotify URI for the track
        }
        suggestions.append(suggestion)

    return suggestions

def get_spotify_token():
    auth_url = 'https://accounts.spotify.com/api/token'
    headers = {
        'Authorization': 'Basic ' + base64.b64encode(f'{CLIENT_ID}:{CLIENT_SECRET}'.encode()).decode('ascii'),
        'Content-Type': 'application/x-www-form-urlencoded'
    }
    data = {
        'grant_type': 'client_credentials'
    }
    response = requests.post(auth_url, headers=headers, data=data)
    response_data = response.json()
    if 'access_token' in response_data:
        return response_data['access_token']
    else:
        raise Exception("Failed to get Spotify access token.")

def create_playlist_on_spotify(token, playlist_name):
    user_id = get_spotify_user_id(token)
    if not user_id:
        print("Failed to get user ID.")
        return None
    
    url = f'https://api.spotify.com/v1/users/{user_id}/playlists'
    headers = {
        'Authorization': f'Bearer {token}',
        'Content-Type': 'application/json'
    }
    data = {
        'name': playlist_name,
        'description': 'Generated by Mellowflow',
        'public': True
    }
    response = requests.post(url, headers=headers, json=data)
    
    # Detailed logging
    print(f"Create playlist response status: {response.status_code}")
    print(f"Create playlist response data: {response.json()}")
    
    if response.status_code == 201:
        return response.json().get('id')  # Fixed typo here: `response_data` -> `response.json()`
    else:
        print("Failed to create playlist on Spotify.")
        return None


def add_tracks_to_playlist(token, playlist_id, track_uris):
    url = f'https://api.spotify.com/v1/playlists/{playlist_id}/tracks'
    headers = {
        'Authorization': f'Bearer {token}',
        'Content-Type': 'application/json'
    }
    data = {
        'uris': track_uris
    }
    response = requests.post(url, headers=headers, json=data)
    
    # Detailed logging
    print(f"Add tracks response status: {response.status_code}")
    print(f"Add tracks response data: {response.json()}")

    if response.status_code != 201:
        print("Failed to add tracks to the playlist.")
        return False
    
    return True

def get_spotify_user_id(token):
    url = 'https://api.spotify.com/v1/me'
    headers = {
        'Authorization': f'Bearer {token}'
    }
    response = requests.get(url, headers=headers)
    response_data = response.json()
    
    # Debugging statements
    print(f"Response status code: {response.status_code}")
    print(f"Response data: {response_data}")
    
    if response.status_code == 200:
        return response_data.get('id')
    elif response.status_code == 401 and response_data.get('error', {}).get('message') == 'The access token expired':
        refresh_token = session.get('spotify_refresh_token')
        if not refresh_token:
            print("No refresh token available.")
            return None
        new_token = refresh_spotify_token(refresh_token)
        if not new_token:
            print("Failed to refresh token.")
            return None
        return get_spotify_user_id(new_token)
    else:
        print("Failed to get user ID.")
        return None


if __name__ == '__main__':
    app.run(debug=True)
