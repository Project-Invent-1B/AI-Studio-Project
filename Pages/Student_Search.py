import streamlit as st
import pandas as pd
import numpy as np
import faiss
from geopy.geocoders import Nominatim
from sentence_transformers import SentenceTransformer
import certifi
import ssl
import os
import time


st.title("Student Search")
st.write("This is the Student Search page.")
# Load data and embeddings
script_dir = os.path.dirname(__file__) #finds directory of this program

m_path = "../Data/full_990_clean.csv"
metadata_filepath = os.path.join(script_dir, m_path) #finds location of file

e_path = "../Data/organization_embeddings.faiss"
embeddings_filepath = os.path.join(script_dir, e_path) #finds location of file

ef_path = "../Data/optimized_index.index"
ef_filepath = os.path.join(script_dir, ef_path) #finds location of file

with st.spinner('Loading data...'):
    metadata = pd.read_csv(metadata_filepath)
    metadata['Latitude'] = metadata['Latitude'].astype(float)
    metadata['Longitude'] = metadata['Longitude'].astype(float)

    metadata['Phone Number'] = metadata['Phone Number'].apply(
        lambda x: f"{str(int(x))[:3]}-{str(int(x))[3:6]}-{str(int(x))[6:]}" if pd.notnull(x) and len(str(int(x))) == 10 else "")

    index = faiss.read_index(embeddings_filepath)
    # Load the model
    model = SentenceTransformer('all-MiniLM-L6-v2')

# Define Haversine Function
def haversine(lat1, lon1, lat2, lon2):
    R = 3958.8  # Radius of Earth in miles
    phi1, phi2 = np.radians(lat1), np.radians(lat2)
    delta_phi = np.radians(lat2 - lat1)
    delta_lambda = np.radians(lon2 - lon1)
    a = np.sin(delta_phi / 2) ** 2 + np.cos(phi1) * np.cos(phi2) * np.sin(delta_lambda / 2) ** 2
    c = 2 * np.arctan2(np.sqrt(a), np.sqrt(1 - a))
    return R * c

# Geocode function
def get_lat_lon_from_zip(zipcode):
    ssl_context = ssl.create_default_context()
    ssl_context.load_verify_locations(certifi.where())
    geolocator = Nominatim(user_agent="geoapi", ssl_context=ssl_context)
    try:
        location = geolocator.geocode(zipcode, country_codes="us", timeout=10)
        if location:
            return location.latitude, location.longitude
        else:
            return None, None
    except Exception as e:
        st.error(f"Error with location services: {e}")
        return None, None

# Streamlit App
st.title("Organization Search Tool")

# User Inputs
query = st.text_input("Enter your query", value="I want to work with an veteran's organization.")
zip_code = st.text_input("Enter your ZIP code", value="90210")
search_radius = st.number_input("Enter search radius (miles)", min_value=1, max_value=100, value=40)
k = st.number_input("Number of organizations to return", min_value=1, max_value=50, value=15)

if st.button("Search"):
    if not zip_code or not query:
        st.warning("Please enter both a query and a ZIP code.")
    else:
        # Get user location
        user_lat, user_lon = get_lat_lon_from_zip(zip_code)
        if user_lat is None or user_lon is None:
            st.error("Invalid ZIP code. Please try again.")
        else:
            with st.spinner('Searching within your radius...'):
                # Filter organizations by radius
                metadata['distance'] = metadata.apply(
                    lambda row: haversine(user_lat, user_lon, row['Latitude'], row['Longitude']), axis=1
                )
                filtered_metadata = metadata[metadata['distance'] <= search_radius]
            with st.spinner('Listing organization names...'):
                if filtered_metadata.empty:
                    st.warning("No organizations found within the specified radius.")
                else:
                    # Create a temporary FAISS index with filtered organizations
                    filtered_indices = filtered_metadata.index
                    filtered_embeddings = np.vstack([index.reconstruct(i) for i in filtered_indices])
                    dimension = filtered_embeddings.shape[1]

                    temp_index = faiss.IndexFlatL2(dimension)
                    temp_index.add(filtered_embeddings)

                    # Query the FAISS index
                    query_embedding = model.encode(query)
                    k = min(k, len(filtered_metadata))  # Handle cases with fewer results than k
                    distances, indices = temp_index.search(np.array([query_embedding]), k)

                    # Map results back to metadata
                    final_results = filtered_metadata.iloc[indices[0]]

                    # Display results
                    st.subheader("Search Results")
                    st.table(final_results)
