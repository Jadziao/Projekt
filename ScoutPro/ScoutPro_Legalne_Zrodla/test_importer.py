import unittest, sqlite3, tempfile, sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).parent))
from import_legal_sources import convert_json, init_db, write_rows, read_catalog
class TestImporter(unittest.TestCase):
    def test_shape_json(self):
        self.assertEqual(convert_json({'a':[1, float('nan')]}),{'a':[1,None]})
    def test_sqlite_insert_is_idempotent(self):
        with sqlite3.connect(':memory:') as con:
            init_db(con)
            entry=next(x for x in read_catalog()['leagues'] if x['slug']=='openfootball-poland-pl1')
            a={'date':'2024-07-19','team1':'A','team2':'B','score':{'ft':[2,1]}}
            write_rows(con,entry,'match','2024-25',[a],'https://openfootball.github.io/europe/poland_2024-25_pl1.json')
            write_rows(con,entry,'match','2024-25',[a],'https://openfootball.github.io/europe/poland_2024-25_pl1.json')
            self.assertEqual(con.execute('SELECT count(*) FROM source_records').fetchone()[0],1)
    def test_catalog_legal_source_and_url(self):
        catalog=read_catalog()
        self.assertTrue(len(catalog['leagues'])>=80)
        self.assertTrue(all(x['license_confirmed'] for x in catalog['leagues']))
        self.assertTrue(all(x['source_url'].startswith('https://') for x in catalog['leagues']))
if __name__=='__main__': unittest.main()
