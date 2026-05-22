import streamlit as st
import spotipy
from spotipy.oauth2 import SpotifyClientCredentials
import pandas as pd

# Page Configuration
st.set_page_config(page_title="Spotify Playlist Exporter", page_icon="🎵", layout="centered")

# Hide Streamlit header, footer, and menu, and inject custom fonts
custom_css = """
<style>
@import url(https://db.onlinewebfonts.com/c/bac2610117740a492b7a9f5079c9aca4?family=Italian+Plate+No2+Expanded);

@font-face {
    font-family: "Italian Plate No2 Expanded";
    src: url("https://db.onlinewebfonts.com/t/bac2610117740a492b7a9f5079c9aca4.eot");
    src: url("https://db.onlinewebfonts.com/t/bac2610117740a492b7a9f5079c9aca4.eot?#iefix")format("embedded-opentype"),
    url("https://db.onlinewebfonts.com/t/bac2610117740a492b7a9f5079c9aca4.woff2")format("woff2"),
    url("https://db.onlinewebfonts.com/t/bac2610117740a492b7a9f5079c9aca4.woff")format("woff"),
    url("https://db.onlinewebfonts.com/t/bac2610117740a492b7a9f5079c9aca4.ttf")format("truetype"),
    url("https://db.onlinewebfonts.com/t/bac2610117740a492b7a9f5079c9aca4.svg#Italian Plate No2 Expanded")format("svg");
}

#MainMenu {visibility: hidden;}
footer {visibility: hidden;}
header {visibility: hidden;}

html, body, [class*="css"] {
    font-family: 'Italian Plate No2 Expanded', sans-serif !important;
}
</style>
"""
st.markdown(custom_css, unsafe_allow_html=True)
st.title("🎵 Spotify Artist Track Downloader")
st.write("Search for an artist, select your favorite tracks, and export them to a CSV.")

# Streamlit's secrets management
try:
    CLIENT_ID = st.secrets["SPOTIPY_CLIENT_ID"]
    CLIENT_SECRET = st.secrets["SPOTIPY_CLIENT_SECRET"]
except Exception as e:
    st.error("Secrets not found. Please configure your secrets in the Streamlit Cloud dashboard or locally in `.streamlit/secrets.toml`.")
    st.stop()

# Initialize Spotipy with Client Credentials (no user login required!)
@st.cache_resource
def get_spotify_client(client_id, client_secret):
    return spotipy.Spotify(auth_manager=SpotifyClientCredentials(
        client_id=client_id,
        client_secret=client_secret
    ))

try:
    sp = get_spotify_client(CLIENT_ID, CLIENT_SECRET)
except Exception as e:
    st.error(f"Authentication Error: {e}")
    st.stop()

# --- STEP 1: ARTIST SEARCH ---
search_query = st.text_input("Search for an artist:", placeholder="e.g., Daft Punk")

if search_query:
    results = sp.search(q=search_query, type='artist', limit=5)
    artists = results['artists']['items']
    
    if not artists:
        st.warning("No artists found. Try a different spelling.")
    else:
        # Let the user confirm the exact artist
        artist_options = {f"{a['name']} ({a['followers']['total']:,} followers)": a for a in artists}
        selected_artist_str = st.selectbox("Confirm the artist you are looking for:", list(artist_options.keys()))
        
        selected_artist = artist_options[selected_artist_str]
        artist_id = selected_artist['id']
        
        # Display Artist Confirmation Success
        st.success(f"✅ Approved: **{selected_artist['name']}**")
        if selected_artist['images']:
            st.image(selected_artist['images'][0]['url'], width=150)

        # --- STEP 2: FETCH ALL TRACKS ---
        @st.cache_data(show_spinner="Fetching all tracks (this might take a second)...")
        def get_all_artist_tracks(art_id):
            # Fetch all albums
            albums = []
            results = sp.artist_albums(art_id, album_type='album,single', limit=50)
            albums.extend(results['items'])
            while results['next']:
                results = sp.next(results)
                albums.extend(results['items'])
            
            # Fetch tracks from those albums (deduplicating by track name to avoid repeats on deluxe versions)
            track_list = []
            seen_tracks = set()
            
            for album in albums:
                album_tracks = sp.album_tracks(album['id'])['items']
                for track in album_tracks:
                    track_name_lower = track['name'].lower()
                    if track_name_lower not in seen_tracks:
                        seen_tracks.add(track_name_lower)
                        track_list.append({
                            "Track Name": track['name'],
                            "Album": album['name'],
                            "Release Date": album['release_date'],
                            "URI": track['uri'],
                            "Duration (ms)": track['duration_ms']
                        })
            return pd.DataFrame(track_list)

        df_tracks = get_all_artist_tracks(artist_id)
        
        if df_tracks.empty:
            st.write("No tracks found for this artist.")
        else:
            st.write(f"Found **{len(df_tracks)}** unique tracks.")

            # --- STEP 3: INTERACTIVE SELECTION ---
            # We use st.data_editor to easily embed checkboxes directly into a dataframe UI
            df_tracks.insert(0, "Select", False) # Add a column of checkboxes initialized to False
            
            edited_df = st.data_editor(
                df_tracks,
                column_config={"Select": st.column_config.CheckboxColumn(required=True)},
                disabled=["Track Name", "Album", "Release Date", "URI", "Duration (ms)"],
                hide_index=True,
                use_container_width=True
            )

            # Filter rows where the checkbox is checked
            selected_rows = edited_df[edited_df["Select"] == True]

            # --- STEP 4: DOWNLOAD CSV ---
            st.write("---")
            st.subheader("📥 Export Selection")
            
            if not selected_rows.empty:
                # Remove the 'Select' checkbox column before downloading
                csv_df = selected_rows.drop(columns=["Select"])
                csv = csv_df.to_csv(index=False).encode('utf-8')
                
                st.write(f"You have selected **{len(selected_rows)}** tracks.")
                st.download_button(
                    label="Download Selected Tracks as CSV",
                    data=csv,
                    file_name=f"{selected_artist['name'].replace(' ', '_')}_playlist.csv",
                    mime="text/csv",
                )
            else:
                st.info("Check the boxes next to the songs above to select them for export.")
