#!/usr/bin/env python
"""
Railway Deployment Pre-Check
Verifies all files are in place before deploying to Railway.
"""

import os
import sys
from pathlib import Path

def check_file(filepath, description):
    """Check if file exists."""
    if os.path.exists(filepath):
        size = os.path.getsize(filepath)
        print(f"✅ {description:45} ({size} bytes)")
        return True
    else:
        print(f"❌ {description:45} (MISSING)")
        return False

def check_git():
    """Check if git is initialized."""
    if os.path.exists('.git'):
        print(f"✅ {'Git repository initialized':45}")
        return True
    else:
        print(f"❌ {'Git repository':45} (Not initialized - run: git init)")
        return False

def check_content(filepath, search_string, description):
    """Check if file contains specific content."""
    if not os.path.exists(filepath):
        return False
    
    with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
        content = f.read()
        if search_string in content:
            print(f"✅ {description:45}")
            return True
        else:
            print(f"⚠️  {description:45} (may need update)")
            return False

def main():
    print("\n" + "="*70)
    print("  RAILWAY DEPLOYMENT PRE-CHECK")
    print("="*70 + "\n")
    
    checks_passed = 0
    checks_total = 0
    
    print("📦 Required Files:")
    print("-" * 70)
    
    files_to_check = [
        ("bdg_predictor/multi_game_collector.py", "Multi-game collector"),
        ("bdg_predictor/firebase_client.py", "Firebase client"),
        ("bdg_predictor/main.py", "Main module"),
        ("bdg_predictor/config.py", "Configuration"),
        ("bdg_predictor/requirements.txt", "Requirements"),
        ("Procfile", "Railway process file"),
        ("runtime.txt", "Python runtime version"),
        (".gitignore", "Git ignore rules"),
    ]
    
    for filepath, description in files_to_check:
        checks_total += 1
        if check_file(filepath, description):
            checks_passed += 1
    
    print("\n🔐 Security Files:")
    print("-" * 70)
    
    if os.path.exists("bdg_predictor/firebase-adminsdk.json"):
        checks_total += 1
        print(f"✅ {'Firebase credentials':45} (DO NOT COMMIT!)")
        checks_passed += 1
    else:
        checks_total += 1
        print(f"❌ {'Firebase credentials':45} (Place in bdg_predictor/)")
    
    print("\n📋 Configuration Checks:")
    print("-" * 70)
    
    checks = [
        (".gitignore", "firebase-adminsdk.json", "Firebase excluded from git"),
        ("Procfile", "multi_game_collector.py", "Procfile references collector"),
        ("runtime.txt", "python-3", "Python version specified"),
    ]
    
    for filepath, search_str, description in checks:
        checks_total += 1
        if check_content(filepath, search_str, description):
            checks_passed += 1
    
    print("\n🌐 Git Status:")
    print("-" * 70)
    
    checks_total += 1
    if check_git():
        checks_passed += 1
    
    # Summary
    print("\n" + "="*70)
    print(f"  SUMMARY: {checks_passed}/{checks_total} checks passed")
    print("="*70 + "\n")
    
    if checks_passed == checks_total:
        print("✅ All checks passed! Ready for Railway deployment.\n")
        print("Next steps:")
        print("  1. git add .")
        print("  2. git commit -m 'BDG Collector ready for Railway'")
        print("  3. git push")
        print("  4. Deploy on Railway.app\n")
        return 0
    else:
        print(f"⚠️  {checks_total - checks_passed} item(s) need attention.\n")
        print("See above for details. Fix issues, then try again.\n")
        return 1

if __name__ == "__main__":
    sys.exit(main())
