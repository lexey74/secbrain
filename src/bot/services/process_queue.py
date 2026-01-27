from typing import Optional, List, Tuple, Dict
from datetime import datetime

class ProcessQueue:
    """Global queue for managing transcription, AI, and RAG processes"""
    
    def __init__(self):
        self.transcribe_queue: List[Tuple[int, str, datetime]] = []  # [(user_id, username, timestamp)]
        self.ai_queue: List[Tuple[int, str, datetime]] = []        # [(user_id, username, timestamp)]
        self.rag_queue: List[Tuple[int, str, datetime]] = []       # [(user_id, username, timestamp)]
        
        self.transcribe_running: Optional[Tuple[int, str, int]] = None  # (user_id, username, pid)
        self.ai_running: Optional[Tuple[int, str, int]] = None        # (user_id, username, pid)
        self.rag_running: Optional[Tuple[int, str, int]] = None       # (user_id, username, pid)
    
    def add_to_transcribe_queue(self, user_id: int, username: str) -> int:
        """Adds user to transcribe queue. Returns position."""
        for item in self.transcribe_queue:
            if item[0] == user_id:
                return self.transcribe_queue.index(item) + 1
        
        self.transcribe_queue.append((user_id, username, datetime.now()))
        return len(self.transcribe_queue)
    
    def add_to_ai_queue(self, user_id: int, username: str) -> int:
        """Adds user to AI queue. Returns position."""
        for item in self.ai_queue:
            if item[0] == user_id:
                return self.ai_queue.index(item) + 1
        
        self.ai_queue.append((user_id, username, datetime.now()))
        return len(self.ai_queue)

    def add_to_rag_queue(self, user_id: int, username: str) -> int:
        """Adds user to RAG queue. Returns position."""
        for item in self.rag_queue:
            if item[0] == user_id:
                return self.rag_queue.index(item) + 1

        self.rag_queue.append((user_id, username, datetime.now()))
        return len(self.rag_queue)
    
    def start_transcribe(self, user_id: int, username: str, pid: int):
        self.transcribe_running = (user_id, username, pid)
        self.transcribe_queue = [item for item in self.transcribe_queue if item[0] != user_id]
    
    def start_ai(self, user_id: int, username: str, pid: int):
        self.ai_running = (user_id, username, pid)
        self.ai_queue = [item for item in self.ai_queue if item[0] != user_id]

    def start_rag(self, user_id: int, username: str, pid: int):
        self.rag_running = (user_id, username, pid)
        self.rag_queue = [item for item in self.rag_queue if item[0] != user_id]
    
    def finish_transcribe(self):
        self.transcribe_running = None
    
    def finish_ai(self):
        self.ai_running = None

    def finish_rag(self):
        self.rag_running = None
    
    def get_transcribe_status(self, user_id: int) -> Dict:
        if self.transcribe_running and self.transcribe_running[0] == user_id:
            return {
                'status': 'running',
                'position': 0,
                'pid': self.transcribe_running[2]
            }
        
        for i, item in enumerate(self.transcribe_queue):
            if item[0] == user_id:
                return {
                    'status': 'queued',
                    'position': i + 1,
                    'total': len(self.transcribe_queue)
                }
        
        return {'status': 'not_in_queue'}
    
    def get_ai_status(self, user_id: int) -> Dict:
        if self.ai_running and self.ai_running[0] == user_id:
            return {
                'status': 'running',
                'position': 0,
                'pid': self.ai_running[2]
            }
        
        for i, item in enumerate(self.ai_queue):
            if item[0] == user_id:
                return {
                    'status': 'queued',
                    'position': i + 1,
                    'total': len(self.ai_queue)
                }
        
        return {'status': 'not_in_queue'}

    def get_rag_status(self, user_id: int) -> Dict:
        if self.rag_running and self.rag_running[0] == user_id:
            return {
                'status': 'running',
                'position': 0,
                'pid': self.rag_running[2]
            }

        for i, item in enumerate(self.rag_queue):
            if item[0] == user_id:
                return {
                    'status': 'queued',
                    'position': i + 1,
                    'total': len(self.rag_queue)
                }

        return {'status': 'not_in_queue'}
    
    def can_start_transcribe(self) -> bool:
        return self.transcribe_running is None and len(self.transcribe_queue) > 0
    
    def can_start_ai(self) -> bool:
        return self.ai_running is None and len(self.ai_queue) > 0

    def can_start_rag(self) -> bool:
        return self.rag_running is None and len(self.rag_queue) > 0

# Global instance
queue = ProcessQueue()
