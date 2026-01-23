import sys
import argparse
import requests
import sseclient
import threading
import json
import logging

# Configure logging to stderr (so it doesn't interfere with stdio communication)
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s', stream=sys.stderr)
logger = logging.getLogger("mcp_bridge")

def listen_to_sse(url, headers, stop_event):
    """Listens to SSE stream and prints events to stdout."""
    logger.info(f"Connecting to SSE: {url}")
    try:
        response = requests.get(url, headers=headers, stream=True)
        response.raise_for_status()
        client = sseclient.SSEClient(response)
        
        for event in client.events():
            if stop_event.is_set():
                break
            
            if event.event == 'endpoint':
                logger.info(f"Endpoint received: {event.data}")
                # We can store this if needed, but for now we assume we know how to construct POST URL
                # actually we need to extract session_id from it usually? 
                # The MCP spec says the endpoint event contains the relative URI.
                # data: /messages/?session_id=...
                # We need to communicate this back to the main thread or update a global
                global POST_ENDPOINT
                POST_ENDPOINT = event.data
            
            elif event.event == 'message':
                # This is a JSON-RPC message from server
                # Forward to stdout
                print(event.data)
                sys.stdout.flush()
                logger.debug(f"Received from server: {event.data}")
                
    except Exception as e:
        logger.error(f"SSE Error: {e}")
        stop_event.set()

POST_ENDPOINT = None

def main():
    parser = argparse.ArgumentParser(description="MCP Stdio to SSE Bridge")
    parser.add_argument("--url", required=True, help="Base URL of the MCP server (e.g. http://host:8000)")
    parser.add_argument("--token", required=True, help="JWT Token")
    args = parser.parse_args()

    headers = {
        "Authorization": f"Bearer {args.token}",
        "Content-Type": "application/json"
    }
    
    sse_url = f"{args.url}/sse"
    stop_event = threading.Event()
    
    # Start SSE listener thread
    t = threading.Thread(target=listen_to_sse, args=(sse_url, headers, stop_event), daemon=True)
    t.start()
    
    # Read from Stdin (JSON-RPC requests from Claude)
    # Claude sends JSON-RPC lines
    logger.info("Bridge started. Waiting for input...")
    
    try:
        for line in sys.stdin:
            if stop_event.is_set():
                break
            
            if not line.strip():
                continue

            logger.debug(f"Received from Client: {line}")
            
            # Wait for endpoint to be known
            import time
            timeout = 5
            start = time.time()
            while POST_ENDPOINT is None and time.time() - start < timeout:
                time.sleep(0.1)
            
            if POST_ENDPOINT is None:
                logger.error("Timeout waiting for SSE endpoint event")
                continue

            # Send POST
            post_url = f"{args.url}{POST_ENDPOINT}"
            try:
                # We need to handle potential session_id logic if the server changes it, 
                # but usually endpoint event gives the full relative path.
                
                resp = requests.post(post_url, headers=headers, data=line, timeout=10)
                resp.raise_for_status()
                if resp.status_code == 202:
                     # Accepted, response will come via SSE
                     pass
                else:
                     logger.warning(f"Unexpected status code: {resp.status_code}")
                     
            except Exception as e:
                logger.error(f"Failed to post message: {e}")
                
    except KeyboardInterrupt:
        pass
    finally:
        # Give a moment for any pending SSE messages to print if stdin closed abruptly
        import time
        time.sleep(1)
        stop_event.set()

if __name__ == "__main__":
    main()
