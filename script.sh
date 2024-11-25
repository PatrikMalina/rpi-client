#!/bin/bash

# Start from 1 and go up to 10000
for ((i=100; i<=10000; i++)); do
    echo "$i"   # Print the current count
    sleep 0.5     # Wait for 1 second
done
