"""Lease-based, bounded, idempotent worker. PostgreSQL or local SQLite."""
import time
import threading
from sqlalchemy import select, update, or_, and_
from backend.core import *

def claim():
    with engine.begin() as c:
        # Expired third attempts terminate instead of getting stuck running.
        c.execute(update(assessments).where(assessments.c.state=='running',assessments.c.lease<time.time(),assessments.c.attempts>=3).values(state='failed',error='Worker lease expired after three attempts.'))
        q=select(assessments).where(assessments.c.attempts<3,or_(and_(assessments.c.state=='queued',assessments.c.lease<=time.time()),and_(assessments.c.state=='running',assessments.c.lease<time.time()))).order_by(assessments.c.created).limit(1)
        if engine.dialect.name=='postgresql': q=q.with_for_update(skip_locked=True)
        r=c.execute(q).mappings().first()
        if not r:return None
        token=uid()
        changed=c.execute(update(assessments).where(assessments.c.id==r['id'],assessments.c.token==r['token'],assessments.c.attempts==r['attempts']).values(state='running',attempts=r['attempts']+1,token=token,lease=time.time()+120))
        if changed.rowcount!=1:return None
        return dict(r)|{'token':token,'attempts':r['attempts']+1}

def once():
    job=claim()
    if not job:return False
    stop=threading.Event()
    def renew():
        while not stop.wait(30):
            with engine.begin() as c:
                changed=c.execute(update(assessments).where(assessments.c.id==job['id'],assessments.c.token==job['token'],assessments.c.state=='running').values(lease=time.time()+120))
                if changed.rowcount!=1:return
    heartbeat=threading.Thread(target=renew,daemon=True)
    heartbeat.start()
    try:
        result=analyze(job)
        values={'state':'completed' if result['completeness']==result['dataset_count'] else 'partial','result':result,'error':None}
    except Exception as e:
        values={'state':'failed' if job['attempts']>=3 else 'queued','error':str(e)[:500],'lease':time.time()+2**job['attempts']}
    finally:
        stop.set()
        heartbeat.join(timeout=1)
    with engine.begin() as c:
        c.execute(update(assessments).where(assessments.c.id==job['id'],assessments.c.token==job['token'],assessments.c.state=='running').values(**values))
    return True
if __name__=='__main__':
    init()
    while True:
        if not once():time.sleep(1)
