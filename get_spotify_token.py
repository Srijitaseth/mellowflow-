import base64
import requests
from flask import session

# Spotify API credentials
CLIENT_ID = '37d5359e52124e29b39dd169c46bb4ce'
CLIENT_SECRET = '23cec400f6a141f6a853476a3c7390b1'
REDIRECT_URI = 'http://127.0.0.1:5000/callback'

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
    if response.status_code == 200:
        response_data = response.json()
        session['spotify_user_token'] = response_data['access_token']
        session['spotify_refresh_token'] = response_data['refresh_token']
        return response_data['access_token']
    return None

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
    if response.status_code == 200:
        response_data = response.json()
        return response_data.get('access_token')
    return None
