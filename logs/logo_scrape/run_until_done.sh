#!/bin/zsh
cd /Users/rishirajsinharay/Desktop/Final-Masters-Project
for i in $(seq 1 40); do
  echo "===== round $i  $(date +%H:%M:%S) ====="
  python3 -u logs/logo_scrape/download.py
  code=$?
  if [ $code -eq 0 ]; then echo "ALL DONE round $i"; exit 0; fi
  echo "round $i exit=$code — quiet sleep 600s"
  sleep 600
done
echo "gave up after 40 rounds"
exit 1
