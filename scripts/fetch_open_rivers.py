"""Optional cache prewarm for the authoritative OS Open Rivers input."""
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from backend.open_rivers import fetch
if __name__=='__main__':
 result=fetch()
 print('OS Open Rivers available; SHA-256',result['archive']['sha256'])
