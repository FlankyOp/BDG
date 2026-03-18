#!/usr/bin/env python
import sys
sys.path.insert(0, 'bdg_predictor')

from firebase_client import _get_firestore_client

client = _get_firestore_client()
if client:
    try:
        col = client.collection('bdg_history')
        docs = col.order_by('ts', direction='DESCENDING').limit(5).get()
        print('✓ Latest 5 documents in bdg_history:')
        for i, doc in enumerate(docs, 1):
            data = doc.to_dict()
            period = data.get('period')
            number = data.get('number')
            color = data.get('color')
            size = data.get('size')
            print(f'{i}. Period={period} | Number={number} | {color} | {size}')
    except Exception as e:
        print(f'✗ Error: {e}')
        import traceback
        traceback.print_exc()
else:
    print('✗ Firestore client failed')
