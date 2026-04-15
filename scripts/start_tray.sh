#!/bin/bash
pgrep -f "tray_app.py" > /dev/null || nohup /usr/bin/python3 /Users/moritzcremer/AssistantDev/src/tray_app.py > /tmp/assistantdev_tray.log 2>&1 &
