# Phase 1 — Run Order and Checklist

## Folder Setup
Place all these files + serviceAccountKey.json in the same folder.

## Run Order (do NOT skip steps)

| Step | File | What to check |
|------|------|---------------|
| 0 | `pip install -r requirements.txt` | No errors |
| 1 | `task1_2_firebase_connect.py` | Sees all 4 nodes |
| 2 | `task1_3_read_firebase.py` | Shows initialized structure |
| 3 | `task1_4_write_test_record.py` | Record visible in Firebase Console |
| 4 | `task1_5_read_to_dataframe.py` | DataFrame prints correctly |
| 5 | `task1_6_synthetic_generator.py` | 3 plots saved, all checks PASS |
| 6 | `task1_7_push_synthetic.py` | All 2160 records pushed |
| 7 | `task1_8_verify_roundtrip.py` | ALL CHECKS PASSED |

## Common Errors

**FileNotFoundError: serviceAccountKey.json**
→ Make sure the key file is in the same folder as the scripts.

**TransportError / connection refused**
→ Check your internet connection. Firebase needs outbound HTTPS.

**Permission denied on Firebase**
→ Go to Firebase Console → Realtime Database → Rules
→ Temporarily set: `{ "rules": { ".read": true, ".write": true } }`
→ (Only for development — not for production)

**synthetic_data.csv not found**
→ Run task1_6 before task1_7.
