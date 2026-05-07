#!/bin/bash
set -e

cd "$(dirname "$0")/.."

docker compose run --rm rtl-sdr python3 -c "import matplotlib; matplotlib.use('Qt5Agg'); import matplotlib.pyplot as plt; plt.plot([1,2,3]); plt.title('Display OK'); plt.show()"
