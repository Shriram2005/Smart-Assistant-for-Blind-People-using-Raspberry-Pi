#!/bin/bash

# Wait for the system to be fully ready
sleep 15

# Make sure audio system is ready
while ! aplay -l | grep -q 'card'; do
    sleep 2
done

# Set audio permissions
amixer sset 'Master' 100%

# Start the program (adjust path to your actual location)
cd /home/pi/Desktop
python3 smart_aid.py

