#!/bin/bash

# Wait for system to fully boot and network to be available
sleep 30

# Navigate to the correct directory
cd /home/pi/Desktop

# Start the assistant program
python3 assistant.py

# If the program crashes, wait and restart
while true; do
    echo "Assistant program crashed, restarting in 10 seconds..."
    sleep 10
    python3 assistant.py
done 