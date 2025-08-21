import streamlit as st
import pandas as pd
import time
import random
from typing import List, Dict
from langgraph.graph import StateGraph, END
from playwright.sync_api import sync_playwright
import json
import os
from datetime import datetime

# Set page config
st.set_page_config(
    page_title="LinkedIn Message Sender",
    page_icon="💼",
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

# LinkedIn interaction functions
def login_to_linkedin(page, email, password):
    """Login to LinkedIn"""
    try:
        page.goto("https://www.linkedin.com/login")
        page.fill("#username", email)
        page.fill("#password", password)
        page.click("button[type=submit]")
        page.wait_for_selector("nav.global-nav", timeout=60000)
        time.sleep(3)
        return True
    except Exception as e:
        st.error(f"Login failed: {str(e)}")
        return False

def is_connected(page, profile_url):
    """Check if already connected to the profile"""
    try:
        page.goto(profile_url)
        time.sleep(3)
        
        # Check for "Message" button (indicates connection)
        message_button = page.query_selector('button:has-text("Message")')
        if message_button:
            return True
        
        # Check for "Connect" button (indicates not connected)
        connect_button = page.query_selector('button:has-text("Connect")')
        if connect_button:
            return False
        
        return None
    except Exception as e:
        st.error(f"Connection check failed: {str(e)}")
        return None

def send_message(page, profile_url, message):
    """Send message to a connected profile"""
    try:
        page.goto(profile_url)
        time.sleep(3)
        
        # Click message button
        message_button = page.query_selector('button:has-text("Message")')
        if message_button:
            message_button.click()
            time.sleep(2)
            
            # Find message input and send message
            message_input = page.query_selector('div[aria-label="Write a message…"]')
            if message_input:
                message_input.click()
                message_input.fill(message)
                time.sleep(1)
                
                # Send message
                send_button = page.query_selector('button:has-text("Send")')
                if send_button:
                    send_button.click()
                    time.sleep(2)
                    return "Message sent successfully"
        
        return "Failed to send message - UI elements not found"
    except Exception as e:
        return f"Error sending message: {str(e)}"

def send_connection_request(page, profile_url, message):
    """Send connection request with note"""
    try:
        page.goto(profile_url)
        time.sleep(3)
        
        # Click connect button
        connect_button = page.query_selector('button:has-text("Connect")')
        if connect_button:
            connect_button.click()
            time.sleep(2)
            
            # Check if add note option is available
            add_note_button = page.query_selector('button:has-text("Add a note")')
            if add_note_button:
                add_note_button.click()
                time.sleep(1)
                
                # Add note
                note_textarea = page.query_selector('textarea[name="message"]')
                if note_textarea:
                    note_textarea.fill(message)
                    time.sleep(1)
                    
                    # Send without email if option exists
                    send_without_email = page.query_selector('button:has-text("Send without")')
                    if send_without_email:
                        send_without_email.click()
                    else:
                        # Find and click send button
                        send_buttons = page.query_selector_all('button[aria-label*="Send"]')
                        if send_buttons:
                            send_buttons[0].click()
                    
                    time.sleep(2)
                    return "Connection request sent with note"
        
        return "Failed to send connection request - UI elements not found"
    except Exception as e:
        return f"Error sending connection request: {str(e)}"

# Define nodes for the graph
def check_connection(state, page, email, password):
    """Check if connected to the profile"""
    try:
        # Login if not already logged in
        if not page.url.startswith("https://www.linkedin.com/feed"):
            if not login_to_linkedin(page, email, password):
                return {"status": "error", "result": "Login failed"}
        
        # Check connection status
        connected = is_connected(page, state["linkedin_url"])
        
        if connected is None:
            return {"status": "error", "result": "Could not determine connection status"}
        elif connected:
            return {"status": "connected", "result": "Already connected to this profile"}
        else:
            return {"status": "not_connected", "result": "Not connected to this profile"}
            
    except Exception as e:
        return {"status": "error", "result": f"Error: {str(e)}"}

def send_direct_message(state, page):
    """Send message to connected profile"""
    try:
        result = send_message(page, state["linkedin_url"], state["message"])
        return {"result": result}
    except Exception as e:
        return {"status": "error", "result": f"Error: {str(e)}"}

def send_connection_with_note(state, page):
    """Send connection request with note"""
    try:
        result = send_connection_request(page, state["linkedin_url"], state["message"])
        return {"result": result}
    except Exception as e:
        return {"status": "error", "result": f"Error: {str(e)}"}

# Build the graph
def create_workflow():
    """Create the LangGraph workflow"""
    workflow = StateGraph(AgentState)

    # Add nodes (these will be called with additional parameters)
    workflow.add_node("check_connection", lambda state: check_connection(state, st.session_state.page, st.session_state.email, st.session_state.password))
    workflow.add_node("send_message", lambda state: send_direct_message(state, st.session_state.page))
    workflow.add_node("send_connection_request", lambda state: send_connection_with_note(state, st.session_state.page))

    # Set entry point
    workflow.set_entry_point("check_connection")

    # Add conditional edges
    def route_after_connection_check(state):
        if state["status"] == "connected":
            return "send_message"
        elif state["status"] == "not_connected":
            return "send_connection_request"
        else:
            return "end"

    workflow.add_conditional_edges(
        "check_connection",
        route_after_connection_check,
        {
            "send_message": "send_message",
            "send_connection_request": "send_connection_request",
            "end": END
        }
    )

    # Add edges
    workflow.add_edge("send_message", END)
    workflow.add_edge("send_connection_request", END)

    return workflow.compile()

# Initialize session state
def init_session_state():
    if 'email' not in st.session_state:
        st.session_state.email = ""
    if 'password' not in st.session_state:
        st.session_state.password = ""
    if 'page' not in st.session_state:
        st.session_state.page = None
    if 'browser' not in st.session_state:
        st.session_state.browser = None
    if 'playwright' not in st.session_state:
        st.session_state.playwright = None
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
        
        st.subheader("Login Details")
        email = st.text_input("Email", value=st.session_state.email, type="default")
        password = st.text_input("Password", value=st.session_state.password, type="password")
        
        if st.button("Login to LinkedIn"):
            if email and password:
                st.session_state.email = email
                st.session_state.password = password
                initialize_browser()
                if login_to_linkedin(st.session_state.page, email, password):
                    st.session_state.logged_in = True
                    st.success("Logged in successfully!")
                else:
                    st.error("Login failed. Please check your credentials.")
            else:
                st.error("Please enter both email and password")
        
        if st.session_state.logged_in:
            st.success("✅ Logged in to LinkedIn")
            if st.button("Logout"):
                logout()
        
        st.markdown("---")
        st.subheader("Instructions")
        st.markdown("""
        1. Enter your LinkedIn credentials
        2. Login to LinkedIn
        3. Add profiles and messages in the main area
        4. Click 'Start Sending Messages'
        
        **Note:** Use this tool responsibly and comply with LinkedIn's Terms of Service.
        """)

def initialize_browser():
    """Initialize the browser instance"""
    if st.session_state.browser is None:
        try:
            st.session_state.playwright = sync_playwright().start()
            st.session_state.browser = st.session_state.playwright.chromium.launch(headless=False)
            st.session_state.page = st.session_state.browser.new_page()
        except Exception as e:
            st.error(f"Failed to initialize browser: {str(e)}")

def logout():
    """Clean up browser and session state"""
    if st.session_state.browser:
        st.session_state.browser.close()
    if st.session_state.playwright:
        st.session_state.playwright.stop()
    
    st.session_state.browser = None
    st.session_state.page = None
    st.session_state.playwright = None
    st.session_state.logged_in = False
    st.success("Logged out successfully")

def main_interface():
    """Main content area"""
    st.header("LinkedIn Message Sender")
    
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
            if st.button("Start Sending Messages") and not st.session_state.processing:
                if st.session_state.logged_in:
                    st.session_state.processing = True
                    process_messages()
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

def process_messages():
    """Process all messages in the queue"""
    app = create_workflow()
    
    for i, result in enumerate(st.session_state.results):
        if result['status'] == 'Pending':
            # Update status to processing
            st.session_state.results[i]['status'] = 'Processing'
            st.rerun()
            
            # Add random delay to appear more human
            time.sleep(random.randint(2, 5))
            
            # Execute the workflow
            try:
                state_result = app.invoke(AgentState(
                    linkedin_url=result['url'],
                    message=result['message']
                ))
                
                # Update result
                st.session_state.results[i]['status'] = 'Completed'
                st.session_state.results[i]['result'] = state_result.get('result', 'Unknown result')
                st.session_state.results[i]['timestamp'] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                
            except Exception as e:
                st.session_state.results[i]['status'] = 'Failed'
                st.session_state.results[i]['result'] = f"Error: {str(e)}"
                st.session_state.results[i]['timestamp'] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            
            st.rerun()
    
    st.session_state.processing = False
    st.success("All messages processed!")

# Main app
def main():
    init_session_state()
    sidebar()
    
    if not st.session_state.logged_in:
        st.warning("Please login to LinkedIn using the sidebar to get started.")
    
    main_interface()

if __name__ == "__main__":
    main()
