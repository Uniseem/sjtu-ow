"""只读核查对拍库：最终未知父栏目保护不影响此次已经通过的截图数据。"""
import json
import sqlite3

base = '/tmp/sjtu-ow-parity'
with sqlite3.connect(f'file:{base}/new-data/sjtuow.sqlite3?mode=ro', uri=True) as new, sqlite3.connect(f'file:{base}/db.sqlite3?mode=ro', uri=True) as old:
    rows = new.execute("SELECT id,slug,parent_id FROM pages WHERE kind='article' ORDER BY id").fetchall()
    assert rows, 'missing parity articles'
    for ident, slug, parent in rows:
        expected = old.execute('SELECT parent.id FROM wagtailcore_page p JOIN wagtailcore_page parent ON parent.path=substr(p.path,1,length(p.path)-4) WHERE p.id=?', (ident,)).fetchone()
        assert expected is not None and parent is not None and parent == expected[0], (ident, slug, parent, expected)
    print(json.dumps({'articles': rows, 'all_parents_preserved': True}, ensure_ascii=False))
    print('PARITY-PARENT-OK')
