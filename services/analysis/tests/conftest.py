import sys
from pathlib import Path

# Permite "import synth" (gerador de sinais de teste) nos módulos de teste.
sys.path.insert(0, str(Path(__file__).parent))
