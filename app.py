import streamlit as st
import pandas as pd
import time
import random
from datetime import datetime
import os
import requests
from bs4 import BeautifulSoup
import json

# Set page config
st.set_page_config(
    page_title="LinkedIn Message Sender",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Define the state
class AgentState(dict):
    def __init__(self, linkedin_url, message, status="", result=""):
        super().__init__()
        self['linkedin_url'] = linkedin_url
        self['message'] = message
        self['status'] = status
        self['result'] = result

def init_session_state():
    # Email
    if 'email' not in st.session_state:
        st.session_state.email = os.getenv("LINKEDIN_EMAIL", "")

    # Password
    if 'password' not in st.session_state:
        st.session_state.password = os.getenv("LINKEDIN_PASSWORD", "")

    # Other session states
    if 'logged_in' not in st.session_state:
        st.session_state.logged_in = False
    if 'results' not in st.session_state:
        st.session_state.results = []
    if 'processing' not in st.session_state:
        st.session_state.processing = False

# UI Components
def sidebar():
    """Create the sidebar with login form"""
    with st.sidebar:
        st.title("LinkedIn Message Sender")
        st.markdown("---")
        
        st.subheader("Login Status")
        
        # Check if credentials are available
        credentials_available = st.session_state.email and st.session_state.password
        
        if credentials_available:
            st.success(" Credentials loaded from environment variables")
            
            if st.button("Test Login"):
                # Simple test without browser automation
                st.session_state.logged_in = True
                st.success("Login simulation successful!")
        else:
            st.error(" Credentials not found")
            st.info("Please set LINKEDIN_EMAIL and LINKEDIN_PASSWORD as environment variables")
        
        if st.session_state.logged_in:
            st.success(" Logged in to LinkedIn")
            if st.button("Logout"):
                st.session_state.logged_in = False
                st.success("Logged out successfully")

def main_interface():
    """Main content area"""
    st.header("LinkedIn Message Sender")
    
    st.warning("""
    Note: This is a simplified version for Render deployment.
    Browser automation is disabled due to resource constraints.
    For full functionality, please run locally with Playwright installed.
    """)
    
    # Check if credentials are available
    if not st.session_state.email or not st.session_state.password:
        st.error("LinkedIn credentials not found.")
        return
    
    # Input area for profiles and messages
    col1, col2 = st.columns(2)
    
    with col1:
        st.subheader("Add Single Profile")
        profile_url = st.text_input("LinkedIn Profile URL")
        message = st.text_area("Message", height=150)
        
        if st.button("Add to Queue"):
            if profile_url and message:
                st.session_state.results.append({
                    "url": profile_url,
                    "message": message,
                    "status": "Pending",
                    "result": "",
                    "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                })
                st.success("Added to queue!")
            else:
                st.error("Please enter both profile URL and message")
    
    with col2:
        st.subheader("Bulk Import")
        uploaded_file = st.file_uploader("Upload CSV file", type=['csv'])
        if uploaded_file is not None:
            try:
                df = pd.read_csv(uploaded_file)
                if 'url' in df.columns and 'message' in df.columns:
                    for _, row in df.iterrows():
                        st.session_state.results.append({
                            "url": row['url'],
                            "message": row['message'],
                            "status": "Pending",
                            "result": "",
                            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                        })
                    st.success(f"Added {len(df)} profiles to queue!")
                else:
                    st.error("CSV must contain 'url' and 'message' columns")
            except Exception as e:
                st.error(f"Error reading CSV: {str(e)}")
    
    # Display queue
    st.subheader("Message Queue")
    if st.session_state.results:
        df = pd.DataFrame(st.session_state.results)
        st.dataframe(df[['url', 'status', 'timestamp']])
        
        # Control buttons
        col1, col2, col3 = st.columns(3)
        
        with col1:
            if st.button("Simulate Sending") and not st.session_state.processing:
                if st.session_state.logged_in:
                    st.session_state.processing = True
                    simulate_message_sending()
                else:
                    st.error("Please login to LinkedIn first")
        
        with col2:
            if st.button("Clear Completed"):
                st.session_state.results = [r for r in st.session_state.results if r['status'] == 'Pending']
                st.rerun()
        
        with col3:
            if st.button("Clear All"):
                st.session_state.results = []
                st.rerun()
    else:
        st.info("No profiles in queue. Add profiles above.")

def simulate_message_sending():
    """Simulate message sending without browser automation"""
    progress_bar = st.progress(0)
    status_text = st.empty()
    
    total = len([r for r in st.session_state.results if r['status'] == 'Pending'])
    processed = 0
    
    for i, result in enumerate(st.session_state.results):
        if result['status'] == 'Pending':
            # Update status to processing
            st.session_state.results[i]['status'] = 'Processing'
            
            # Update progress
            processed += 1
            progress = processed / total
            progress_bar.progress(progress)
            status_text.text(f"Processing {processed} of {total}: {result['url']}")
            
            # Add random delay to appear more human
            time.sleep(random.randint(1, 3))
            
            # Simulate result (success or failure)
            if random.random() > 0.2:  # 80% success rate
                st.session_state.results[i]['status'] = 'Completed'
                st.session_state.results[i]['result'] = 'Simulated: Message sent successfully'
            else:
                st.session_state.results[i]['status'] = 'Failed'
                st.session_state.results[i]['result'] = 'Simulated: Failed to send message'
                
            st.session_state.results[i]['timestamp'] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            
            # Rerun to update UI
            st.rerun()
    
    progress_bar.empty()
    status_text.empty()
    st.session_state.processing = False
    st.success("All messages processed (simulation)!")

# Main app
def main():
    init_session_state()
    sidebar()
    
    if not st.session_state.logged_in and st.session_state.email and st.session_state.password:
        st.info("Click 'Test Login' in the sidebar to get started.")
    
    main_interface()

if __name__ == "__main__":
    main()
