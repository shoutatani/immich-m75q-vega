#!/usr/bin/env python3
"""公式3.3.1処理系を使い、既定モデルと見本サイズのGPUキャッシュを準備する。"""
from pathlib import Path
import subprocess
import sys

subprocess.run([sys.executable,str(Path(__file__).with_name('profile-models.py')),
                '--backend','gpu','--warmup'],check=True)
