#!/usr/bin/env python
"""Resumable progress checker for the route deep-dive ledger fragments.
Run:  python check_progress.py
Prints DONE / TODO / MALFORMED per batch so the work can resume in any session.
A batch is DONE only if its fragment exists, has the exact header, the right
row count, and every row has a valid Verdict + non-empty Real_RoadKM.
"""
import csv, os, sys

PARTS = os.path.dirname(os.path.abspath(__file__))
EXP = ['Route_Code','Route_Name','Eng_O','Eng_D','Eng_KM','Eng_Cycle_Min',
       'Eng_Headway','Eng_Fleet','Eng_Type','Eng_Load','Real_RoadKM',
       'Real_OneWay_Time','Real_Service','Coord_Check','KM_Delta_Pct',
       'Time_Check','Verdict','Finding','Sources']
# expected row counts per batch (from active_routes_for_deepdive.csv)
EXPECT = {'R1':12,'R2':12,'R3':12,'R4':12,'R5':12,'R6':11,
          'C1':13,'C2':13,'C3':13,'C4':13,'C5':13,'C6':13,'C7':13,'C8':13,'C9':11}
VALID = {'PASS','REVIEW','FAIL'}

def check(b):
    f = os.path.join(PARTS, f'ledger_{b}.csv')
    if not os.path.exists(f):
        return 'TODO', 'no file'
    try:
        rows = list(csv.DictReader(open(f, encoding='utf-8-sig')))
    except Exception as e:
        return 'MALFORMED', f'unreadable: {e}'
    if not rows:
        return 'MALFORMED', 'empty'
    if list(rows[0].keys()) != EXP:
        return 'MALFORMED', 'header mismatch'
    if len(rows) != EXPECT[b]:
        return 'MALFORMED', f'{len(rows)} rows, expected {EXPECT[b]}'
    bad = [r['Route_Code'] for r in rows
           if (r.get('Verdict') or '').strip() not in VALID
           or not (r.get('Real_RoadKM') or '').strip()]
    if bad:
        return 'MALFORMED', f'{len(bad)} bad rows (e.g. {bad[:2]})'
    return 'DONE', f'{len(rows)} rows'

def main():
    done=todo=mal=0
    todo_list=[]
    for b in EXPECT:
        st, msg = check(b)
        print(f'{b:3} {st:10} {msg}')
        if st=='DONE': done+=1
        else:
            todo_list.append(b)
            if st=='TODO': todo+=1
            else: mal+=1
    print(f'\nDONE {done}/{len(EXPECT)} | TODO {todo} | MALFORMED {mal}')
    if todo_list:
        print('NEXT (redo/run, one at a time):', ' '.join(todo_list))
    return todo_list

if __name__=='__main__':
    main()
