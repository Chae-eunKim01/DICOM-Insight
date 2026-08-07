import os
import json
import sqlite3
import tempfile
from pathlib import Path

_DB_PATH=Path(
    os.environ.get(
        "LOCALAPPDATA",
        tempfile.gettempdir()
    )
)/"PythonDICOMViewer"/"dicom_index_v1.sqlite3"

def _connect():
    _DB_PATH.parent.mkdir(parents=True,exist_ok=True)
    conn=sqlite3.connect(str(_DB_PATH),timeout=2.0)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA synchronous=NORMAL")
    conn.execute("""
        CREATE TABLE IF NOT EXISTS dicom_header(
            path TEXT PRIMARY KEY,
            mtime_ns INTEGER NOT NULL,
            size INTEGER NOT NULL,
            payload TEXT NOT NULL
        )
    """)
    return conn

def _signature(path):
    try:
        st=os.stat(path)
        return int(st.st_mtime_ns),int(st.st_size)
    except OSError:
        return None

def load_cached(paths):
    result={}

    if not paths:
        return result

    try:
        conn=_connect()
        paths=list(paths)

        # 먼저 SQLite에서 해당 path가 실제 cache에 있는지 확인합니다.
        # 첫 Import처럼 cache가 비어 있는 상황에서는 모든 파일에
        # os.stat()을 호출하지 않으므로 초기 Indexing overhead가 줄어듭니다.
        for start in range(0,len(paths),700):
            chunk=paths[start:start+700]
            marks=",".join("?" for _ in chunk)

            rows=conn.execute(
                f"SELECT path,mtime_ns,size,payload "
                f"FROM dicom_header WHERE path IN ({marks})",
                chunk
            ).fetchall()

            for path,mtime_ns,size,payload in rows:
                sig=_signature(path)

                if sig is None or sig!=(mtime_ns,size):
                    continue

                try:
                    result[path]=json.loads(payload)
                except Exception:
                    continue

        conn.close()

    except Exception:
        return {}

    return result

def save_cached(items):
    rows=[]

    for item in items:
        if not item:
            continue

        path=item.get("path")
        if not path:
            continue

        sig=_signature(path)
        if sig is None:
            continue

        try:
            payload=json.dumps(
                item,
                ensure_ascii=False,
                separators=(",",":")
            )
        except Exception:
            continue

        rows.append((path,sig[0],sig[1],payload))

    if not rows:
        return

    try:
        conn=_connect()
        conn.executemany(
            """
            INSERT INTO dicom_header(path,mtime_ns,size,payload)
            VALUES(?,?,?,?)
            ON CONFLICT(path) DO UPDATE SET
                mtime_ns=excluded.mtime_ns,
                size=excluded.size,
                payload=excluded.payload
            """,
            rows
        )
        conn.commit()
        conn.close()
    except Exception:
        pass
